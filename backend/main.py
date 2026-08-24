import os
import time
import threading
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

import requests
from fastapi import FastAPI


app = FastAPI(
    title="Shkar Bourse API",
    version="7.0.0"
)


# =========================================================
# TINDEX
# =========================================================

TINDEX_BASE_URL = "https://tindex.app/api/public"

OVERVIEW_URL = (
    f"{TINDEX_BASE_URL}/stock-market/overview"
)


# =========================================================
# SETTINGS
# =========================================================

DAILY_LIMIT = 100

# زمان بین درخواست‌های TIndex
# بازار باز: حدود 130 ثانیه
MARKET_REQUEST_INTERVAL = 130

# خارج از زمان بازار: 15 دقیقه
OFF_MARKET_REQUEST_INTERVAL = 900

REQUEST_TIMEOUT = 30

TEHRAN_TZ = ZoneInfo("Asia/Tehran")


# =========================================================
# CACHE
# =========================================================

_cache_data = None
_cache_time = 0.0

_last_request_time = 0.0
_next_request_time = 0.0

_daily_requests = []

_last_error = None
_last_success_time = None

_request_lock = threading.Lock()


# =========================================================
# TIME
# =========================================================

def now_tehran():
    return datetime.now(TEHRAN_TZ)


def is_market_open():
    """
    ساعات تقریبی بازار بورس تهران:
    09:00 تا 12:30
    """

    current = now_tehran().time()

    market_start = dt_time(9, 0)
    market_end = dt_time(12, 30)

    return market_start <= current <= market_end


def get_request_interval():
    if is_market_open():
        return MARKET_REQUEST_INTERVAL

    return OFF_MARKET_REQUEST_INTERVAL


def seconds_until_next_request():
    if _last_request_time <= 0:
        return 0

    remaining = (
        _last_request_time
        + get_request_interval()
        - time.time()
    )

    return max(0, int(remaining))


# =========================================================
# DAILY LIMIT
# =========================================================

def cleanup_daily_requests():
    global _daily_requests

    cutoff = time.time() - 86400

    _daily_requests = [
        timestamp
        for timestamp in _daily_requests
        if timestamp > cutoff
    ]


def daily_requests_used():
    cleanup_daily_requests()
    return len(_daily_requests)


def daily_requests_remaining():
    return max(
        0,
        DAILY_LIMIT - daily_requests_used()
    )


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
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ShkarBoursePro2/7.0"
    }


# =========================================================
# HELPERS
# =========================================================

def safe_number(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default

        return int(float(value))

    except (TypeError, ValueError):
        return default


# =========================================================
# TINDEX REQUEST
# =========================================================

def make_tindex_request(force=False):
    global _last_error
    global _last_request_time
    global _next_request_time
    global _last_success_time

    with _request_lock:

        # -------------------------------------------------
        # اگر کش معتبر داریم، اصلاً TIndex را صدا نزن
        # -------------------------------------------------

        if (
            not force
            and _cache_data is not None
            and _last_request_time > 0
            and time.time() - _last_request_time
            < get_request_interval()
        ):
            return {
                "status": "ok",
                "source": "tindex.app",
                "cached": True,
                "data": _cache_data
            }

        # -------------------------------------------------
        # بررسی فاصله اجباری بین درخواست‌ها
        # -------------------------------------------------

        if (
            _last_request_time > 0
            and time.time() - _last_request_time
            < get_request_interval()
        ):
            remaining = seconds_until_next_request()

            return {
                "status": "ok",
                "source": "local-cache",
                "cached": True,
                "data": _cache_data,
                "message": (
                    f"درخواست بعدی TIndex حدود "
                    f"{remaining} ثانیه دیگر انجام می‌شود."
                ),
                "seconds_until_next_request": remaining
            }

        # -------------------------------------------------
        # توکن
        # -------------------------------------------------

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

        # -------------------------------------------------
        # سقف روزانه
        # -------------------------------------------------

        cleanup_daily_requests()

        if len(_daily_requests) >= DAILY_LIMIT:

            _last_error = (
                "سقف 100 درخواست در 24 ساعت مصرف شده است."
            )

            return {
                "status": "error",
                "source": "local-rate-limit",
                "message": _last_error,
                "daily_requests_used": (
                    daily_requests_used()
                ),
                "daily_requests_remaining": (
                    daily_requests_remaining()
                )
            }

        # -------------------------------------------------
        # ثبت درخواست
        # -------------------------------------------------

        request_timestamp = time.time()

        _daily_requests.append(
            request_timestamp
        )

        _last_request_time = request_timestamp

        _next_request_time = (
            request_timestamp
            + get_request_interval()
        )

        # -------------------------------------------------
        # درخواست فقط به Overview
        # -------------------------------------------------

        try:

            response = requests.get(
                OVERVIEW_URL,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )

            # ---------------------------------------------
            # Unauthorized
            # ---------------------------------------------

            if response.status_code == 401:

                _last_error = (
                    "توکن TIndex معتبر نیست."
                )

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error
                }

            # ---------------------------------------------
            # Too Many Requests
            # ---------------------------------------------

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
                    ),
                    "retry_after_seconds": (
                        get_request_interval()
                    )
                }

            # ---------------------------------------------
            # سایر خطاهای HTTP
            # ---------------------------------------------

            response.raise_for_status()

            # ---------------------------------------------
            # JSON
            # ---------------------------------------------

            result = response.json()

            if not isinstance(result, dict):

                _last_error = (
                    "پاسخ TIndex ساختار معتبر ندارد."
                )

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error
                }

            # ---------------------------------------------
            # Success = false
            # ---------------------------------------------

            if result.get("success") is False:

                message = result.get(
                    "message",
                    "TIndex پاسخ موفقی ارسال نکرد."
                )

                _last_error = str(message)

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error
                }

            # ---------------------------------------------
            # Data
            # ---------------------------------------------

            data = result.get("data")

            if not isinstance(data, dict):

                _last_error = (
                    "ساختار data دریافتی از TIndex معتبر نیست."
                )

                return {
                    "status": "error",
                    "source": "tindex.app",
                    "message": _last_error
                }

            # ---------------------------------------------
            # ذخیره کش
            # ---------------------------------------------

            global _cache_data
            global _cache_time

            _cache_data = data
            _cache_time = time.time()

            _last_success_time = (
                now_tehran().isoformat()
            )

            _last_error = None

            return {
                "status": "ok",
                "source": "tindex.app",
                "cached": False,
                "data": data
            }

        except requests.exceptions.Timeout:

            _last_error = (
                "اتصال به TIndex بیش از "
                f"{REQUEST_TIMEOUT} ثانیه طول کشید."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
            }

        except requests.exceptions.RequestException as exc:

            _last_error = str(exc)

            return {
                "status": "error",
                "source": "tindex.app",
                "message": (
                    f"خطا در اتصال به TIndex: {str(exc)}"
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
# MARKET DATA
# =========================================================

def get_market_data(force=False):

    # اگر کش موجود است و زمانش نرسیده
    if (
        not force
        and _cache_data is not None
        and _last_request_time > 0
        and time.time() - _last_request_time
        < get_request_interval()
    ):
        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": True,
            "data": _cache_data
        }

    return make_tindex_request(
        force=force
    )


# =========================================================
# STOCK NORMALIZATION
# =========================================================

def normalize_stock(stock):

    return {
        "slug": stock.get("slug"),
        "ticker": stock.get("ticker"),
        "name": stock.get("name"),
        "sector": stock.get("sector"),
        "current_price": stock.get(
            "last_price"
        ),
        "change_percent": stock.get(
            "change_percent"
        ),
        "trade_value": stock.get(
            "trade_value"
        ),
        "trade_volume": stock.get(
            "trade_volume"
        ),
        "market_cap": stock.get(
            "market_cap"
        ),
        "pe": stock.get("pe")
    }


# =========================================================
# SCORE
# =========================================================

def calculate_score(stock):

    score = 0

    change = safe_number(
        stock.get("change_percent")
    )

    value = safe_number(
        stock.get("trade_value")
    )

    market_cap = safe_number(
        stock.get("market_cap")
    )

    pe = stock.get("pe")

    # ---------------------------------------------
    # Momentum
    # ---------------------------------------------

    if change >= 4:
        score += 25

    elif change >= 3:
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

    # ---------------------------------------------
    # Trade Value
    # ---------------------------------------------

    if value >= 20_000_000_000_000:
        score += 25

    elif value >= 10_000_000_000_000:
        score += 20

    elif value >= 5_000_000_000_000:
        score += 15

    elif value >= 1_000_000_000_000:
        score += 10

    elif value >= 100_000_000_000:
        score += 5

    # ---------------------------------------------
    # Market Cap
    # ---------------------------------------------

    if market_cap > 0:
        score += 5

    # ---------------------------------------------
    # P/E
    # ---------------------------------------------

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
        stock.get("change_percent")
    )

    value = safe_number(
        stock.get("trade_value")
    )

    pe = stock.get("pe")

    if change >= 3:
        reasons.append(
            "مومنتوم روزانه مثبت"
        )

    elif change > 0:
        reasons.append(
            "تغییر روزانه مثبت"
        )

    elif change <= -2:
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


def prepare_stock(stock):

    item = normalize_stock(
        stock
    )

    item["score"] = calculate_score(
        stock
    )

    item["reasons"] = build_reasons(
        stock
    )

    return item


# =========================================================
# ANALYSIS FROM TINDEX OVERVIEW
# =========================================================

def analyze_overview(data):

    boards = data.get(
        "boards",
        {}
    )

    if not isinstance(boards, dict):
        boards = {}

    gainers = boards.get(
        "gainers",
        []
    )

    losers = boards.get(
        "losers",
        []
    )

    most_active_value = boards.get(
        "most_active_value",
        []
    )

    most_active_volume = boards.get(
        "most_active_volume",
        []
    )

    # ---------------------------------------------
    # Combine all available symbols
    # ---------------------------------------------

    combined = {}

    for collection in [
        gainers,
        losers,
        most_active_value,
        most_active_volume
    ]:

        if not isinstance(collection, list):
            continue

        for stock in collection:

            if not isinstance(stock, dict):
                continue

            ticker = stock.get(
                "ticker"
            )

            if ticker:
                combined[ticker] = stock

    candidates = []

    for stock in combined.values():

        item = prepare_stock(
            stock
        )

        candidates.append(
            item
        )

    # ---------------------------------------------
    # Short term
    # ---------------------------------------------

    short_term = sorted(
        candidates,
        key=lambda x: (
            safe_number(
                x.get("score")
            ),
            safe_number(
                x.get("trade_value")
            ),
            safe_number(
                x.get("change_percent")
            )
        ),
        reverse=True
    )

    # ---------------------------------------------
    # Six month
    # ---------------------------------------------

    six_month = sorted(
        candidates,
        key=lambda x: (
            safe_number(
                x.get("score")
            ),
            safe_number(
                x.get("market_cap")
            ),
            safe_number(
                x.get("trade_value")
            )
        ),
        reverse=True
    )

    # ---------------------------------------------
    # Gainers
    # ---------------------------------------------

    top_gainers = sorted(
        candidates,
        key=lambda x: safe_number(
            x.get("change_percent")
        ),
        reverse=True
    )

    # ---------------------------------------------
    # Losers
    # ---------------------------------------------

    top_losers = sorted(
        candidates,
        key=lambda x: safe_number(
            x.get("change_percent")
        )
    )

    # ---------------------------------------------
    # Most active
    # ---------------------------------------------

    most_active = sorted(
        candidates,
        key=lambda x: safe_number(
            x.get("trade_value")
        ),
        reverse=True
    )

    return {
        "candidate_count": len(
            candidates
        ),
        "short_term_top_20": short_term[:20],
        "six_month_top_20": six_month[:20],
        "top_gainers": top_gainers[:20],
        "top_losers": top_losers[:20],
        "most_active": most_active[:20]
    }


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "status": "ok",
        "message": "Shkar Bourse API is running",
        "version": "7.0.0",
        "source": "tindex.app"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "source": "tindex.app",
        "version": "7.0.0",

        "market_open": is_market_open(),

        "request_interval_seconds": (
            get_request_interval()
        ),

        "seconds_until_next_request": (
            seconds_until_next_request()
        ),

        "cache_available": (
            _cache_data is not None
        ),

        "last_request_time": (
            _last_request_time
            if _last_request_time > 0
            else None
        ),

        "last_success_time": (
            _last_success_time
        ),

        "daily_requests_used": (
            daily_requests_used()
        ),

        "daily_requests_remaining": (
            daily_requests_remaining()
        ),

        "last_error": _last_error
    }


# =========================================================
# MARKET
# =========================================================

@app.get("/market")
def market():

    return get_market_data()


# =========================================================
# FULL MARKET
# =========================================================

@app.get("/full-market")
def full_market():

    result = get_market_data()

    if result["status"] != "ok":
        return result

    data = result["data"]

    breadth = data.get(
        "breadth",
        {}
    )

    totals = data.get(
        "totals",
        {}
    )

    flow = data.get(
        "flow",
        {}
    )

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": result.get(
            "cached",
            False
        ),

        "market_date": data.get(
            "as_of"
        ),

        "symbols": (
            breadth.get(
                "total_symbols"
            )
            if isinstance(
                breadth,
                dict
            )
            else None
        ),

        "quoted_symbols": (
            breadth.get(
                "quoted_symbols"
            )
            if isinstance(
                breadth,
                dict
            )
            else None
        ),

        "breadth": breadth,
        "totals": totals,
        "flow": flow,

        "boards": data.get(
            "boards",
            {}
        ),

        "sectors": data.get(
            "sectors",
            []
        ),

        "options": data.get(
            "options",
            {}
        ),

        "fear_greed": data.get(
            "fear_greed"
        ),

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


# =========================================================
# FULL ANALYSIS
# =========================================================

@app.get("/full-analysis")
def full_analysis():

    result = get_market_data()

    if result["status"] != "ok":
        return result

    data = result["data"]

    analysis = analyze_overview(
        data
    )

    flow = data.get(
        "flow",
        {}
    )

    breadth = data.get(
        "breadth",
        {}
    )

    fear_greed = data.get(
        "fear_greed"
    )

    return {
        "status": "ok",
        "source": "tindex.app",

        "cached": result.get(
            "cached",
            False
        ),

        "market_date": data.get(
            "as_of"
        ),

        "analysis": analysis,

        "market_context": {
            "breadth": breadth,
            "flow": flow,
            "fear_greed": fear_greed,
            "options": data.get(
                "options",
                {}
            )
        },

        "sectors": data.get(
            "sectors",
            []
        ),

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
        ),

        "request_interval_seconds": (
            get_request_interval()
        ),

        "seconds_until_next_request": (
            seconds_until_next_request()
        )
    }


# =========================================================
# SHORT TERM
# =========================================================

@app.get("/short-term-opportunities")
def short_term_opportunities():

    result = get_market_data()

    if result["status"] != "ok":
        return result

    analysis = analyze_overview(
        result["data"]
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
            **stock
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
        "opportunities": opportunities,

        "warning": (
            "این رتبه‌بندی سیگنال "
            "اولیه است و سود تضمینی نیست."
        )
    }


# =========================================================
# SIX MONTH
# =========================================================

@app.get("/six-month-opportunities")
def six_month_opportunities():

    result = get_market_data()

    if result["status"] != "ok":
        return result

    analysis = analyze_overview(
        result["data"]
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
            **stock
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
        "opportunities": opportunities,

        "warning": (
            "این رتبه‌بندی نسخه اولیه "
            "است و سود تضمینی نیست."
        )
    }


# =========================================================
# SCANNER
# =========================================================

@app.get("/scanner/step")
def scanner_step():

    result = get_market_data()

    if result["status"] != "ok":
        return result

    data = result["data"]

    analysis = analyze_overview(
        data
    )

    return {
        "status": "ok",
        "source": "tindex.app",

        "message": (
            "اسکن بازار با یک درخواست "
            "Overview با موفقیت انجام شد."
        ),

        "market_date": data.get(
            "as_of"
        ),

        "total_symbols": (
            data.get(
                "breadth",
                {}
            ).get(
                "total_symbols"
            )
            if isinstance(
                data.get(
                    "breadth"
                ),
                dict
            )
            else None
        ),

        "quoted_symbols": (
            data.get(
                "breadth",
                {}
            ).get(
                "quoted_symbols"
            )
            if isinstance(
                data.get(
                    "breadth"
                ),
                dict
            )
            else None
        ),

        "top_gainers": analysis[
            "top_gainers"
        ][:10],

        "top_losers": analysis[
            "top_losers"
        ][:10],

        "most_active": analysis[
            "most_active"
        ][:10],

        "flow": data.get(
            "flow",
            {}
        ),

        "fear_greed": data.get(
            "fear_greed"
        ),

        "options": data.get(
            "options",
            {}
        ),

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
