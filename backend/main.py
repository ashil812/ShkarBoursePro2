import os
import time
from datetime import datetime
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

OVERVIEW_URL = f"{TINDEX_BASE_URL}/stock-market/overview"
STOCKS_URL = f"{TINDEX_BASE_URL}/stocks/by-category/stock-energy"


# =========================================================
# SETTINGS
# =========================================================

DAILY_LIMIT = 100

# حداقل فاصله بین دو درخواست واقعی به TIndex
MIN_REQUEST_INTERVAL = 75

# کش داده‌ها
MARKET_CACHE_SECONDS = 75
OVERVIEW_CACHE_SECONDS = 75

PER_PAGE = 100

# حداکثر صفحات برای جلوگیری از Loop ناخواسته
MAX_PAGES = 5000


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


# =========================================================
# MARKET TIME
# =========================================================

def is_market_open():
    """
    تشخیص تقریبی زمان فعال بازار بورس ایران.

    شنبه تا چهارشنبه:
    09:00 تا 12:30

    پنجشنبه و جمعه:
    تعطیل
    """

    try:
        tehran = ZoneInfo("Asia/Tehran")
        now = datetime.now(tehran)

        weekday = now.weekday()

        # شنبه تا چهارشنبه
        if weekday not in [5, 6, 0, 1, 2]:
            return False

        current_minutes = (
            now.hour * 60
            + now.minute
        )

        start_minutes = 9 * 60
        end_minutes = 12 * 60 + 30

        return (
            start_minutes
            <= current_minutes
            <= end_minutes
        )

    except Exception:
        return False


def current_market_mode():
    if is_market_open():
        return "active"

    return "inactive"


# =========================================================
# DAILY REQUEST LIMIT
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
# RATE LIMIT
# =========================================================

def seconds_until_next_request():
    if _last_request_time <= 0:
        return 0

    elapsed = time.time() - _last_request_time

    remaining = MIN_REQUEST_INTERVAL - elapsed

    if remaining <= 0:
        return 0

    return int(remaining) + 1


def can_request_tindex():
    cleanup_daily_requests()

    if len(_daily_requests) >= DAILY_LIMIT:
        return (
            False,
            "سقف 100 درخواست در 24 ساعت مصرف شده است."
        )

    wait_seconds = seconds_until_next_request()

    if wait_seconds > 0:
        return (
            False,
            f"برای درخواست بعدی باید {wait_seconds} ثانیه صبر شود."
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
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ShkarBoursePro2/7.0"
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


# =========================================================
# TINDEX REQUEST
# =========================================================

def make_tindex_request(
    url,
    params=None
):
    global _last_error
    global _last_request_time

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

    allowed, reason = can_request_tindex()

    if not allowed:
        return {
            "status": "error",
            "source": "local-rate-limit",
            "message": reason,
            "wait_seconds": seconds_until_next_request(),
            "daily_requests_used": (
                daily_requests_used()
            ),
            "daily_requests_remaining": (
                daily_requests_remaining()
            )
        }

    # ثبت زمان درخواست واقعی
    request_time = time.time()

    _daily_requests.append(
        request_time
    )

    _last_request_time = request_time

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

        if result.get("success") is False:
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
            "data": result.get("data"),
            "meta": result.get("meta")
        }

    except requests.exceptions.RequestException as exc:
        _last_error = str(exc)

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
# FULL MARKET
# =========================================================

def get_full_market(
    force=False
):
    global _full_market_cache
    global _full_market_cache_time

    now = time.time()

    if (
        not force
        and _full_market_cache is not None
        and now - _full_market_cache_time
        < MARKET_CACHE_SECONDS
    ):
        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": True,
            "stocks": _full_market_cache,
            "count": len(
                _full_market_cache
            ),
            "page_count": None
        }

    all_stocks = []

    page = 1
    last_page = 1

    while True:

        result = make_tindex_request(
            STOCKS_URL,
            params={
                "page": page,
                "per_page": PER_PAGE
            }
        )

        if result["status"] != "ok":
            return result

        data = result.get(
            "data"
        )

        if not isinstance(
            data,
            dict
        ):
            return {
                "status": "error",
                "source": "tindex.app",
                "message": (
                    "ساختار data بازار معتبر نیست."
                )
            }

        rows = data.get(
            "rows",
            []
        )

        if isinstance(
            rows,
            list
        ):
            all_stocks.extend(
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

        try:
            last_page = int(
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
            last_page = page

        has_more = meta.get(
            "has_more"
        )

        if has_more is None:
            has_more = (
                page < last_page
            )

        if not has_more:
            break

        page += 1

        if page > MAX_PAGES:
            break

    _full_market_cache = (
        all_stocks
    )

    _full_market_cache_time = (
        time.time()
    )

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": False,
        "stocks": all_stocks,
        "count": len(
            all_stocks
        ),
        "page_count": page
    }


# =========================================================
# STOCK VALIDATION
# =========================================================

def is_valid_stock(stock):
    if not isinstance(
        stock,
        dict
    ):
        return False

    return bool(
        stock.get("ticker")
    )


# =========================================================
# SCORE
# =========================================================

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


# =========================================================
# REASONS
# =========================================================

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


# =========================================================
# NORMALIZE
# =========================================================

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
        "closing_change_percent": stock.get(
            "closing_change"
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


# =========================================================
# MARKET ANALYSIS
# =========================================================

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
        key=lambda x: safe_number(
            x["change_percent"]
        ),
        reverse=True
    )

    losers = sorted(
        candidates,
        key=lambda x: safe_number(
            x["change_percent"]
        )
    )

    most_active = sorted(
        candidates,
        key=lambda x: safe_number(
            x["trade_value"]
        ),
        reverse=True
    )

    return {
        "candidate_count": len(
            candidates
        ),
        "short_term_top_20": short_term[:20],
        "six_month_top_20": six_month[:20],
        "top_gainers": gainers[:20],
        "top_losers": losers[:20],
        "most_active": most_active[:20]
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

        "market_mode": (
            current_market_mode()
        ),

        "market_open": (
            is_market_open()
        ),

        "overview_cached": (
            _cache_data is not None
        ),

        "full_market_cached": (
            _full_market_cache is not None
        ),

        "cached_stocks": (
            len(_full_market_cache)
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

    result = get_full_market()

    if result["status"] != "ok":
        return result

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": result.get(
            "cached",
            False
        ),
        "count": result["count"],
        "stocks": result["stocks"],
        "daily_requests_used": (
            daily_requests_used()
        ),
        "daily_requests_remaining": (
            daily_requests_remaining()
        ),
        "market_mode": (
            current_market_mode()
        )
    }


# =========================================================
# FULL ANALYSIS
# =========================================================

@app.get("/full-analysis")
def full_analysis():

    result = get_full_market()

    if result["status"] != "ok":
        return result

    analysis = analyze_full_market(
        result["stocks"]
    )

    market_date = None

    if isinstance(
        _cache_data,
        dict
    ):
        market_date = _cache_data.get(
            "as_of"
        )

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": result.get(
            "cached",
            False
        ),
        "market_mode": (
            current_market_mode()
        ),
        "market_open": (
            is_market_open()
        ),
        "market_date": market_date,
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
        ),
        "seconds_until_next_request": (
            seconds_until_next_request()
        )
    }


# =========================================================
# SHORT TERM
# =========================================================

@app.get(
    "/short-term-opportunities"
)
def short_term_opportunities():

    result = get_full_market()

    if result["status"] != "ok":
        return result

    analysis = analyze_full_market(
        result["stocks"]
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
            "score": stock["score"],
            "ticker": stock["ticker"],
            "name": stock["name"],
            "sector": stock["sector"],
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
            "pe": stock["pe"],
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
        "opportunities": opportunities,
        "warning": (
            "این رتبه‌بندی سیگنال "
            "اولیه است و سود تضمینی نیست."
        )
    }


# =========================================================
# SIX MONTH
# =========================================================

@app.get(
    "/six-month-opportunities"
)
def six_month_opportunities():

    result = get_full_market()

    if result["status"] != "ok":
        return result

    analysis = analyze_full_market(
        result["stocks"]
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
            "score": stock["score"],
            "ticker": stock["ticker"],
            "name": stock["name"],
            "sector": stock["sector"],
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
            "pe": stock["pe"],
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
        "opportunities": opportunities,
        "warning": (
            "این رتبه‌بندی نسخه اولیه "
            "است و سود تضمینی نیست."
        )
    }


# =========================================================
# SCANNER
# =========================================================

@app.get(
    "/scanner/step"
)
def scanner_step():

    result = get_full_market()

    if result["status"] != "ok":
        return result

    stocks = result["stocks"]

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
        "top_gainers": analysis[
            "top_gainers"
        ][:10],
        "top_losers": analysis[
            "top_losers"
        ][:10],
        "most_active": analysis[
            "most_active"
        ][:10],
        "market_mode": (
            current_market_mode()
        ),
        "next_step": (
            "مرحله بعد: اضافه کردن "
            "تحلیل جریان پول حقیقی، "
            "صف خرید و فروش، روند تاریخی "
            "و امتیاز ریسک."
        ),
        "daily_requests_used": (
            daily_requests_used()
        ),
        "daily_requests_remaining": (
            daily_requests_remaining()
        )
    }
