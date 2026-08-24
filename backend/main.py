import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from tsetmc import (
    DAILY_LIMIT,
    REQUEST_INTERVAL,
    MARKET_START_HOUR,
    MARKET_START_MINUTE,
    MARKET_END_HOUR,
    MARKET_END_MINUTE,
    STOCKS_URL,
    make_tindex_request,
    daily_requests_used,
    daily_requests_remaining,
    seconds_until_next_request,
)


app = FastAPI(
    title="Shkar Bourse API",
    version="10.0.0"
)


# =========================================================
# SETTINGS
# =========================================================

PER_PAGE = 100

# طبق چیزی که مشخص کردیم:
# تعداد صفحات لازم برای تکمیل بازار
EXPECTED_MARKET_PAGES = 17

MAX_PAGES = 5000

# Cache فقط برای نگهداری آخرین داده دریافت‌شده است.
# درخواست‌ها برای روز بعد ذخیره نمی‌شوند.
FULL_MARKET_CACHE_SECONDS = 3600

OVERVIEW_CACHE_SECONDS = 75


# =========================================================
# GLOBAL STATE
# =========================================================

_cache_data = None
_cache_time = 0.0

_full_market_cache = None
_full_market_cache_time = 0.0

_market_page = 1
_market_last_page = None

_market_collecting = False
_market_complete = False

_market_started_at = None
_market_completed_at = None

_market_buffer = []

_background_thread_started = False

_last_error = None

_state_lock = threading.Lock()


# =========================================================
# TIME
# =========================================================

def tehran_now():

    return datetime.now(
        ZoneInfo("Asia/Tehran")
    )


def is_trading_day():

    return tehran_now().weekday() in (
        5,
        6,
        0,
        1,
        2
    )


def market_start_datetime():

    now = tehran_now()

    return now.replace(
        hour=MARKET_START_HOUR,
        minute=MARKET_START_MINUTE,
        second=0,
        microsecond=0
    )


def market_end_datetime():

    now = tehran_now()

    return now.replace(
        hour=MARKET_END_HOUR,
        minute=MARKET_END_MINUTE,
        second=0,
        microsecond=0
    )


def first_request_datetime():

    return (
        market_start_datetime()
        + __import__("datetime").timedelta(
            seconds=REQUEST_INTERVAL
        )
    )


def is_market_open():

    if not is_trading_day():
        return False

    now = tehran_now()

    return (
        market_start_datetime()
        <= now
        <= market_end_datetime()
    )


def current_market_mode():

    if is_market_open():
        return "active"

    return "inactive"


def seconds_until_market_start():

    if not is_trading_day():
        return 0

    now = tehran_now()

    start = market_start_datetime()

    if now >= start:
        return 0

    return max(
        0,
        int(
            (start - now).total_seconds()
        )
    )


def seconds_until_first_request():

    if not is_trading_day():
        return 0

    now = tehran_now()

    target = first_request_datetime()

    if now >= target:
        return 0

    return max(
        0,
        int(
            (target - now).total_seconds()
        )
    )


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
            "data": _cache_data,
            "daily_requests_used": (
                daily_requests_used()
            ),
            "daily_requests_remaining": (
                daily_requests_remaining()
            )
        }

    from tsetmc import OVERVIEW_URL

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
        "data": _cache_data,
        "daily_requests_used": (
            daily_requests_used()
        ),
        "daily_requests_remaining": (
            daily_requests_remaining()
        )
    }


# =========================================================
# FULL MARKET COLLECTOR
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
    global _last_error

    while True:

        try:

            # ---------------------------------------------
            # روز غیر معاملاتی
            # ---------------------------------------------

            if not is_trading_day():

                time.sleep(30)
                continue


            # ---------------------------------------------
            # قبل از شروع بازار
            # ---------------------------------------------

            if not is_market_open():

                wait = seconds_until_market_start()

                if wait > 0:

                    time.sleep(
                        min(
                            30,
                            max(
                                1,
                                wait
                            )
                        )
                    )

                else:

                    time.sleep(30)

                continue


            # ---------------------------------------------
            # سقف روزانه
            # ---------------------------------------------

            if daily_requests_used() >= DAILY_LIMIT:

                time.sleep(30)
                continue


            # ---------------------------------------------
            # اولین درخواست:
            # 75 ثانیه بعد از 09:00
            # درخواست‌های بعدی:
            # هر 75 ثانیه
            # ---------------------------------------------

            wait = seconds_until_next_request()

            if wait > 0:

                time.sleep(
                    min(
                        30,
                        max(
                            1,
                            wait
                        )
                    )
                )

                continue


            # ---------------------------------------------
            # شروع سیکل جمع‌آوری
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


            page = _market_page


            # ---------------------------------------------
            # درخواست صفحه
            # ---------------------------------------------

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

                _last_error = result.get(
                    "message"
                )

                _market_collecting = False

                time.sleep(30)

                continue


            data = result.get(
                "data"
            )


            if not isinstance(
                data,
                dict
            ):

                _last_error = (
                    "ساختار data بازار معتبر نیست."
                )

                _market_collecting = False

                time.sleep(30)

                continue


            # ---------------------------------------------
            # Rows
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
            # تشخیص آخرین صفحه
            # ---------------------------------------------

            last_page = meta.get(
                "last_page"
            )

            if last_page is not None:

                try:

                    _market_last_page = int(
                        last_page
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    _market_last_page = None


            has_more = meta.get(
                "has_more"
            )


            # ---------------------------------------------
            # اگر API تعداد صفحات را نداد،
            # بر اساس 17 صفحه‌ای که مشخص کردیم
            # عمل می‌کنیم.
            # ---------------------------------------------

            if has_more is None:

                if _market_last_page is not None:

                    has_more = (
                        page
                        < _market_last_page
                    )

                else:

                    has_more = (
                        page
                        < EXPECTED_MARKET_PAGES
                    )


            # ---------------------------------------------
            # پایان جمع‌آوری
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

                _market_page = 1

                _market_buffer = []

                _last_error = None

                # درخواست بعدی در صورت وجود سهمیه،
                # خودش بعد از 75 ثانیه انجام خواهد شد.

                continue


            # ---------------------------------------------
            # صفحه بعد
            # ---------------------------------------------

            _market_page += 1

        except Exception as exc:

            _last_error = str(
                exc
            )

            _market_collecting = False

            time.sleep(30)


# =========================================================
# START BACKGROUND
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


def analyze_full_market(stocks):

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

        "version": "10.0.0",

        "source": "tindex.app",

        "market_start": "09:00",

        "first_request": "09:01:15",

        "market_end": "12:30",

        "minimum_request_interval": (
            REQUEST_INTERVAL
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

        "version": "10.0.0",

        "market_mode": (
            current_market_mode()
        ),

        "market_open": (
            is_market_open()
        ),

        "market_start": "09:00",

        "first_request": "09:01:15",

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

        "expected_market_pages": (
            EXPECTED_MARKET_PAGES
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
            REQUEST_INTERVAL
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

    if _full_market_cache is None:

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

    if _full_market_cache is None:

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

    if _full_market_cache is None:

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

    if _full_market_cache is None:

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

    if _full_market_cache is None:

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
            REQUEST_INTERVAL
        )
    }
