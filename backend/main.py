import os
import time
import threading
import requests

from fastapi import FastAPI


app = FastAPI(
    title="Shkar Bourse API",
    version="3.0.0"
)


# ============================================================
# TINDEX
# ============================================================

TINDEX_TOKEN = os.getenv("TINDEX_TOKEN", "").strip()

TINDEX_BASE_URL = "https://tindex.app/api/public"

OVERVIEW_URL = (
    f"{TINDEX_BASE_URL}/stock-market/overview"
)

STOCKS_URL = (
    f"{TINDEX_BASE_URL}/stocks/by-category/stock-energy"
)


# ============================================================
# RATE LIMIT
# ============================================================

# پلن رایگان TIndex:
# حدود 1 درخواست در دقیقه
#
# ما کمی فاصله امن می‌گذاریم تا به 429 نخوریم.

MIN_REQUEST_INTERVAL = 65


_last_tindex_request = 0.0

_request_lock = threading.Lock()


def wait_for_tindex_slot():

    global _last_tindex_request

    with _request_lock:

        now = time.time()

        elapsed = now - _last_tindex_request

        if elapsed < MIN_REQUEST_INTERVAL:

            wait_seconds = (
                MIN_REQUEST_INTERVAL - elapsed
            )

            time.sleep(wait_seconds)

        _last_tindex_request = time.time()


# ============================================================
# MARKET CACHE
# ============================================================

_market_data = None
_market_time = 0


# ============================================================
# ALL STOCKS CACHE
# ============================================================

_all_stocks = {}

_stocks_lock = threading.Lock()

_current_page = 1

_total_pages = None

_total_symbols = 0

_last_page_update = 0

_stocks_complete = False


# ============================================================
# SAFE NUMBER
# ============================================================

def safe_number(value, default=0.0):

    try:

        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):

        return default


# ============================================================
# TINDEX REQUEST
# ============================================================

def tindex_get(url, params=None):

    global _last_tindex_request

    if not TINDEX_TOKEN:

        return {
            "status": "error",
            "message": "TINDEX_TOKEN پیدا نشد."
        }

    wait_for_tindex_slot()

    headers = {
        "Authorization": f"Bearer {TINDEX_TOKEN}",
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

        if response.status_code == 429:

            retry_after = response.headers.get(
                "Retry-After",
                "نامشخص"
            )

            return {
                "status": "error",
                "rate_limited": True,
                "message": (
                    "TIndex محدودیت درخواست اعمال کرده. "
                    f"Retry-After: {retry_after}"
                )
            }

        if response.status_code == 401:

            return {
                "status": "error",
                "message": "TINDEX_TOKEN معتبر نیست."
            }

        if response.status_code == 403:

            return {
                "status": "error",
                "message": (
                    "دسترسی API برای این حساب توسط TIndex "
                    "غیرفعال شده است."
                )
            }

        response.raise_for_status()

        payload = response.json()

        if not payload.get("success"):

            return {
                "status": "error",
                "message": payload.get(
                    "message",
                    "TIndex پاسخ موفقی ارسال نکرد."
                )
            }

        return {
            "status": "ok",
            "data": payload.get("data"),
            "meta": payload.get("meta")
        }

    except requests.exceptions.RequestException as e:

        return {
            "status": "error",
            "message": f"خطا در اتصال به TIndex: {str(e)}"
        }

    except ValueError:

        return {
            "status": "error",
            "message": "پاسخ TIndex JSON معتبر نبود."
        }


# ============================================================
# MARKET OVERVIEW
# ============================================================

def get_market_overview():

    global _market_data
    global _market_time

    now = time.time()

    # کش 60 ثانیه‌ای
    if (
        _market_data is not None
        and (now - _market_time) < 60
    ):

        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": True,
            "data": _market_data
        }

    result = tindex_get(
        OVERVIEW_URL
    )

    if result["status"] != "ok":

        # اگر قبلاً داده داشتیم،
        # همان داده آخر را نگه می‌داریم.

        if _market_data is not None:

            return {
                "status": "ok",
                "source": "tindex.app",
                "cached": True,
                "stale": True,
                "data": _market_data
            }

        return result

    _market_data = result["data"]

    _market_time = time.time()

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": False,
        "data": _market_data
    }


# ============================================================
# FETCH ONE STOCK PAGE
# ============================================================

def fetch_stock_page(page):

    global _total_pages
    global _total_symbols
    global _last_page_update

    result = tindex_get(
        STOCKS_URL,
        params={
            "page": page,
            "per_page": 100,
            "sort": "ticker",
            "dir": "asc"
        }
    )

    if result["status"] != "ok":

        return result

    data = result.get("data") or {}

    rows = data.get("rows") or []

    meta = result.get("meta") or {}

    if not meta:

        meta = data.get("meta") or {}

    total = safe_number(
        meta.get("total"),
        0
    )

    last_page = safe_number(
        meta.get("last_page"),
        0
    )

    if total > 0:

        _total_symbols = int(total)

    if last_page > 0:

        _total_pages = int(last_page)

    added = 0

    with _stocks_lock:

        for stock in rows:

            slug = stock.get("slug")

            if not slug:

                continue

            _all_stocks[slug] = stock

            added += 1

        _last_page_update = time.time()

    return {
        "status": "ok",
        "page": page,
        "rows": added,
        "total_cached": len(_all_stocks),
        "total_symbols": _total_symbols,
        "total_pages": _total_pages
    }


# ============================================================
# BACKGROUND STOCK COLLECTOR
# ============================================================

def stock_collector():

    global _current_page
    global _stocks_complete
    global _total_pages

    print(
        "Shkar Bourse stock collector started."
    )

    while True:

        try:

            # اگر کل بازار هنوز کامل نشده،
            # صفحه بعدی را دریافت کن.

            if _total_pages is None:

                page = 1

            else:

                page = _current_page

            result = fetch_stock_page(page)

            if result["status"] == "ok":

                print(
                    "TIndex stock page:",
                    page,
                    "| cached:",
                    len(_all_stocks),
                    "| total:",
                    _total_symbols,
                    "| pages:",
                    _total_pages
                )

                if (
                    _total_pages is not None
                    and page >= _total_pages
                ):

                    _stocks_complete = True

                    _current_page = 1

                else:

                    _current_page = page + 1

            else:

                print(
                    "TIndex stock collector error:",
                    result.get("message")
                )

                # در خطا، صفحه را جلو نمی‌بریم.

            # مهم:
            # حداقل 65 ثانیه بین درخواست‌های TIndex

            time.sleep(MIN_REQUEST_INTERVAL)

        except Exception as e:

            print(
                "Stock collector exception:",
                str(e)
            )

            time.sleep(
                MIN_REQUEST_INTERVAL
            )


# ============================================================
# START BACKGROUND COLLECTOR
# ============================================================

@app.on_event("startup")
def startup_event():

    collector = threading.Thread(
        target=stock_collector,
        daemon=True
    )

    collector.start()


# ============================================================
# SHORT TERM SCORE
# ============================================================

def calculate_short_term_score(
    stock,
    market_data=None
):

    score = 0.0

    change = safe_number(
        stock.get("change"),
        0
    )

    value = safe_number(
        stock.get("value"),
        0
    )

    volume = safe_number(
        stock.get("volume"),
        0
    )

    market_cap = safe_number(
        stock.get("market_cap"),
        0
    )

    pe = stock.get("pe")

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    if change >= 5:

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

    # --------------------------------------------------------
    # Trade value
    # --------------------------------------------------------

    if value >= 10_000_000_000_000:

        score += 25

    elif value >= 5_000_000_000_000:

        score += 20

    elif value >= 1_000_000_000_000:

        score += 14

    elif value >= 100_000_000_000:

        score += 7

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    if volume > 1_000_000_000:

        score += 10

    elif volume > 100_000_000:

        score += 6

    elif volume > 10_000_000:

        score += 3

    # --------------------------------------------------------
    # Market cap
    # --------------------------------------------------------

    if market_cap > 0:

        score += 5

    # --------------------------------------------------------
    # P/E
    # --------------------------------------------------------

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

            score -= 10

        elif pe_value < 0:

            score -= 5

    return max(
        0,
        min(
            100,
            round(score)
        )
    )


# ============================================================
# SIX MONTH SCORE
# ============================================================

def calculate_six_month_score(
    stock,
    market_data=None
):

    score = 0.0

    change = safe_number(
        stock.get("change"),
        0
    )

    value = safe_number(
        stock.get("value"),
        0
    )

    market_cap = safe_number(
        stock.get("market_cap"),
        0
    )

    pe = stock.get("pe")

    # --------------------------------------------------------
    # Liquidity
    # --------------------------------------------------------

    if value >= 10_000_000_000_000:

        score += 25

    elif value >= 5_000_000_000_000:

        score += 20

    elif value >= 1_000_000_000_000:

        score += 15

    elif value >= 100_000_000_000:

        score += 8

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    if change >= 5:

        score += 12

    elif change >= 3:

        score += 10

    elif change >= 2:

        score += 8

    elif change > 0:

        score += 4

    # --------------------------------------------------------
    # Market cap
    # --------------------------------------------------------

    if market_cap > 0:

        score += 8

    # --------------------------------------------------------
    # P/E
    # --------------------------------------------------------

    if pe is not None:

        pe_value = safe_number(
            pe,
            0
        )

        if 0 < pe_value <= 6:

            score += 20

        elif 6 < pe_value <= 10:

            score += 15

        elif 10 < pe_value <= 15:

            score += 8

        elif pe_value > 30:

            score -= 10

        elif pe_value < 0:

            score -= 8

    return max(
        0,
        min(
            100,
            round(score)
        )
    )


# ============================================================
# REASONS
# ============================================================

def build_reasons(stock):

    reasons = []

    change = safe_number(
        stock.get("change"),
        0
    )

    value = safe_number(
        stock.get("value"),
        0
    )

    pe = stock.get("pe")

    if change >= 3:

        reasons.append(
            "مومنتوم روزانه قدرتمند"
        )

    elif change > 0:

        reasons.append(
            "مومنتوم روزانه مثبت"
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
                "P/E بالا؛ نیازمند بررسی ارزش‌گذاری"
            )

    if not reasons:

        reasons.append(
            "نیازمند بررسی عمیق‌تر"
        )

    return reasons


# ============================================================
# ANALYZE ALL CACHED STOCKS
# ============================================================

def analyze_all_stocks():

    with _stocks_lock:

        stocks = list(
            _all_stocks.values()
        )

    candidates = []

    for stock in stocks:

        ticker = stock.get("ticker")

        if not ticker:

            continue

        short_score = (
            calculate_short_term_score(
                stock
            )
        )

        six_score = (
            calculate_six_month_score(
                stock
            )
        )

        candidates.append({

            "slug": stock.get(
                "slug"
            ),

            "ticker": ticker,

            "name": stock.get(
                "name",
                "---"
            ),

            "sector": stock.get(
                "sector",
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

            "closing_price": stock.get(
                "closing_price",
                0
            ),

            "closing_change_percent": stock.get(
                "closing_change",
                0
            ),

            "volume": stock.get(
                "volume",
                0
            ),

            "trade_value": stock.get(
                "value",
                0
            ),

            "market_cap": stock.get(
                "market_cap",
                0
            ),

            "pe": stock.get(
                "pe"
            ),

            "short_term_score": short_score,

            "six_month_score": six_score,

            "reasons": build_reasons(
                stock
            )
        })

    short_term = sorted(
        candidates,
        key=lambda x: (
            x["short_term_score"],
            x["trade_value"]
        ),
        reverse=True
    )[:3]

    six_month = sorted(
        candidates,
        key=lambda x: (
            x["six_month_score"],
            x["trade_value"]
        ),
        reverse=True
    )[:10]

    return {
        "short_term_top_3": short_term,
        "six_month_top_10": six_month
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "status": "ok",

        "message":
            "Shkar Bourse API is running",

        "version":
            "3.0.0",

        "source":
            "tindex.app",

        "tsetmc_direct":
            False

    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {

        "status":
            "healthy",

        "source":
            "tindex.app",

        "cached_stocks":
            len(_all_stocks),

        "total_symbols":
            _total_symbols,

        "total_pages":
            _total_pages,

        "stocks_complete":
            _stocks_complete

    }


# ============================================================
# MARKET
# ============================================================

@app.get("/market")
def market():

    return get_market_overview()


# ============================================================
# STOCK UNIVERSE STATUS
# ============================================================

@app.get("/stocks-status")
def stocks_status():

    with _stocks_lock:

        cached_count = len(
            _all_stocks
        )

    progress = 0.0

    if _total_symbols > 0:

        progress = (
            cached_count
            /
            _total_symbols
        ) * 100

    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "cached_stocks":
            cached_count,

        "total_symbols":
            _total_symbols,

        "total_pages":
            _total_pages,

        "current_page":
            _current_page,

        "progress_percent":
            round(
                progress,
                2
            ),

        "complete":
            _stocks_complete,

        "last_page_update":
            _last_page_update,

        "request_interval_seconds":
            MIN_REQUEST_INTERVAL,

        "message":
            (
                "داده‌های کل بازار به‌صورت "
                "تدریجی و کنترل‌شده دریافت می‌شوند."
            )

    }


# ============================================================
# ANALYSIS
# ============================================================

@app.get("/analysis")
def analysis():

    analyzed = (
        analyze_all_stocks()
    )

    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "coverage": {

            "cached_stocks":
                len(_all_stocks),

            "total_symbols":
                _total_symbols,

            "complete":
                _stocks_complete

        },

        "analysis":
            analyzed,

        "warning":
            (
                "امتیازها نسخه اولیه موتور تحلیل "
                "هستند و سود تضمینی نیستند."
            )

    }


# ============================================================
# SHORT TERM
# ============================================================

@app.get(
    "/short-term-opportunities"
)
def short_term_opportunities():

    analyzed = (
        analyze_all_stocks()
    )

    opportunities = []

    for rank, stock in enumerate(
        analyzed["short_term_top_3"],
        start=1
    ):

        item = dict(stock)

        item["rank"] = rank

        opportunities.append(
            item
        )

    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "section":
            "short_term_opportunities",

        "title":
            "۳ فرصت برتر کوتاه‌مدت",

        "coverage": {

            "cached_stocks":
                len(_all_stocks),

            "total_symbols":
                _total_symbols,

            "complete":
                _stocks_complete

        },

        "count":
            len(opportunities),

        "opportunities":
            opportunities,

        "warning":
            (
                "این نسخه هنوز پیش‌بینی قطعی "
                "دو برابر شدن قیمت نیست."
            )

    }


# ============================================================
# SIX MONTH
# ============================================================

@app.get(
    "/six-month-opportunities"
)
def six_month_opportunities():

    analyzed = (
        analyze_all_stocks()
    )

    opportunities = []

    for rank, stock in enumerate(
        analyzed["six_month_top_10"],
        start=1
    ):

        item = dict(stock)

        item["rank"] = rank

        opportunities.append(
            item
        )

    return {

        "status":
            "ok",

        "source":
            "tindex.app",

        "section":
            "six_month_opportunities",

        "title":
            "۱۰ فرصت برتر سرمایه‌گذاری ۶ ماهه",

        "coverage": {

            "cached_stocks":
                len(_all_stocks),

            "total_symbols":
                _total_symbols,

            "complete":
                _stocks_complete

        },

        "count":
            len(opportunities),

        "opportunities":
            opportunities,

        "warning":
            (
                "این نسخه رتبه‌بندی اولیه است "
                "و سود تضمینی نیست."
            )

    }
