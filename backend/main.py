import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from fastapi import FastAPI


app = FastAPI(
    title="Shkar Bourse API",
    version="9.0.0"
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


# =========================================================
# SETTINGS
# =========================================================

DAILY_LIMIT = 100

# حداقل فاصله بین دو درخواست واقعی
MIN_REQUEST_INTERVAL = 75

# اولین ساعت مجاز برای شروع جمع‌آوری
MARKET_START_HOUR = 9
MARKET_START_MINUTE = 0

# پایان تقریبی بازار
MARKET_END_HOUR = 12
MARKET_END_MINUTE = 30

# تعداد سهم در هر صفحه
PER_PAGE = 100

# حداکثر صفحات
MAX_PAGES = 5000

# اعتبار Cache بازار
FULL_MARKET_CACHE_SECONDS = 3600

# اعتبار Cache Overview
OVERVIEW_CACHE_SECONDS = 75


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

_market_collecting = False
_market_complete = False

_market_started_at = None
_market_completed_at = None

_market_buffer = []

_background_thread_started = False

_state_lock = threading.Lock()


# =========================================================
# TIME HELPERS
# =========================================================

def tehran_now():
    return datetime.now(
        ZoneInfo("Asia/Tehran")
    )


def is_trading_day():
    """
    شنبه تا چهارشنبه
    """

    now = tehran_now()

    # Monday=0
    # Tuesday=1
    # Wednesday=2
    # Thursday=3
    # Friday=4
    # Saturday=5
    # Sunday=6

    return now.weekday() in [
        5,
        6,
        0,
        1,
        2
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
    """
    بازه فعالیت بازار:
    09:00 تا 12:30
    شنبه تا چهارشنبه
    """

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


def seconds_until_market_start():
    """
    چند ثانیه تا ساعت 09:00 تهران باقی مانده.
    """

    now = tehran_now()

    if is_trading_day():

        start = now.replace(
            hour=MARKET_START_HOUR,
            minute=MARKET_START_MINUTE,
            second=0,
            microsecond=0
        )

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

    cutoff = time.time() - 86400

    with _state_lock:

        _daily_requests = [
            timestamp
            for timestamp in _daily_requests
            if timestamp > cutoff
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


# =========================================================
# REQUEST TIMING
# =========================================================

def seconds_until_next_request():

    with _state_lock:
        last_request = _last_request_time

    if last_request <= 0:
        return 0

    elapsed = (
        time.time()
        - last_request
    )

    remaining = (
        MIN_REQUEST_INTERVAL
        - elapsed
    )

    if remaining <= 0:
        return 0

    return int(
        remaining
    ) + 1


def can_request_tindex():

    cleanup_daily_requests()

    # فقط در زمان بازار
    if not is_market_open():
        return (
            False,
            "در حال حاضر خارج از زمان جمع‌آوری بازار است."
        )

    # سقف روزانه
    if daily_requests_used() >= DAILY_LIMIT:
        return (
            False,
            "سقف 100 درخواست روزانه مصرف شده است."
        )

    # فاصله 75 ثانیه
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
        "Authorization": (
            f"Bearer {token}"
        ),
        "Accept": "application/json",
        "User-Agent": (
            "ShkarBoursePro2/9.0"
        )
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

        return float(
            value
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
    global _daily_requests

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
            "wait_seconds": (
                seconds_until_next_request()
            ),
            "daily_requests_used": (
                daily_requests_used()
            ),
            "daily_requests_remaining": (
                daily_requests_remaining()
            )
        }

    request_time = time.time()

    with _state_lock:

        _daily_requests.append(
            request_time
        )

        _last_request_time = (
            request_time
        )

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
                "daily_requests_used": (
                    daily_requests_used()
                ),
                "daily_requests_remaining": (
                    daily_requests_remaining()
                )
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

        _last_error = str(
            exc
        )

        return {
            "status": "error",
            "source": "tindex.app",
            "message": (
                "خطا در اتصال به TIndex: "
                + str(exc)
            )
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
        and now - _cache_time
        < OVERVIEW_CACHE_SECONDS
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
# BACKGROUND FULL MARKET COLLECTOR
# =========================================================

def collect_market_background():

    global _full_market_cache
    global _full_market_cache_time

    global _market_page
    global _market_last_page
    global _market_collecting
    global _market_complete
    global _market_started_at
    global _market_completed_at
    global _market_buffer

    while True:

        try:

            # ---------------------------------------------
            # خارج از روز معاملاتی
            # ---------------------------------------------

            if not is_trading_day():

                time.sleep(30)

                continue


            # ---------------------------------------------
            # قبل از ساعت 09:00
            # ---------------------------------------------

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

                    # بعد از 12:30
                    time.sleep(30)

                continue


            # ---------------------------------------------
            # سقف 100 درخواست
            # ---------------------------------------------

            if daily_requests_used() >= DAILY_LIMIT:

                time.sleep(30)

                continue


            # ---------------------------------------------
            # فاصله 75 ثانیه
            # ---------------------------------------------

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


            # ---------------------------------------------
            # شروع یک سیکل جدید بازار
            # ---------------------------------------------

            if not _market_collecting:

                _market_collecting = True

                _market_complete = False

                _market_page = 1

                _market_last_page = None

                _market_buffer = []

                _market_started_at = (
                    time.time()
                )


            # ---------------------------------------------
            # درخواست صفحه فعلی
            # ---------------------------------------------

            page = _market_page

            result = make_tindex_request(

                STOCKS_URL,

                params={
                    "page": page,
                    "per_page": PER_PAGE
                }
            )


            # ---------------------------------------------
            # خطا
            # ---------------------------------------------

            if result["status"] != "ok":

                _market_collecting = False

                time.sleep(30)

                continue


            # ---------------------------------------------
            # دریافت data
            # ---------------------------------------------

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


            # ---------------------------------------------
            # ذخیره سهم‌ها
            # ---------------------------------------------

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


            # ---------------------------------------------
            # Meta
            # ---------------------------------------------

            meta = result.get(
                "meta"
            )

            if not isinstance(
                meta,
                dict
            ):

                meta = {}


            # ---------------------------------------------
            # Last Page
            # ---------------------------------------------

            try:

                _market_last_page = int(
                    safe_number(
                        meta.get(
                            "last_page"
                        ),
                        page
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                _market_last_page = page


            # ---------------------------------------------
            # Has More
            # ---------------------------------------------

            has_more = meta.get(
                "has_more"
            )

            if has_more is None:

                has_more = (
                    page
                    < _market_last_page
                )


            # ---------------------------------------------
            # آخرین صفحه
            # ---------------------------------------------

            if (
                not has_more
                or page >= MAX_PAGES
            ):

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

                # -----------------------------------------
                # مهم:
                # بعد از تکمیل بازار، سیکل بعدی دوباره
                # از صفحه 1 شروع می‌شود.
                # درخواست بعدی همچنان باید 75 ثانیه
                # فاصله داشته باشد.
                # -----------------------------------------

                _market_page = 1

                _market_buffer = []

                continue


            # ---------------------------------------------
            # رفتن به صفحه بعد
            # ---------------------------------------------

            _market_page += 1

            # نیازی به sleep یک ثانیه نیست.
            # حلقه بعدی خودش 75 ثانیه را کنترل می‌کند.

        except Exception as exc:

            _last_error = str(
                exc
            )

            _market_collecting = False

            time.sleep(30)


# =========================================================
# START BACKGROUND THREAD
# =========================================================

def start_background_collector():

    global _background_thread_started

    if _background_thread_started:
        return

    _background_thread_started = True

    thread = threading.Thread(
        target=collect_market_background,
        daemon=True
    )

    thread.start()


@app.on_event(
    "startup"
)
def startup_event():

    start_background_collector()


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
        stock.get(
            "ticker"
        )
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

        "slug": stock.get(
            "slug"
        ),

        "ticker": stock.get(
            "ticker"
        ),

        "name": stock.get(
            "name"
        ),

        "sector": stock.get(
            "sector"
        ),

        "current_price": stock.get(
            "last_price",
            stock.get(
                "current_price"
            )
        ),

        "closing_price": stock.get(
            "closing_price"
        ),

        "change_percent": stock.get(
            "change",
            stock.get(
                "change_percent"
            )
        ),

        "closing_change_percent": (
            stock.get(
                "closing_change"
            )
        ),

        "volume": stock.get(
            "volume"
        ),

        "trade_value": stock.get(
            "value",
            stock.get(
                "trade_value"
            )
        ),

        "market_cap": stock.get(
            "market_cap"
        ),

        "pe": stock.get(
            "pe"
        ),

        "updated_at": stock.get(
            "updated_at"
        ),

        "score": calculate_score(
            stock
        ),

        "reasons": build_reasons(
            stock
        )
    }


def analyze_full_market(
    stocks
):

    candidates = []

    for stock in stocks:

        if not is_valid_stock(
            stock
        ):
            continue

        candidates.append(
            normalize_stock(
                stock
            )
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

        "candidate_count": len(
            candidates
        ),

        "short_term_top_20": (
            short_term[:20]
        ),

        "six_month_top_20": (
            six_month[:20]
        ),

        "top_gainers": (
            gainers[:20]
        ),

        "top_losers": (
            losers[:20]
        ),

        "most_active": (
            most_active[:20]
        )
    }


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {

        "status": "ok",

        "message": (
            "Shkar Bourse API is running"
        ),

        "version": "9.0.0",

        "source": "tindex.app",

        "market_start": "09:00",

        "market_end": "12:30",

        "minimum_request_interval": (
            MIN_REQUEST_INTERVAL
        ),

        "daily_limit": DAILY_LIMIT
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {

        "status": "healthy",

        "source": "tindex.app",

        "version": "9.0.0",

        "market_mode": (
            current_market_mode()
        ),

        "market_open": (
            is_market_open()
        ),

        "market_start": "09:00",

        "market_end": "12:30",

        "market_collecting": (
            _market_collecting
        ),

        "market_complete": (
            _market_complete
        ),

        "current_page": (
            _market_page
        ),

        "last_page": (
            _market_last_page
        ),

        "cached_stocks": (

            len(
                _full_market_cache
            )

            if isinstance(
                _full_market_cache,
                list
            )

            else 0
        ),

        "daily_requests_used": (
            daily_requests_used()
        ),

        "daily_requests_remaining": (
            daily_requests_remaining()
        ),

        "minimum_request_interval": (
            MIN_REQUEST_INTERVAL
        ),

        "seconds_until_next_request": (
            seconds_until_next_request()
        ),

        "seconds_until_market_start": (
            seconds_until_market_start()
        ),

        "last_error": _last_error
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

    if (
        _full_market_cache is None
    ):

        return {

            "status": "warming_up",

            "source": "tindex.app",

            "message": (
                "دریافت کل بازار در پس‌زمینه "
                "در حال انجام است."
            ),

            "market_mode": (
                current_market_mode()
            ),

            "market_open": (
                is_market_open()
            ),

            "current_page": (
                _market_page
            ),

            "last_page": (
                _market_last_page
            ),

            "cached_stocks": 0,

            "daily_requests_used": (
                daily_requests_used()
            ),

            "daily_requests_remaining": (
                daily_requests_remaining()
            ),

            "seconds_until_next_request": (
                seconds_until_next_request()
            )
        }


    return {

        "status": "ok",

        "source": "tindex.app",

        "cached": True,

        "count": len(
            _full_market_cache
        ),

        "stocks": _full_market_cache,

        "market_complete": (
            _market_complete
        ),

        "current_page": (
            _market_page
        ),

        "last_page": (
            _market_last_page
        ),

        "daily_requests_used": (
            daily_requests_used()
        ),

        "daily_requests_remaining": (
            daily_requests_remaining()
        )
    }


# =========================================================
# FULL ANALYSIS
# =========================================================

@app.get("/full-analysis")
def full_analysis():

    if (
        _full_market_cache is None
    ):

        return {

            "status": "warming_up",

            "source": "tindex.app",

            "message": (
                "داده کامل بازار هنوز آماده نیست. "
                "دریافت بازار در پس‌زمینه ادامه دارد."
            ),

            "market_mode": (
                current_market_mode()
            ),

            "market_open": (
                is_market_open()
            ),

            "current_page": (
                _market_page
            ),

            "last_page": (
                _market_last_page
            ),

            "cached_stocks": 0,

            "daily_requests_used": (
                daily_requests_used()
            ),

            "daily_requests_remaining": (
                daily_requests_remaining()
            ),

            "seconds_until_next_request": (
                seconds_until_next_request()
            )
        }


    analysis = analyze_full_market(
        _full_market_cache
    )


    return {

        "status": "ok",

        "source": "tindex.app",

        "market_mode": (
            current_market_mode()
        ),

        "market_open": (
            is_market_open()
        ),

        "market_complete": (
            _market_complete
        ),

        "cached": True,

        "count": len(
            _full_market_cache
        ),

        "analysis": analysis,

        "warning": (
            "این رتبه‌بندی نسخه اولیه "
            "موتور تحلیل است و به معنی "
            "تضمین سود نیست."
        ),

        "daily_requests_used": (
            daily_requests_used()
        ),

        "daily_requests_remaining": (
            daily_requests_remaining()
        )
    }


# =========================================================
# SHORT TERM
# =========================================================

@app.get(
    "/short-term-opportunities"
)
def short_term_opportunities():

    if (
        _full_market_cache is None
    ):

        return {

            "status": "warming_up",

            "message": (
                "بازار هنوز در حال دریافت است."
            ),

            "current_page": (
                _market_page
            ),

            "cached_stocks": 0
        }


    analysis = analyze_full_market(
        _full_market_cache
    )

    opportunities = []


    for rank, stock in enumerate(

        analysis[
            "short_term_top_20"
        ][:10],

        start=1
    ):

        opportunities.append({

            "rank": rank,

            "score": stock[
                "score"
            ],

            "ticker": stock[
                "ticker"
            ],

            "name": stock[
                "name"
            ],

            "sector": stock[
                "sector"
            ],

            "current_price": stock[
                "current_price"
            ],

            "change_percent": stock[
                "change_percent"
            ],

            "trade_value": stock[
                "trade_value"
            ],

            "market_cap": stock[
                "market_cap"
            ],

            "pe": stock[
                "pe"
            ],

            "reasons": stock[
                "reasons"
            ]
        })


    return {

        "status": "ok",

        "source": "tindex.app",

        "section": (
            "short_term_opportunities"
        ),

        "title": (
            "۱۰ فرصت برتر کوتاه‌مدت"
        ),

        "count": len(
            opportunities
        ),

        "opportunities": opportunities
    }


# =========================================================
# SIX MONTH
# =========================================================

@app.get(
    "/six-month-opportunities"
)
def six_month_opportunities():

    if (
        _full_market_cache is None
    ):

        return {

            "status": "warming_up",

            "message": (
                "بازار هنوز در حال دریافت است."
            ),

            "current_page": (
                _market_page
            ),

            "cached_stocks": 0
        }


    analysis = analyze_full_market(
        _full_market_cache
    )

    opportunities = []


    for rank, stock in enumerate(

        analysis[
            "six_month_top_20"
        ][:10],

        start=1
    ):

        opportunities.append({

            "rank": rank,

            "score": stock[
                "score"
            ],

            "ticker": stock[
                "ticker"
            ],

            "name": stock[
                "name"
            ],

            "sector": stock[
                "sector"
            ],

            "current_price": stock[
                "current_price"
            ],

            "change_percent": stock[
                "change_percent"
            ],

            "trade_value": stock[
                "trade_value"
            ],

            "market_cap": stock[
                "market_cap"
            ],

            "pe": stock[
                "pe"
            ],

            "reasons": stock[
                "reasons"
            ]
        })


    return {

        "status": "ok",

        "source": "tindex.app",

        "section": (
            "six_month_opportunities"
        ),

        "title": (
            "۱۰ فرصت برتر ۶ ماهه"
        ),

        "count": len(
            opportunities
        ),

        "opportunities": opportunities
    }


# =========================================================
# SCANNER
# =========================================================

@app.get(
    "/scanner/step"
)
def scanner_step():

    if (
        _full_market_cache is None
    ):

        return {

            "status": "warming_up",

            "message": (
                "اسکن بازار هنوز آماده نیست."
            ),

            "current_page": (
                _market_page
            ),

            "cached_stocks": 0
        }


    stocks = _full_market_cache

    analysis = analyze_full_market(
        stocks
    )


    return {

        "status": "ok",

        "source": "tindex.app",

        "message": (
            "اسکن کامل بازار "
            "با موفقیت انجام شد."
        ),

        "total_stocks": len(
            stocks
        ),

        "top_gainers": (
            analysis[
                "top_gainers"
            ][:10]
        ),

        "top_losers": (
            analysis[
                "top_losers"
            ][:10]
        ),

        "most_active": (
            analysis[
                "most_active"
            ][:10]
        ),

        "market_complete": (
            _market_complete
        ),

        "daily_requests_used": (
            daily_requests_used()
        ),

        "daily_requests_remaining": (
            daily_requests_remaining()
        ),

        "minimum_request_interval": (
            MIN_REQUEST_INTERVAL
        )
    }
