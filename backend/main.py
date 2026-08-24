import os
import time
import threading
import requests

from fastapi import FastAPI


app = FastAPI(
    title="Shkar Bourse API",
    version="3.0.0"
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
# LIMITS
# =========================================================

# TIndex free plan:
# 1 request / minute
# 100 successful requests / day

MIN_REQUEST_INTERVAL = 61
DAILY_LIMIT = 100

PER_PAGE = 100

# چند درخواست را برای اطلاعات کلی بازار ذخیره می‌کنیم
RESERVED_REQUESTS = 15


# =========================================================
# GLOBAL CACHE
# =========================================================

market_overview = None

stocks_cache = {}

current_page = 1
total_pages = None
total_symbols = None

last_request_time = 0

daily_successful_requests = 0
daily_date = None

last_error = None

cache_lock = threading.Lock()


# =========================================================
# TOKEN
# =========================================================

def get_token():

    token = os.getenv("TINDEX_TOKEN", "").strip()

    if not token:
        return None

    return token


# =========================================================
# DAILY COUNTER
# =========================================================

def reset_daily_counter_if_needed():

    global daily_date
    global daily_successful_requests

    today = time.strftime("%Y-%m-%d")

    if daily_date != today:

        daily_date = today
        daily_successful_requests = 0


# =========================================================
# REQUEST CONTROL
# =========================================================

def can_make_request():

    reset_daily_counter_if_needed()

    now = time.time()

    # فاصله بین درخواست‌ها
    if now - last_request_time < MIN_REQUEST_INTERVAL:
        return False

    # سهمیه روزانه
    if daily_successful_requests >= DAILY_LIMIT:
        return False

    return True


# =========================================================
# TINDEX REQUEST
# =========================================================

def tindex_get(url, params=None):

    global last_request_time
    global daily_successful_requests
    global last_error

    token = get_token()

    if not token:

        return {
            "status": "error",
            "message": "TINDEX_TOKEN پیدا نشد."
        }

    with cache_lock:

        reset_daily_counter_if_needed()

        if not can_make_request():

            return {
                "status": "rate_limited_local",
                "message": (
                    "فعلاً درخواست جدید به TIndex ارسال نمی‌شود "
                    "تا محدودیت API رعایت شود."
                )
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "ShkarBoursePro2/3.0"
        }

        try:

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )

            # زمان آخرین درخواست
            last_request_time = time.time()

            # -------------------------------------------------
            # 429
            # -------------------------------------------------

            if response.status_code == 429:

                retry_after = response.headers.get(
                    "Retry-After",
                    "60"
                )

                last_error = (
                    f"TIndex rate limit. Retry-After={retry_after}"
                )

                return {
                    "status": "rate_limited",
                    "retry_after": retry_after,
                    "message": (
                        "محدودیت درخواست TIndex فعال است."
                    )
                }

            # -------------------------------------------------
            # AUTH
            # -------------------------------------------------

            if response.status_code == 401:

                last_error = "Invalid TIndex token"

                return {
                    "status": "error",
                    "message": "توکن TIndex معتبر نیست."
                }

            # -------------------------------------------------
            # FORBIDDEN
            # -------------------------------------------------

            if response.status_code == 403:

                last_error = "TIndex API disabled"

                return {
                    "status": "error",
                    "message": (
                        "دسترسی API حساب TIndex غیرفعال شده است."
                    )
                }

            response.raise_for_status()

            payload = response.json()

            # فقط درخواست موفق سهمیه روزانه را مصرف می‌کند
            if payload.get("success") is True:

                daily_successful_requests += 1

            else:

                last_error = payload.get(
                    "message",
                    "TIndex پاسخ موفقی ارسال نکرد."
                )

                return {
                    "status": "error",
                    "message": last_error
                }

            return {
                "status": "ok",
                "data": payload.get("data"),
                "headers": {
                    "limit": response.headers.get(
                        "X-RateLimit-Limit"
                    ),
                    "remaining": response.headers.get(
                        "X-RateLimit-Remaining"
                    )
                }
            }

        except requests.exceptions.RequestException as exc:

            last_error = str(exc)

            return {
                "status": "error",
                "message": (
                    f"خطا در اتصال به TIndex: {str(exc)}"
                )
            }

        except ValueError:

            last_error = "Invalid JSON"

            return {
                "status": "error",
                "message": (
                    "پاسخ TIndex JSON معتبر نبود."
                )
            }


# =========================================================
# MARKET OVERVIEW
# =========================================================

def update_market_overview():

    global market_overview

    result = tindex_get(
        OVERVIEW_URL
    )

    if result["status"] == "ok":

        market_overview = result["data"]

    return result


# =========================================================
# STOCK PAGE
# =========================================================

def update_stock_page(page):

    global total_pages
    global total_symbols
    global stocks_cache

    result = tindex_get(
        STOCKS_URL,
        params={
            "page": page,
            "per_page": PER_PAGE,
            "sort": "ticker",
            "dir": "asc"
        }
    )

    if result["status"] != "ok":

        return result

    data = result["data"]

    rows = data.get("rows", [])

    meta = data.get("meta", {})

    total_pages = meta.get(
        "last_page",
        total_pages
    )

    total_symbols = meta.get(
        "total",
        total_symbols
    )

    # ذخیره نمادها
    for stock in rows:

        ticker = stock.get("ticker")

        if ticker:

            stocks_cache[ticker] = stock

    return {
        "status": "ok",
        "page": page,
        "rows": len(rows),
        "total_pages": total_pages,
        "total_symbols": total_symbols
    }


# =========================================================
# NEXT MARKET UPDATE
# =========================================================

def perform_next_update():

    global current_page

    reset_daily_counter_if_needed()

    # -----------------------------------------------
    # اگر تقریباً سهمیه روزانه تمام شده
    # -----------------------------------------------

    if daily_successful_requests >= (
        DAILY_LIMIT - RESERVED_REQUESTS
    ):

        return {
            "status": "daily_budget_reserved",
            "message": (
                "سهمیه روزانه برای درخواست‌های ضروری "
                "ذخیره شده است."
            )
        }

    # -----------------------------------------------
    # ابتدا بازار کلی
    # -----------------------------------------------

    if market_overview is None:

        return update_market_overview()

    # -----------------------------------------------
    # اسکن صفحات سهام
    # -----------------------------------------------

    if total_pages is None:

        total_pages_local = 17

    else:

        total_pages_local = total_pages

    result = update_stock_page(
        current_page
    )

    if result["status"] == "ok":

        current_page += 1

        if current_page > total_pages_local:

            current_page = 1

    return result


# =========================================================
# MARKET SCORE
# =========================================================

def safe_number(value, default=0.0):

    try:

        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):

        return default


def get_market_change(data):

    if not data:
        return 0.0

    for index in data.get("indices", []):

        name = str(
            index.get("name", "")
        )

        slug = str(
            index.get("slug", "")
        ).upper()

        if (
            "کل" in name
            or slug == "TEDPIX"
        ):

            return safe_number(
                index.get("change_percent"),
                0
            )

    return 0.0


def calculate_score(stock, market_change):

    score = 0

    change = safe_number(
        stock.get("change"),
        0
    )

    value = safe_number(
        stock.get("value"),
        0
    )

    pe = stock.get("pe")

    # -----------------------------------------------
    # Momentum
    # -----------------------------------------------

    if change >= 3:
        score += 20

    elif change >= 2:
        score += 15

    elif change >= 1:
        score += 10

    elif change > 0:
        score += 5

    elif change <= -3:
        score -= 15

    elif change <= -2:
        score -= 10

    # -----------------------------------------------
    # Liquidity
    # -----------------------------------------------

    if value >= 10_000_000_000_000:
        score += 20

    elif value >= 5_000_000_000_000:
        score += 15

    elif value >= 1_000_000_000_000:
        score += 10

    elif value >= 100_000_000_000:
        score += 5

    # -----------------------------------------------
    # P/E
    # -----------------------------------------------

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

    # -----------------------------------------------
    # Relative strength
    # -----------------------------------------------

    if change > market_change:

        score += 10

    elif change < market_change - 2:

        score -= 5

    return max(
        0,
        min(
            100,
            round(score)
        )
    )


# =========================================================
# ANALYSIS ENGINE
# =========================================================

def analyze_all_stocks():

    market_change = get_market_change(
        market_overview
    )

    candidates = []

    for stock in stocks_cache.values():

        score = calculate_score(
            stock,
            market_change
        )

        candidates.append({

            "ticker": stock.get(
                "ticker"
            ),

            "name": stock.get(
                "name",
                "---"
            ),

            "current_price": stock.get(
                "last_price",
                0
            ),

            "change_percent": stock.get(
                "change",
                0
            ),

            "trade_value": stock.get(
                "value",
                0
            ),

            "volume": stock.get(
                "volume",
                0
            ),

            "market_cap": stock.get(
                "market_cap",
                0
            ),

            "pe": stock.get(
                "pe"
            ),

            "score": score
        })

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return candidates


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "status": "ok",
        "message": "Shkar Bourse API is running",
        "version": "3.0.0",
        "source": "tindex.app"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    reset_daily_counter_if_needed()

    return {

        "status": "healthy",

        "source": "tindex.app",

        "cached_stocks": len(
            stocks_cache
        ),

        "total_symbols": total_symbols,

        "total_pages": total_pages,

        "current_page": current_page,

        "stocks_complete": (
            total_symbols is not None
            and len(stocks_cache) >= total_symbols
        ),

        "daily_requests_used": (
            daily_successful_requests
        ),

        "daily_requests_remaining_local": max(
            0,
            DAILY_LIMIT -
            daily_successful_requests
        ),

        "last_error": last_error
    }


# =========================================================
# MARKET
# =========================================================

@app.get("/market")
def market():

    # فقط از کش خودمان جواب بده
    # تا هر کاربر مستقیماً TIndex را صدا نزند.

    if market_overview is None:

        result = update_market_overview()

        if result["status"] != "ok":

            return result

    return {

        "status": "ok",

        "source": "tindex.app",

        "data": market_overview,

        "cached_stocks": len(
            stocks_cache
        )
    }


# =========================================================
# ANALYSIS
# =========================================================

@app.get("/analysis")
def analysis():

    # تحلیل فقط روی داده‌هایی که تا الان
    # در کش جمع شده‌اند.

    candidates = analyze_all_stocks()

    return {

        "status": "ok",

        "source": "tindex.app",

        "stocks_loaded": len(
            stocks_cache
        ),

        "total_symbols": total_symbols,

        "stocks_complete": (
            total_symbols is not None
            and len(stocks_cache) >= total_symbols
        ),

        "top_3": candidates[:3],

        "top_10": candidates[:10],

        "warning": (
            "این نسخه موتور رتبه‌بندی اولیه است "
            "و به معنی تضمین سود یا دو برابر شدن قیمت نیست."
        )
    }


# =========================================================
# SHORT TERM
# =========================================================

@app.get("/short-term-opportunities")
def short_term_opportunities():

    candidates = analyze_all_stocks()

    top = candidates[:3]

    result = []

    for rank, stock in enumerate(
        top,
        start=1
    ):

        result.append({

            "rank": rank,

            "score": stock["score"],

            "ticker": stock["ticker"],

            "name": stock["name"],

            "current_price": stock[
                "current_price"
            ],

            "change_percent": stock[
                "change_percent"
            ],

            "trade_value": stock[
                "trade_value"
            ],

            "pe": stock["pe"]

        })

    return {

        "status": "ok",

        "section": (
            "short_term_opportunities"
        ),

        "title": (
            "۳ فرصت برتر کوتاه‌مدت"
        ),

        "stocks_loaded": len(
            stocks_cache
        ),

        "complete_market": (
            total_symbols is not None
            and len(stocks_cache) >= total_symbols
        ),

        "opportunities": result,

        "warning": (
            "این رتبه‌بندی تحلیلی است و "
            "تضمین دو برابر شدن قیمت نیست."
        )
    }


# =========================================================
# SIX MONTH
# =========================================================

@app.get("/six-month-opportunities")
def six_month_opportunities():

    candidates = analyze_all_stocks()

    top = candidates[:10]

    result = []

    for rank, stock in enumerate(
        top,
        start=1
    ):

        result.append({

            "rank": rank,

            "rank_score": stock[
                "score"
            ],

            "ticker": stock[
                "ticker"
            ],

            "name": stock[
                "name"
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
            ]

        })

    return {

        "status": "ok",

        "section": (
            "six_month_opportunities"
        ),

        "title": (
            "۱۰ فرصت برتر سرمایه‌گذاری ۶ ماهه"
        ),

        "stocks_loaded": len(
            stocks_cache
        ),

        "complete_market": (
            total_symbols is not None
            and len(stocks_cache) >= total_symbols
        ),

        "opportunities": result,

        "warning": (
            "این نسخه موتور تحلیل اولیه است "
            "و سود تضمینی ارائه نمی‌کند."
        )
    }


# =========================================================
# ADMIN / REFRESH STATUS
# =========================================================

@app.get("/scanner-status")
def scanner_status():

    reset_daily_counter_if_needed()

    return {

        "status": "ok",

        "source": "tindex.app",

        "scanner": {

            "current_page": current_page,

            "total_pages": total_pages,

            "cached_stocks": len(
                stocks_cache
            ),

            "total_symbols": total_symbols,

            "complete": (
                total_symbols is not None
                and len(stocks_cache) >= total_symbols
            )

        },

        "rate_limit": {

            "daily_limit": DAILY_LIMIT,

            "successful_requests_used": (
                daily_successful_requests
            ),

            "remaining_local": max(
                0,
                DAILY_LIMIT -
                daily_successful_requests
            ),

            "minimum_interval_seconds": (
                MIN_REQUEST_INTERVAL
            )

        },

        "message": (
            "هر بار فراخوانی این endpoint "
            "به TIndex درخواست ارسال نمی‌کند."
        )
    }


# =========================================================
# MANUAL SCAN STEP
# =========================================================

@app.post("/scanner/step")
def scanner_step():

    result = perform_next_update()

    return {

        "status": result.get(
            "status",
            "unknown"
        ),

        "result": result,

        "cached_stocks": len(
            stocks_cache
        ),

        "total_symbols": total_symbols,

        "current_page": current_page,

        "total_pages": total_pages,

        "daily_requests_used": (
            daily_successful_requests
        )

    }
