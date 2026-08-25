import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from fastapi import FastAPI


app = FastAPI(
    title="Shkar Bourse API",
    version="11.0.0"
)


# =========================================================
# TINDEX
# =========================================================

TINDEX_BASE_URL = "https://tindex.app/api/public"

OVERVIEW_URL = (
    f"{TINDEX_BASE_URL}/stock-market/overview"
)

STOCKS_URL = (
    f"{TINDEX_BASE_URL}/stocks/by-category/stock-energy"
)

HISTORY_BASE_URL = (
    f"{TINDEX_BASE_URL}/stocks"
)


# =========================================================
# SETTINGS
# =========================================================

DAILY_LIMIT = 100

REQUEST_INTERVAL = 75

MARKET_START_HOUR = 9
MARKET_START_MINUTE = 0

MARKET_END_HOUR = 12
MARKET_END_MINUTE = 30

PER_PAGE = 100

MAX_PAGES = 5000

# دو چرخه کامل بازار
MARKET_CYCLES_BEFORE_HISTORY = 2

HISTORY_RANGE = "3m"


# =========================================================
# GLOBAL STATE
# =========================================================

_cache_data = None
_cache_time = 0.0


_full_market_cache = None
_full_market_cache_time = 0.0


_daily_requests = []

_last_request_time = 0.0
_last_error = None


_market_page = 1
_market_last_page = None
_market_total_symbols = None

_market_collecting = False
_market_complete = False

_market_started_at = None
_market_completed_at = None

_market_buffer = []

_market_cycles_completed = 0


_history_started = False
_history_complete = False

_history_queue = []
_history_results = {}

_history_total_requested = 0
_history_total_completed = 0

_history_started_at = None
_history_completed_at = None


_background_thread_started = False

_state_lock = threading.Lock()

# قفل اختصاصی درخواست TIndex
# تضمین می‌کند دو Thread همزمان درخواست نفرستند.
_tindex_request_lock = threading.Lock()


# =========================================================
# TIME
# =========================================================

def tehran_now():
    return datetime.now(
        ZoneInfo("Asia/Tehran")
    )


def today_string():
    return tehran_now().strftime(
        "%Y-%m-%d"
    )


def is_trading_day():

    now = tehran_now()

    return now.weekday() in [
        5,  # Saturday
        6,  # Sunday
        0,  # Monday
        1,  # Tuesday
        2   # Wednesday
    ]


def minutes_since_midnight():

    now = tehran_now()

    return (
        now.hour * 60
        + now.minute
    )


def market_start_minutes():

    return (
        MARKET_START_HOUR * 60
        + MARKET_START_MINUTE
    )


def market_end_minutes():

    return (
        MARKET_END_HOUR * 60
        + MARKET_END_MINUTE
    )


def is_market_open():

    if not is_trading_day():
        return False

    current = minutes_since_midnight()

    return (
        market_start_minutes()
        <= current
        <= market_end_minutes()
    )


def current_market_mode():

    if is_market_open():
        return "active"

    return "inactive"


def market_start_datetime():

    now = tehran_now()

    return now.replace(
        hour=MARKET_START_HOUR,
        minute=MARKET_START_MINUTE,
        second=0,
        microsecond=0
    )


def seconds_until_market_start():

    now = tehran_now()

    if not is_trading_day():
        return 0

    start = market_start_datetime()

    if now < start:

        return max(
            0,
            int(
                (
                    start - now
                ).total_seconds()
            )
        )

    return 0


# =========================================================
# DAILY REQUEST LIMIT
# =========================================================

def cleanup_daily_requests():

    global _daily_requests

    current_day = today_string()

    with _state_lock:

        _daily_requests = [
            item
            for item in _daily_requests
            if item.get("date") == current_day
        ]


def daily_requests_used():

    cleanup_daily_requests()

    with _state_lock:

        return len(
            _daily_requests
        )


def daily_requests_remaining():

    return max(
        0,
        DAILY_LIMIT
        - daily_requests_used()
    )


def register_request():

    with _state_lock:

        _daily_requests.append({
            "date": today_string(),
            "time": time.time()
        })


# =========================================================
# REQUEST TIMING
# =========================================================

def seconds_until_next_request():

    with _state_lock:

        last_request = _last_request_time

    if last_request <= 0:

        if is_market_open():

            start = market_start_datetime()

            elapsed = (
                tehran_now()
                - start
            ).total_seconds()

            remaining = (
                REQUEST_INTERVAL
                - elapsed
            )

            if remaining <= 0:
                return 0

            return int(
                remaining
            ) + 1

        return 0

    elapsed = (
        time.time()
        - last_request
    )

    remaining = (
        REQUEST_INTERVAL
        - elapsed
    )

    if remaining <= 0:
        return 0

    return int(
        remaining
    ) + 1


# =========================================================
# REQUEST PERMISSION
# =========================================================

def can_request_tindex():

    cleanup_daily_requests()

    if not is_market_open():

        return (
            False,
            "در حال حاضر خارج از زمان جمع‌آوری بازار است."
        )

    if daily_requests_used() >= DAILY_LIMIT:

        return (
            False,
            "سقف 100 درخواست روزانه مصرف شده است."
        )

    wait_seconds = (
        seconds_until_next_request()
    )

    if wait_seconds > 0:

        return (
            False,
            (
                "برای درخواست بعدی باید "
                f"{wait_seconds} ثانیه صبر شود."
            )
        )

    return True, None


# =========================================================
# HEADERS
# =========================================================

def get_headers():

    token = os.getenv(
        "TINDEX_TOKEN",
        ""
    ).strip()

    if not token:

        return None

    return {

        "Authorization":
            f"Bearer {token}",

        "Accept":
            "application/json",

        "User-Agent":
            "ShkarBoursePro2/11.0"
    }


# =========================================================
# HELPERS
# =========================================================

def safe_number(
    value,
    default=0.0
):

    try:

        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return default


def safe_int(
    value,
    default=0
):

    try:

        return int(
            float(value)
        )

    except (
        TypeError,
        ValueError
    ):

        return default


# =========================================================
# TINDEX REQUEST
# =========================================================

def make_tindex_request(
    url,
    params=None
):

    global _last_error
    global _last_request_time

    # -----------------------------------------------------
    # فقط یک Thread در هر لحظه اجازه درخواست دارد
    # -----------------------------------------------------

    with _tindex_request_lock:

        headers = get_headers()

        if headers is None:

            _last_error = (
                "TINDEX_TOKEN تنظیم نشده است."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
            }


        allowed, reason = (
            can_request_tindex()
        )

        if not allowed:

            return {
                "status": "error",
                "source": "local-rate-limit",
                "message": reason,
                "wait_seconds":
                    seconds_until_next_request(),
                "daily_requests_used":
                    daily_requests_used(),
                "daily_requests_remaining":
                    daily_requests_remaining()
            }


        request_time = time.time()

        with _state_lock:

            _last_request_time = (
                request_time
            )

        register_request()


        try:

            response = requests.get(

                url,

                headers=headers,

                params=params,

                timeout=30
            )


            if response.status_code == 401:

                _last_error = (
                    "توکن TIndex معتبر نیست."
                )

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error
                }


            if response.status_code == 429:

                _last_error = (
                    "محدودیت درخواست TIndex فعال شده است."
                )

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error,
                    "daily_requests_used":
                        daily_requests_used(),
                    "daily_requests_remaining":
                        daily_requests_remaining()
                }


            response.raise_for_status()

            result = response.json()


            if not isinstance(
                result,
                dict
            ):

                _last_error = (
                    "پاسخ TIndex معتبر نیست."
                )

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error
                }


            if result.get(
                "success"
            ) is False:

                message = result.get(
                    "message",
                    "TIndex پاسخ موفقی ارسال نکرد."
                )

                _last_error = str(
                    message
                )

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error
                }


            _last_error = None


            return {

                "status": "ok",

                "source": "tindex.app",

                "data": result.get(
                    "data"
                ),

                "meta": result.get(
                    "meta"
                )
            }


        except requests.exceptions.RequestException as exc:

            _last_error = str(exc)

            return {

                "status": "error",

                "source": "tindex.app",

                "message":
                    "خطا در اتصال به TIndex: "
                    + str(exc)
            }


        except ValueError:

            _last_error = (
                "پاسخ TIndex JSON معتبر نبود."
            )

            return {

                "status": "error",

                "source": "tindex.app",

                "message": _last_error
            }


# =========================================================
# OVERVIEW
# =========================================================

def get_overview():

    global _cache_data
    global _cache_time

    now = time.time()

    if (
        _cache_data is not None
        and
        now - _cache_time < 75
    ):

        return {

            "status": "ok",

            "source": "tindex.app",

            "cached": True,

            "data": _cache_data
        }


    result = make_tindex_request(
        OVERVIEW_URL
    )


    if result["status"] != "ok":
        return result


    _cache_data = result.get(
        "data"
    )

    _cache_time = time.time()


    return {

        "status": "ok",

        "source": "tindex.app",

        "cached": False,

        "data": _cache_data
    }


# =========================================================
# MARKET CYCLE
# =========================================================

def reset_market_cycle():

    global _market_page
    global _market_last_page
    global _market_total_symbols

    global _market_collecting
    global _market_complete

    global _market_started_at
    global _market_completed_at

    global _market_buffer

    _market_page = 1

    _market_last_page = None

    _market_total_symbols = None

    _market_collecting = True

    _market_complete = False

    _market_started_at = time.time()

    _market_completed_at = None

    _market_buffer = []


def finish_market_cycle():

    global _full_market_cache
    global _full_market_cache_time

    global _market_collecting
    global _market_complete

    global _market_completed_at

    global _market_cycles_completed

    global _market_page
    global _market_buffer

    _full_market_cache = list(
        _market_buffer
    )

    _full_market_cache_time = (
        time.time()
    )

    _market_complete = True

    _market_collecting = False

    _market_completed_at = (
        time.time()
    )

    _market_cycles_completed += 1

    _market_page = 1

    _market_buffer = []


# =========================================================
# HISTORY RESET
# =========================================================

def reset_history():

    global _history_started
    global _history_complete

    global _history_queue
    global _history_results

    global _history_total_requested
    global _history_total_completed

    global _history_started_at
    global _history_completed_at

    _history_started = False

    _history_complete = False

    _history_queue = []

    _history_results = {}

    _history_total_requested = 0

    _history_total_completed = 0

    _history_started_at = None

    _history_completed_at = None


# =========================================================
# ANALYSIS
# =========================================================

def is_valid_stock(stock):

    if not isinstance(
        stock,
        dict
    ):
        return False

    return bool(
        stock.get("slug")
        or stock.get("ticker")
    )


def calculate_score(stock):

    score = 0.0

    change = safe_number(
        stock.get(
            "change",
            stock.get(
                "change_percent",
                0
            )
        )
    )

    value = safe_number(
        stock.get(
            "value",
            stock.get(
                "trade_value",
                0
            )
        )
    )

    volume = safe_number(
        stock.get(
            "volume",
            0
        )
    )

    market_cap = safe_number(
        stock.get(
            "market_cap",
            0
        )
    )

    pe = stock.get(
        "pe"
    )


    if change >= 3:
        score += 20
    elif change >= 2:
        score += 15
    elif change >= 1:
        score += 8
    elif change > 0:
        score += 4
    elif change <= -3:
        score -= 15
    elif change <= -2:
        score -= 10


    if value >= 10_000_000_000_000:
        score += 20
    elif value >= 5_000_000_000_000:
        score += 15
    elif value >= 1_000_000_000_000:
        score += 10
    elif value >= 100_000_000_000:
        score += 5


    if volume >= 1_000_000_000:
        score += 10
    elif volume >= 100_000_000:
        score += 6
    elif volume >= 10_000_000:
        score += 3


    if market_cap > 0:
        score += 5


    if pe is not None:

        pe_value = safe_number(
            pe,
            0
        )

        if 0 < pe_value <= 6:
            score += 15
        elif 6 < pe_value <= 10:
            score += 10
        elif 10 < pe_value <= 15:
            score += 5
        elif pe_value > 30:
            score -= 8
        elif pe_value < 0:
            score -= 5


    return max(
        0,
        min(
            100,
            round(score)
        )
    )


def build_reasons(stock):

    reasons = []

    change = safe_number(
        stock.get(
            "change",
            stock.get(
                "change_percent",
                0
            )
        )
    )

    value = safe_number(
        stock.get(
            "value",
            stock.get(
                "trade_value",
                0
            )
        )
    )

    pe = stock.get(
        "pe"
    )


    if change >= 2:

        reasons.append(
            "مومنتوم روزانه مثبت"
        )

    elif change > 0:

        reasons.append(
            "تغییر روزانه مثبت"
        )

    elif change < -2:

        reasons.append(
            "فشار فروش روزانه"
        )


    if value >= 10_000_000_000_000:

        reasons.append(
            "ارزش معاملات بسیار بالا"
        )

    elif value >= 1_000_000_000_000:

        reasons.append(
            "نقدشوندگی مناسب"
        )


    if pe is not None:

        pe_value = safe_number(
            pe,
            0
        )

        if 0 < pe_value <= 10:

            reasons.append(
                "P/E نسبتاً مناسب"
            )

        elif pe_value > 30:

            reasons.append(
                "P/E بالا"
            )


    if not reasons:

        reasons.append(
            "نیازمند بررسی عمیق‌تر"
        )


    return reasons


def normalize_stock(stock):

    return {

        "slug": stock.get("slug"),

        "ticker": stock.get("ticker"),

        "name": stock.get("name"),

        "sector": stock.get("sector"),

        "current_price":
            stock.get(
                "last_price",
                stock.get(
                    "current_price"
                )
            ),

        "closing_price":
            stock.get(
                "closing_price"
            ),

        "change_percent":
            stock.get(
                "change",
                stock.get(
                    "change_percent"
                )
            ),

        "closing_change_percent":
            stock.get(
                "closing_change"
            ),

        "volume":
            stock.get("volume"),

        "trade_value":
            stock.get(
                "value",
                stock.get(
                    "trade_value"
                )
            ),

        "market_cap":
            stock.get(
                "market_cap"
            ),

        "pe":
            stock.get("pe"),

        "updated_at":
            stock.get(
                "updated_at"
            ),

        "score":
            calculate_score(stock),

        "reasons":
            build_reasons(stock)
    }


def analyze_full_market(stocks):

    candidates = []

    for stock in stocks:

        if not is_valid_stock(stock):
            continue

        candidates.append(
            normalize_stock(stock)
        )


    short_term = sorted(
        candidates,
        key=lambda x: (
            x["score"],
            safe_number(
                x["trade_value"]
            ),
            safe_number(
                x["change_percent"]
            )
        ),
        reverse=True
    )


    six_month = sorted(
        candidates,
        key=lambda x: (
            x["score"],
            safe_number(
                x["market_cap"]
            ),
            safe_number(
                x["trade_value"]
            )
        ),
        reverse=True
    )


    gainers = sorted(
        candidates,
        key=lambda x:
            safe_number(
                x["change_percent"]
            ),
        reverse=True
    )


    losers = sorted(
        candidates,
        key=lambda x:
            safe_number(
                x["change_percent"]
            )
    )


    most_active = sorted(
        candidates,
        key=lambda x:
            safe_number(
                x["trade_value"]
            ),
        reverse=True
    )


    return {

        "candidate_count":
            len(candidates),

        "short_term_top_20":
            short_term[:20],

        "six_month_top_20":
            six_month[:20],

        "top_gainers":
            gainers[:20],

        "top_losers":
            losers[:20],

        "most_active":
            most_active[:20]
    }


# =========================================================
# BUILD HISTORY QUEUE
# =========================================================

def build_history_queue():

    global _history_queue
    global _history_started
    global _history_complete

    global _history_total_requested
    global _history_total_completed

    global _history_started_at


    if _history_started:
        return


    if (
        _market_cycles_completed
        <
        MARKET_CYCLES_BEFORE_HISTORY
    ):
        return


    if not isinstance(
        _full_market_cache,
        list
    ):
        return


    # =====================================================
    # مهم:
    # تعداد نمادهای History دقیقاً برابر
    # تعداد درخواست‌های باقی‌مانده است.
    # =====================================================

    remaining_requests = (
        daily_requests_remaining()
    )


    if remaining_requests <= 0:

        _history_started = True

        _history_complete = True

        _history_total_requested = 0

        return


    # =====================================================
    # رتبه‌بندی کل بازار
    # =====================================================

    all_ranked = sorted(

        [
            normalize_stock(stock)

            for stock in _full_market_cache

            if is_valid_stock(stock)
        ],

        key=lambda x: (
            x["score"],
            safe_number(
                x["trade_value"]
            ),
            safe_number(
                x["change_percent"]
            )
        ),

        reverse=True
    )


    all_ranked = [

        stock

        for stock in all_ranked

        if stock.get("slug")
    ]


    # =====================================================
    # تعداد History
    #
    # هیچ سقف مصنوعی مثل 20 یا 100 اعمال نمی‌کنیم.
    #
    # فقط:
    # remaining requests
    # =====================================================

    history_count = min(

        remaining_requests,

        len(all_ranked)
    )


    _history_queue = [

        all_ranked[index]

        for index in range(
            history_count
        )
    ]


    _history_total_requested = (
        len(_history_queue)
    )

    _history_total_completed = 0

    _history_started = True

    _history_complete = (
        len(_history_queue) == 0
    )

    _history_started_at = (
        time.time()
    )


# =========================================================
# HISTORY REQUEST
# =========================================================

def request_stock_history(stock):

    slug = stock.get(
        "slug"
    )

    if not slug:

        return {

            "status": "error",

            "source": "local",

            "message":
                "slug نماد برای History وجود ندارد."
        }


    history_url = (
        f"{HISTORY_BASE_URL}/"
        f"{slug}/history"
    )


    result = make_tindex_request(

        history_url,

        params={
            "range": HISTORY_RANGE
        }
    )


    if result["status"] != "ok":
        return result


    return {

        "status": "ok",

        "source": "tindex.app",

        "slug": slug,

        "ticker":
            stock.get("ticker"),

        "name":
            stock.get("name"),

        "data":
            result.get("data")
    }


# =========================================================
# HISTORY COLLECTOR
# =========================================================

def collect_history_background():

    global _history_complete
    global _history_total_completed
    global _history_completed_at
    global _last_error


    while True:

        try:

            # -------------------------------------------------
            # روز معاملاتی
            # -------------------------------------------------

            if not is_trading_day():

                time.sleep(30)

                continue


            # -------------------------------------------------
            # بازار باید باز باشد
            # -------------------------------------------------

            if not is_market_open():

                time.sleep(30)

                continue


            # -------------------------------------------------
            # دو چرخه کامل
            # -------------------------------------------------

            if (
                _market_cycles_completed
                <
                MARKET_CYCLES_BEFORE_HISTORY
            ):

                time.sleep(10)

                continue


            # -------------------------------------------------
            # ساخت صف
            # -------------------------------------------------

            if not _history_started:

                build_history_queue()


            # -------------------------------------------------
            # تمام شده
            # -------------------------------------------------

            if _history_complete:

                time.sleep(30)

                continue


            # -------------------------------------------------
            # سهمیه
            # -------------------------------------------------

            if daily_requests_remaining() <= 0:

                _history_complete = True

                _history_completed_at = (
                    time.time()
                )

                continue


            # -------------------------------------------------
            # فاصله
            # -------------------------------------------------

            wait_seconds = (
                seconds_until_next_request()
            )


            if wait_seconds > 0:

                time.sleep(
                    min(
                        30,
                        max(
                            1,
                            wait_seconds
                        )
                    )
                )

                continue


            # -------------------------------------------------
            # صف
            # -------------------------------------------------

            if not _history_queue:

                _history_complete = True

                _history_completed_at = (
                    time.time()
                )

                continue


            # -------------------------------------------------
            # نماد بعدی
            # -------------------------------------------------

            stock = _history_queue.pop(0)


            result = request_stock_history(
                stock
            )


            if result["status"] == "ok":

                slug = stock.get(
                    "slug"
                )

                _history_results[slug] = {

                    "slug":
                        slug,

                    "ticker":
                        stock.get(
                            "ticker"
                        ),

                    "name":
                        stock.get(
                            "name"
                        ),

                    "score":
                        stock.get(
                            "score"
                        ),

                    "reasons":
                        stock.get(
                            "reasons"
                        ),

                    "history":
                        result.get(
                            "data"
                        ),

                    "received_at":
                        time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime()
                        )
                }

                _history_total_completed += 1


            else:

                _last_error = result.get(
                    "message"
                )


            if not _history_queue:

                _history_complete = True

                _history_completed_at = (
                    time.time()
                )


        except Exception as exc:

            _last_error = str(exc)

            time.sleep(30)


# =========================================================
# MARKET COLLECTOR
# =========================================================

def collect_market_background():

    global _market_page
    global _market_last_page
    global _market_total_symbols

    global _market_collecting
    global _market_complete

    global _last_error

    global _daily_requests
    global _last_request_time

    global _full_market_cache
    global _full_market_cache_time


    local_day = None


    while True:

        try:

            current_day = today_string()


            # =================================================
            # روز جدید
            # =================================================

            if local_day != current_day:

                local_day = current_day

                with _state_lock:

                    _daily_requests = []

                    _last_request_time = 0.0


                _market_page = 1

                _market_last_page = None

                _market_total_symbols = None

                _market_collecting = False

                _market_complete = False

                _market_cycles_completed = 0

                _market_started_at = None

                _market_completed_at = None

                _market_buffer = []


                reset_history()


                _full_market_cache = None

                _full_market_cache_time = 0.0


            # =================================================
            # روز غیر معاملاتی
            # =================================================

            if not is_trading_day():

                time.sleep(30)

                continue


            # =================================================
            # خارج بازار
            # =================================================

            if not is_market_open():

                wait_start = (
                    seconds_until_market_start()
                )

                if wait_start > 0:

                    time.sleep(
                        min(
                            30,
                            max(
                                1,
                                wait_start
                            )
                        )
                    )

                else:

                    time.sleep(30)

                continue


            # =================================================
            # سقف روزانه
            # =================================================

            if daily_requests_remaining() <= 0:

                time.sleep(30)

                continue


            # =================================================
            # بعد از دو چرخه
            #
            # History Collector ادامه می‌دهد.
            # =================================================

            if (
                _market_cycles_completed
                >=
                MARKET_CYCLES_BEFORE_HISTORY
            ):

                if not _history_started:

                    build_history_queue()

                time.sleep(5)

                continue


            # =================================================
            # فاصله
            # =================================================

            wait_seconds = (
                seconds_until_next_request()
            )


            if wait_seconds > 0:

                time.sleep(
                    min(
                        30,
                        max(
                            1,
                            wait_seconds
                        )
                    )
                )

                continue


            # =================================================
            # شروع چرخه
            # =================================================

            if not _market_collecting:

                reset_market_cycle()


            page = _market_page


            # =================================================
            # درخواست
            # =================================================

            result = make_tindex_request(

                STOCKS_URL,

                params={
                    "page": page,
                    "per_page": PER_PAGE
                }
            )


            if result["status"] != "ok":

                _market_collecting = False

                _last_error = result.get(
                    "message"
                )

                time.sleep(30)

                continue


            data = result.get(
                "data"
            )


            if not isinstance(
                data,
                dict
            ):

                _market_collecting = False

                _last_error = (
                    "ساختار data بازار معتبر نیست."
                )

                time.sleep(30)

                continue


            rows = data.get(
                "rows",
                []
            )


            if isinstance(
                rows,
                list
            ):

                _market_buffer.extend(
                    rows
                )


            meta = result.get(
                "meta"
            )


            if not isinstance(
                meta,
                dict
            ):

                meta = {}


            total = meta.get(
                "total"
            )


            if total is not None:

                _market_total_symbols = (
                    safe_int(
                        total,
                        0
                    )
                )


            last_page = meta.get(
                "last_page"
            )


            if last_page is not None:

                _market_last_page = (
                    safe_int(
                        last_page,
                        page
                    )
                )


            if (

                _market_last_page is None

                and

                _market_total_symbols is not None

                and

                _market_total_symbols > 0

            ):

                _market_last_page = (

                    (
                        _market_total_symbols
                        + PER_PAGE
                        - 1
                    )
                    // PER_PAGE
                )


            has_more = meta.get(
                "has_more"
            )


            if has_more is None:

                if _market_last_page is not None:

                    has_more = (
                        page
                        <
                        _market_last_page
                    )

                elif len(rows) >= PER_PAGE:

                    has_more = True

                else:

                    has_more = False


            # =================================================
            # تعداد واقعی صفحات
            # =================================================

            if (

                _market_total_symbols is not None

                and

                _market_total_symbols > 0

            ):

                required_pages = (

                    (
                        _market_total_symbols
                        + PER_PAGE
                        - 1
                    )
                    // PER_PAGE
                )

                _market_last_page = (
                    required_pages
                )

                has_more = (
                    page
                    <
                    required_pages
                )


            # =================================================
            # پایان چرخه
            # =================================================

            if (

                not has_more

                or

                (
                    _market_last_page is not None
                    and
                    page >= _market_last_page
                )

                or

                page >= MAX_PAGES

            ):

                finish_market_cycle()

                continue


            _market_page += 1


        except Exception as exc:

            _last_error = str(exc)

            _market_collecting = False

            time.sleep(30)


# =========================================================
# BACKGROUND START
# =========================================================

def start_background_collectors():

    global _background_thread_started

    if _background_thread_started:
        return


    _background_thread_started = True


    market_thread = threading.Thread(
        target=collect_market_background,
        daemon=True,
        name="market-collector"
    )


    history_thread = threading.Thread(
        target=collect_history_background,
        daemon=True,
        name="history-collector"
    )


    market_thread.start()

    history_thread.start()


@app.on_event("startup")
def startup_event():

    start_background_collectors()


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {

        "status": "ok",

        "message":
            "Shkar Bourse API is running",

        "version":
            "11.0.0",

        "source":
            "tindex.app",

        "market_start":
            "09:00",

        "market_end":
            "12:30",

        "first_request_after_seconds":
            REQUEST_INTERVAL,

        "minimum_request_interval":
            REQUEST_INTERVAL,

        "daily_limit":
            DAILY_LIMIT,

        "market_cycles_before_history":
            MARKET_CYCLES_BEFORE_HISTORY,

        "history_range":
            HISTORY_RANGE
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {

        "status":
            "healthy",

        "source":
            "tindex.app",

        "version":
            "11.0.0",

        "market_mode":
            current_market_mode(),

        "market_open":
            is_market_open(),

        "market_start":
            "09:00",

        "market_end":
            "12:30",


        "market_collecting":
            _market_collecting,

        "market_complete":
            _market_complete,

        "market_cycles_completed":
            _market_cycles_completed,

        "current_page":
            _market_page,

        "last_page":
            _market_last_page,

        "total_symbols":
            _market_total_symbols,

        "cached_stocks":
            (
                len(_full_market_cache)
                if isinstance(
                    _full_market_cache,
                    list
                )
                else 0
            ),


        "history_started":
            _history_started,

        "history_complete":
            _history_complete,

        "history_queue_remaining":
            len(_history_queue),

        "history_total_requested":
            _history_total_requested,

        "history_total_completed":
            _history_total_completed,

        "history_cached_symbols":
            len(_history_results),


        "daily_requests_used":
            daily_requests_used(),

        "daily_requests_remaining":
            daily_requests_remaining(),

        "minimum_request_interval":
            REQUEST_INTERVAL,

        "seconds_until_next_request":
            seconds_until_next_request(),

        "seconds_until_market_start":
            seconds_until_market_start(),

        "last_error":
            _last_error
    }


# =========================================================
# MARKET
# =========================================================

@app.get("/market")
def market():

    return get_overview()


# =========================================================
# FULL MARKET
# =========================================================

@app.get("/full-market")
def full_market():

    if _full_market_cache is None:

        return {

            "status":
                "warming_up",

            "source":
                "tindex.app",

            "message":
                "دریافت کل بازار در پس‌زمینه در حال انجام است.",

            "market_mode":
                current_market_mode(),

            "market_open":
                is_market_open(),

            "market_cycles_completed":
                _market_cycles_completed,

            "current_page":
                _market_page,

            "last_page":
                _market_last_page,

            "total_symbols":
                _market_total_symbols,

            "cached_stocks":
                0,

            "daily_requests_used":
                daily_requests_used(),

            "daily_requests_remaining":
                daily_requests_remaining(),

            "seconds_until_next_request":
                seconds_until_next_request()
        }


    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "cached":
            True,

        "count":
            len(_full_market_cache),

        "stocks":
            _full_market_cache,

        "market_complete":
            _market_complete,

        "market_cycles_completed":
            _market_cycles_completed,

        "current_page":
            _market_page,

        "last_page":
            _market_last_page,

        "total_symbols":
            _market_total_symbols,

        "daily_requests_used":
            daily_requests_used(),

        "daily_requests_remaining":
            daily_requests_remaining()
    }


# =========================================================
# FULL ANALYSIS
# =========================================================

@app.get("/full-analysis")
def full_analysis():

    if _full_market_cache is None:

        return {

            "status":
                "warming_up",

            "source":
                "tindex.app",

            "message":
                "داده کامل بازار هنوز آماده نیست.",

            "market_cycles_completed":
                _market_cycles_completed,

            "current_page":
                _market_page,

            "last_page":
                _market_last_page,

            "cached_stocks":
                0,

            "daily_requests_used":
                daily_requests_used(),

            "daily_requests_remaining":
                daily_requests_remaining()
        }


    analysis = analyze_full_market(
        _full_market_cache
    )


    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "market_mode":
            current_market_mode(),

        "market_open":
            is_market_open(),

        "market_cycles_completed":
            _market_cycles_completed,

        "market_complete":
            _market_complete,

        "cached":
            True,

        "count":
            len(_full_market_cache),

        "analysis":
            analysis,

        "history": {

            "started":
                _history_started,

            "complete":
                _history_complete,

            "total_requested":
                _history_total_requested,

            "total_completed":
                _history_total_completed,

            "cached_symbols":
                len(_history_results)
        },

        "warning":
            "این رتبه‌بندی نسخه اولیه موتور تحلیل است و به معنی تضمین سود نیست.",

        "daily_requests_used":
            daily_requests_used(),

        "daily_requests_remaining":
            daily_requests_remaining()
    }


# =========================================================
# SHORT TERM
# =========================================================

@app.get("/short-term-opportunities")
def short_term_opportunities():

    if _full_market_cache is None:

        return {

            "status":
                "warming_up",

            "message":
                "بازار هنوز در حال دریافت است.",

            "market_cycles_completed":
                _market_cycles_completed,

            "cached_stocks":
                0
        }


    analysis = analyze_full_market(
        _full_market_cache
    )


    opportunities = []


    for rank, stock in enumerate(
        analysis["short_term_top_20"][:10],
        start=1
    ):

        opportunities.append({

            "rank":
                rank,

            "score":
                stock["score"],

            "ticker":
                stock["ticker"],

            "name":
                stock["name"],

            "sector":
                stock["sector"],

            "current_price":
                stock["current_price"],

            "change_percent":
                stock["change_percent"],

            "trade_value":
                stock["trade_value"],

            "market_cap":
                stock["market_cap"],

            "pe":
                stock["pe"],

            "reasons":
                stock["reasons"]
        })


    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "section":
            "short_term_opportunities",

        "title":
            "۱۰ فرصت برتر کوتاه‌مدت",

        "count":
            len(opportunities),

        "opportunities":
            opportunities
    }


# =========================================================
# SIX MONTH
# =========================================================

@app.get("/six-month-opportunities")
def six_month_opportunities():

    if _full_market_cache is None:

        return {

            "status":
                "warming_up",

            "message":
                "بازار هنوز در حال دریافت است.",

            "market_cycles_completed":
                _market_cycles_completed,

            "cached_stocks":
                0
        }


    analysis = analyze_full_market(
        _full_market_cache
    )


    opportunities = []


    for rank, stock in enumerate(
        analysis["six_month_top_20"][:10],
        start=1
    ):

        opportunities.append({

            "rank":
                rank,

            "score":
                stock["score"],

            "ticker":
                stock["ticker"],

            "name":
                stock["name"],

            "sector":
                stock["sector"],

            "current_price":
                stock["current_price"],

            "change_percent":
                stock["change_percent"],

            "trade_value":
                stock["trade_value"],

            "market_cap":
                stock["market_cap"],

            "pe":
                stock["pe"],

            "reasons":
                stock["reasons"]
        })


    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "section":
            "six_month_opportunities",

        "title":
            "۱۰ فرصت برتر ۶ ماهه",

        "count":
            len(opportunities),

        "opportunities":
            opportunities
    }


# =========================================================
# HISTORY STATUS
# =========================================================

@app.get("/history/status")
def history_status():

    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "market_cycles_completed":
            _market_cycles_completed,

        "history_started":
            _history_started,

        "history_complete":
            _history_complete,

        "history_range":
            HISTORY_RANGE,

        "history_total_requested":
            _history_total_requested,

        "history_total_completed":
            _history_total_completed,

        "history_queue_remaining":
            len(_history_queue),

        "history_cached_symbols":
            len(_history_results),

        "daily_requests_used":
            daily_requests_used(),

        "daily_requests_remaining":
            daily_requests_remaining(),

        "seconds_until_next_request":
            seconds_until_next_request(),

        "last_error":
            _last_error
    }


# =========================================================
# HISTORY
# =========================================================

@app.get("/history")
def history():

    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "history_range":
            HISTORY_RANGE,

        "count":
            len(_history_results),

        "market_cycles_completed":
            _market_cycles_completed,

        "history_complete":
            _history_complete,

        "symbols":
            list(
                _history_results.values()
            ),

        "daily_requests_used":
            daily_requests_used(),

        "daily_requests_remaining":
            daily_requests_remaining()
    }


# =========================================================
# SINGLE HISTORY
# =========================================================

@app.get("/history/{slug}")
def single_history(
    slug: str
):

    item = _history_results.get(
        slug
    )


    if item is None:

        return {

            "status":
                "not_found",

            "source":
                "local",

            "message":
                "تاریخچه این نماد هنوز دریافت نشده است.",

            "slug":
                slug,

            "history_complete":
                _history_complete
        }


    return {

        "status":
            "ok",

        "source":
            "local",

        "data":
            item
    }


# =========================================================
# SCANNER
# =========================================================

@app.get("/scanner/step")
def scanner_step():

    if _full_market_cache is None:

        return {

            "status":
                "warming_up",

            "message":
                "اسکن بازار هنوز آماده نیست.",

            "current_page":
                _market_page,

            "cached_stocks":
                0
        }


    analysis = analyze_full_market(
        _full_market_cache
    )


    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "message":
            "اسکن کامل بازار با موفقیت انجام شد.",

        "total_stocks":
            len(_full_market_cache),

        "market_cycles_completed":
            _market_cycles_completed,

        "top_gainers":
            analysis["top_gainers"][:10],

        "top_losers":
            analysis["top_losers"][:10],

        "most_active":
            analysis["most_active"][:10],

        "market_complete":
            _market_complete,

        "daily_requests_used":
            daily_requests_used(),

        "daily_requests_remaining":
            daily_requests_remaining(),

        "minimum_request_interval":
            REQUEST_INTERVAL
    }
