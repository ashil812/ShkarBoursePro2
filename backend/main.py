import os
import time
import requests

from fastapi import FastAPI


app = FastAPI(
    title="Shkar Bourse API",
    version="3.0.0"
)


# =========================================================
# TINDEX
# =========================================================

TINDEX_URL = "https://tindex.app/api/public/stock-market/overview"

CACHE_SECONDS = 60
DAILY_LIMIT = 100


# =========================================================
# LOCAL STATE
# =========================================================

_cache_data = None
_cache_time = 0

_daily_requests = []
_last_error = None


# =========================================================
# HELPERS
# =========================================================

def cleanup_daily_requests():
    """
    فقط درخواست‌های 24 ساعت اخیر را نگه می‌دارد.
    """

    global _daily_requests

    now = time.time()

    cutoff = now - (24 * 60 * 60)

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


def seconds_since_last_request():
    cleanup_daily_requests()

    if not _daily_requests:
        return None

    return time.time() - _daily_requests[-1]


def can_request_tindex():
    """
    محدودیت محلی:

    - حداکثر یک درخواست در هر 60 ثانیه
    - حداکثر 100 درخواست در 24 ساعت
    """

    cleanup_daily_requests()

    used = len(_daily_requests)

    if used >= DAILY_LIMIT:
        return False, (
            "سقف محلی 100 درخواست در 24 ساعت مصرف شده است."
        )

    elapsed = seconds_since_last_request()

    if elapsed is not None and elapsed < CACHE_SECONDS:
        remaining = int(CACHE_SECONDS - elapsed) + 1

        return False, (
            f"برای درخواست بعدی باید {remaining} ثانیه صبر کنیم."
        )

    return True, None


def safe_number(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


# =========================================================
# TINDEX REQUEST
# =========================================================

def request_tindex():
    """
    فقط زمانی به TIndex درخواست می‌فرستد که
    محدودیت محلی اجازه بدهد.
    """

    global _last_error

    token = os.getenv("TINDEX_TOKEN", "").strip()

    if not token:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": "TINDEX_TOKEN در Render تنظیم نشده است."
        }

    allowed, reason = can_request_tindex()

    if not allowed:
        return {
            "status": "error",
            "source": "local-rate-limit",
            "message": reason,
            "daily_requests_used": daily_requests_used(),
            "daily_requests_remaining": daily_requests_remaining()
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ShkarBoursePro2/3.0"
    }

    try:

        # ثبت درخواست قبل از ارسال
        _daily_requests.append(time.time())

        response = requests.get(
            TINDEX_URL,
            headers=headers,
            timeout=30
        )

        if response.status_code == 429:

            _last_error = (
                "TIndex محدودیت درخواست اعمال کرده است."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": (
                    "TIndex درخواست را به دلیل محدودیت "
                    "Rate Limit رد کرد."
                ),
                "daily_requests_used": daily_requests_used(),
                "daily_requests_remaining": daily_requests_remaining()
            }

        if response.status_code == 401:

            _last_error = "توکن TIndex معتبر نیست."

            return {
                "status": "error",
                "source": "tindex.app",
                "message": "توکن TIndex معتبر نیست."
            }

        response.raise_for_status()

        result = response.json()

        if not isinstance(result, dict):

            _last_error = (
                "پاسخ TIndex ساختار JSON مورد انتظار را ندارد."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": (
                    "پاسخ TIndex ساختار JSON معتبر ندارد."
                )
            }

        if result.get("success") is False:

            message = result.get(
                "message",
                "TIndex پاسخ موفقی ارسال نکرد."
            )

            _last_error = str(message)

            return {
                "status": "error",
                "source": "tindex.app",
                "message": str(message)
            }

        data = result.get("data")

        if data is None:

            _last_error = (
                "فیلد data در پاسخ TIndex وجود ندارد."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": (
                    "داده بازار در پاسخ TIndex پیدا نشد."
                )
            }

        _last_error = None

        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": False,
            "data": data,
            "daily_requests_used": daily_requests_used(),
            "daily_requests_remaining": daily_requests_remaining()
        }

    except requests.exceptions.RequestException as e:

        _last_error = str(e)

        return {
            "status": "error",
            "source": "tindex.app",
            "message": f"خطا در اتصال به TIndex: {str(e)}",
            "daily_requests_used": daily_requests_used(),
            "daily_requests_remaining": daily_requests_remaining()
        }

    except ValueError:

        _last_error = (
            "پاسخ TIndex JSON معتبر نبود."
        )

        return {
            "status": "error",
            "source": "tindex.app",
            "message": "پاسخ TIndex JSON معتبر نبود."
        }


# =========================================================
# MARKET OVERVIEW
# =========================================================

def get_tindex_overview():

    global _cache_data
    global _cache_time

    now = time.time()

    # استفاده از cache
    if (
        _cache_data is not None
        and (now - _cache_time) < CACHE_SECONDS
    ):
        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": True,
            "data": _cache_data,
            "daily_requests_used": daily_requests_used(),
            "daily_requests_remaining": daily_requests_remaining()
        }

    result = request_tindex()

    if result["status"] != "ok":
        return result

    _cache_data = result["data"]
    _cache_time = now

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": False,
        "data": _cache_data,
        "daily_requests_used": daily_requests_used(),
        "daily_requests_remaining": daily_requests_remaining()
    }


# =========================================================
# ANALYSIS
# =========================================================

def calculate_short_term_score(stock, market_data):

    score = 0.0

    change = safe_number(
        stock.get("change_percent"),
        0
    )

    trade_value = safe_number(
        stock.get("trade_value"),
        0
    )

    pe = stock.get("pe")

    # Momentum
    if change >= 3:
        score += 20
    elif change >= 2:
        score += 15
    elif change >= 1:
        score += 8
    elif change > 0:
        score += 4
    elif change < -3:
        score -= 15
    elif change < -2:
        score -= 10

    # Liquidity
    if trade_value >= 10_000_000_000_000:
        score += 20
    elif trade_value >= 5_000_000_000_000:
        score += 15
    elif trade_value >= 1_000_000_000_000:
        score += 10
    elif trade_value >= 100_000_000_000:
        score += 5

    # P/E
    if pe is not None:

        pe_value = safe_number(pe, 0)

        if 0 < pe_value <= 6:
            score += 15
        elif 6 < pe_value <= 10:
            score += 10
        elif 10 < pe_value <= 15:
            score += 4
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


def calculate_six_month_score(stock, market_data):

    score = 0.0

    change = safe_number(
        stock.get("change_percent"),
        0
    )

    trade_value = safe_number(
        stock.get("trade_value"),
        0
    )

    pe = stock.get("pe")

    # Liquidity
    if trade_value >= 10_000_000_000_000:
        score += 25
    elif trade_value >= 5_000_000_000_000:
        score += 20
    elif trade_value >= 1_000_000_000_000:
        score += 14
    elif trade_value >= 100_000_000_000:
        score += 7

    # Momentum
    if change >= 3:
        score += 15
    elif change >= 2:
        score += 12
    elif change >= 1:
        score += 8
    elif change > 0:
        score += 4

    # P/E
    if pe is not None:

        pe_value = safe_number(pe, 0)

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


def build_reasons(stock):

    reasons = []

    change = safe_number(
        stock.get("change_percent"),
        0
    )

    trade_value = safe_number(
        stock.get("trade_value"),
        0
    )

    pe = stock.get("pe")

    if change >= 2:
        reasons.append(
            "مومنتوم روزانه مثبت"
        )

    if trade_value >= 10_000_000_000_000:
        reasons.append(
            "ارزش معاملات بسیار بالا"
        )
    elif trade_value >= 1_000_000_000_000:
        reasons.append(
            "نقدشوندگی مناسب"
        )

    if pe is not None:

        pe_value = safe_number(pe, 0)

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
# ANALYZE MARKET
# =========================================================

def analyze_market(data):

    boards = data.get(
        "boards",
        {}
    )

    candidates = []

    seen = set()

    board_names = [
        "gainers",
        "most_active_value",
        "most_active_volume"
    ]

    for board_name in board_names:

        rows = boards.get(
            board_name,
            []
        )

        if not isinstance(rows, list):
            continue

        for stock in rows:

            if not isinstance(stock, dict):
                continue

            ticker = stock.get("ticker")

            if not ticker:
                continue

            if ticker in seen:
                continue

            seen.add(ticker)

            short_score = calculate_short_term_score(
                stock,
                data
            )

            six_score = calculate_six_month_score(
                stock,
                data
            )

            candidates.append({

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
                    "change_percent",
                    0
                ),

                "trade_value": stock.get(
                    "trade_value",
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
        key=lambda x: x["short_term_score"],
        reverse=True
    )[:3]

    six_month = sorted(
        candidates,
        key=lambda x: x["six_month_score"],
        reverse=True
    )[:10]

    return {
        "short_term_top_3": short_term,
        "six_month_top_10": six_month,
        "candidate_count": len(candidates)
    }


# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def root():

    return {
        "status": "ok",
        "message": "Shkar Bourse API is running",
        "version": "3.0.0",
        "source": "tindex.app"
    }


@app.get("/health")
def health():

    return {

        "status": "healthy",

        "source": "tindex.app",

        "cached_stocks": (
            len(_cache_data.get("boards", {}).get("gainers", []))
            if isinstance(_cache_data, dict)
            else 0
        ),

        "total_symbols": (
            _cache_data.get("breadth", {}).get("total_symbols")
            if isinstance(_cache_data, dict)
            else None
        ),

        "total_pages": None,

        "current_page": 1,

        "stocks_complete": False,

        "daily_requests_used": daily_requests_used(),

        "daily_requests_remaining_local": (
            daily_requests_remaining()
        ),

        "last_error": _last_error
    }


@app.get("/market")
def market():

    result = get_tindex_overview()

    return result


@app.get("/analysis")
def analysis():

    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]

    analyzed = analyze_market(
        data
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

        "analysis": analyzed,

        "warning": (
            "این موتور در این مرحله نسخه اولیه است "
            "و سود یا رشد مشخصی را تضمین نمی‌کند."
        )
    }


@app.get("/six-month-opportunities")
def six_month_opportunities():

    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]

    analyzed = analyze_market(
        data
    )

    opportunities = []

    for rank, stock in enumerate(
        analyzed["six_month_top_10"],
        start=1
    ):

        opportunities.append({

            "rank": rank,

            "rank_score": stock[
                "six_month_score"
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

            "pe": stock[
                "pe"
            ],

            "risk": "نیازمند بررسی عمیق‌تر",

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
            "۱۰ فرصت برتر سرمایه‌گذاری ۶ ماهه"
        ),

        "market_date": data.get(
            "as_of"
        ),

        "count": len(
            opportunities
        ),

        "opportunities": opportunities,

        "warning": (
            "این رتبه‌بندی نسخه اولیه "
            "موتور تحلیل است و سود تضمینی نیست."
        )
    }


@app.get("/short-term-opportunities")
def short_term_opportunities():

    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]

    analyzed = analyze_market(
        data
    )

    opportunities = []

    for rank, stock in enumerate(
        analyzed["short_term_top_3"],
        start=1
    ):

        opportunities.append({

            "rank": rank,

            "score": stock[
                "short_term_score"
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
            "۳ فرصت برتر کوتاه‌مدت"
        ),

        "market_date": data.get(
            "as_of"
        ),

        "count": len(
            opportunities
        ),

        "opportunities": opportunities,

        "warning": (
            "این رتبه‌بندی سیگنال اولیه است "
            "و به معنی تضمین دو برابر شدن قیمت نیست."
        )
    }


# =========================================================
# SCANNER STEP
# =========================================================

@app.get("/scanner/step")
def scanner_step():

    """
    فعلاً این endpoint فقط یک درخواست واقعی
    به endpoint overview می‌فرستد.

    هدف این مرحله:
    بررسی پاسخ واقعی TIndex قبل از ساخت
    pagination کامل بازار.
    """

    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]

    boards = data.get(
        "boards",
        {}
    )

    stock_count = 0

    for board_name in boards:

        rows = boards.get(
            board_name,
            []
        )

        if isinstance(rows, list):
            stock_count += len(rows)

    return {

        "status": "ok",

        "source": "tindex.app",

        "message": (
            "مرحله اسکن با موفقیت اجرا شد."
        ),

        "daily_requests_used": (
            daily_requests_used()
        ),

        "daily_requests_remaining": (
            daily_requests_remaining()
        ),

        "market_date": data.get(
            "as_of"
        ),

        "breadth": data.get(
            "breadth",
            {}
        ),

        "detected_board_rows": stock_count,

        "next_step": (
            "پس از تأیید ساختار داده، "
            "اسکن کامل بازار ساخته می‌شود."
        )
    }
