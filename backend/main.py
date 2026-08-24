import os
import time
import requests
from fastapi import FastAPI

app = FastAPI(
    title="Shkar Bourse API",
    version="5.0.0"
)

TINDEX_OVERVIEW_URL = "https://tindex.app/api/public/stock-market/overview"

CACHE_SECONDS = 60
DAILY_LIMIT = 100

_cache_data = None
_cache_time = 0.0

_daily_requests = []
_last_error = None


# =========================
# Rate Limit
# =========================

def cleanup_daily_requests():
    global _daily_requests

    now = time.time()
    cutoff = now - 86400

    _daily_requests = [
        t for t in _daily_requests
        if t > cutoff
    ]


def daily_requests_used():
    cleanup_daily_requests()
    return len(_daily_requests)


def daily_requests_remaining():
    return max(
        0,
        DAILY_LIMIT - daily_requests_used()
    )


def can_request_tindex():
    cleanup_daily_requests()

    if len(_daily_requests) >= DAILY_LIMIT:
        return False, "سقف 100 درخواست در 24 ساعت مصرف شده است."

    if _daily_requests:
        elapsed = time.time() - _daily_requests[-1]

        if elapsed < CACHE_SECONDS:
            remaining = int(CACHE_SECONDS - elapsed) + 1

            return False, (
                f"برای درخواست بعدی باید {remaining} ثانیه صبر کنید."
            )

    return True, None


# =========================
# TIndex Request
# =========================

def get_token():
    return os.getenv("TINDEX_TOKEN", "").strip()


def request_tindex():
    global _last_error

    token = get_token()

    if not token:
        _last_error = "TINDEX_TOKEN تنظیم نشده است."

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
            "daily_requests_used": daily_requests_used(),
            "daily_requests_remaining": daily_requests_remaining()
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ShkarBoursePro2/5.0"
    }

    _daily_requests.append(time.time())

    try:
        response = requests.get(
            TINDEX_OVERVIEW_URL,
            headers=headers,
            timeout=30
        )

        if response.status_code == 401:
            _last_error = "توکن TIndex معتبر نیست."

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
            }

        if response.status_code == 429:
            _last_error = "محدودیت درخواست TIndex فعال شده است."

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error,
                "daily_requests_used": daily_requests_used(),
                "daily_requests_remaining": daily_requests_remaining()
            }

        response.raise_for_status()

        result = response.json()

        if not isinstance(result, dict):
            _last_error = "پاسخ TIndex ساختار معتبر ندارد."

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

            _last_error = str(message)

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
            }

        data = result.get("data")

        if not isinstance(data, dict):
            _last_error = "داده بازار در پاسخ TIndex پیدا نشد."

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
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
        _last_error = "پاسخ TIndex JSON معتبر نبود."

        return {
            "status": "error",
            "source": "tindex.app",
            "message": _last_error
        }


# =========================
# Market Cache
# =========================

def get_tindex_overview():
    global _cache_data
    global _cache_time

    now = time.time()

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
    _cache_time = time.time()

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": False,
        "data": _cache_data,
        "daily_requests_used": daily_requests_used(),
        "daily_requests_remaining": daily_requests_remaining()
    }


# =========================
# Helpers
# =========================

def safe_number(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def get_boards(data):
    if not isinstance(data, dict):
        return {}

    boards = data.get("boards", {})

    if not isinstance(boards, dict):
        return {}

    return boards


# =========================
# Scoring
# =========================

def calculate_short_term_score(stock):
    score = 0

    change = safe_number(
        stock.get("change_percent")
    )

    trade_value = safe_number(
        stock.get("trade_value")
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
        pe_value = safe_number(pe)

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

    return max(0, min(100, round(score)))


def calculate_six_month_score(stock):
    score = 0

    change = safe_number(
        stock.get("change_percent")
    )

    trade_value = safe_number(
        stock.get("trade_value")
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
        pe_value = safe_number(pe)

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

    return max(0, min(100, round(score)))


def build_reasons(stock):
    reasons = []

    change = safe_number(
        stock.get("change_percent")
    )

    trade_value = safe_number(
        stock.get("trade_value")
    )

    pe = stock.get("pe")

    if change >= 2:
        reasons.append("مومنتوم روزانه مثبت")
    elif change > 0:
        reasons.append("تغییر روزانه مثبت")

    if trade_value >= 10_000_000_000_000:
        reasons.append("ارزش معاملات بسیار بالا")
    elif trade_value >= 1_000_000_000_000:
        reasons.append("نقدشوندگی مناسب")

    if pe is not None:
        pe_value = safe_number(pe)

        if 0 < pe_value <= 10:
            reasons.append("P/E نسبتاً مناسب")
        elif pe_value > 30:
            reasons.append("P/E بالا")

    if not reasons:
        reasons.append("نیازمند بررسی عمیق‌تر")

    return reasons


# =========================
# Market Analysis
# =========================

def analyze_market(data):
    boards = get_boards(data)

    candidates = []
    seen = set()

    board_names = [
        "gainers",
        "losers",
        "most_active_value",
        "most_active_volume"
    ]

    for board_name in board_names:
        rows = boards.get(board_name, [])

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

            candidates.append({
                "ticker": ticker,
                "name": stock.get("name", "---"),
                "sector": stock.get("sector", "---"),
                "current_price": stock.get("last_price", 0),
                "change_percent": stock.get("change_percent", 0),
                "trade_value": stock.get("trade_value", 0),
                "pe": stock.get("pe"),
                "short_term_score": calculate_short_term_score(stock),
                "six_month_score": calculate_six_month_score(stock),
                "reasons": build_reasons(stock)
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


# =========================
# Routes
# =========================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Shkar Bourse API is running",
        "version": "5.0.0",
        "source": "tindex.app"
    }


@app.get("/health")
def health():
    cached_stocks = 0

    if isinstance(_cache_data, dict):
        boards = get_boards(_cache_data)

        for rows in boards.values():
            if isinstance(rows, list):
                cached_stocks += len(rows)

    total_symbols = None

    if isinstance(_cache_data, dict):
        breadth = _cache_data.get("breadth", {})

        if isinstance(breadth, dict):
            total_symbols = breadth.get("total")

    return {
        "status": "healthy",
        "source": "tindex.app",
        "cached_stocks": cached_stocks,
        "total_symbols": total_symbols,
        "daily_requests_used": daily_requests_used(),
        "daily_requests_remaining_local": daily_requests_remaining(),
        "last_error": _last_error
    }


@app.get("/market")
def market():
    return get_tindex_overview()


@app.get("/analysis")
def analysis():
    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": result.get("cached", False),
        "market_date": data.get("as_of"),
        "analysis": analyze_market(data),
        "warning": (
            "این موتور تحلیل نسخه اولیه است و سود مشخصی را تضمین نمی‌کند."
        )
    }


@app.get("/short-term-opportunities")
def short_term_opportunities():
    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]
    analyzed = analyze_market(data)

    opportunities = []

    for rank, stock in enumerate(
        analyzed["short_term_top_3"],
        start=1
    ):
        opportunities.append({
            "rank": rank,
            "score": stock["short_term_score"],
            "ticker": stock["ticker"],
            "name": stock["name"],
            "sector": stock["sector"],
            "current_price": stock["current_price"],
            "change_percent": stock["change_percent"],
            "trade_value": stock["trade_value"],
            "pe": stock["pe"],
            "reasons": stock["reasons"]
        })

    return {
        "status": "ok",
        "source": "tindex.app",
        "section": "short_term_opportunities",
        "title": "۳ فرصت برتر کوتاه‌مدت",
        "market_date": data.get("as_of"),
        "count": len(opportunities),
        "opportunities": opportunities,
        "warning": (
            "این رتبه‌بندی سیگنال اولیه است و تضمین سود نیست."
        )
    }


@app.get("/six-month-opportunities")
def six_month_opportunities():
    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]
    analyzed = analyze_market(data)

    opportunities = []

    for rank, stock in enumerate(
        analyzed["six_month_top_10"],
        start=1
    ):
        opportunities.append({
            "rank": rank,
            "score": stock["six_month_score"],
            "ticker": stock["ticker"],
            "name": stock["name"],
            "sector": stock["sector"],
            "current_price": stock["current_price"],
            "change_percent": stock["change_percent"],
            "trade_value": stock["trade_value"],
            "pe": stock["pe"],
            "reasons": stock["reasons"]
        })

    return {
        "status": "ok",
        "source": "tindex.app",
        "section": "six_month_opportunities",
        "title": "۱۰ فرصت برتر ۶ ماهه",
        "market_date": data.get("as_of"),
        "count": len(opportunities),
        "opportunities": opportunities,
        "warning": (
            "این رتبه‌بندی نسخه اولیه موتور تحلیل است و سود تضمینی نیست."
        )
    }


@app.get("/scanner/step")
def scanner_step():
    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]
    boards = get_boards(data)

    stock_count = 0

    for rows in boards.values():
        if isinstance(rows, list):
            stock_count += len(rows)

    return {
        "status": "ok",
        "source": "tindex.app",
        "message": "مرحله اسکن با موفقیت اجرا شد.",
        "market_date": data.get("as_of"),
        "daily_requests_used": daily_requests_used(),
        "daily_requests_remaining": daily_requests_remaining(),
        "breadth": data.get("breadth", {}),
        "detected_board_rows": stock_count,
        "next_step": "اسکن کامل بازار آماده توسعه است."
    }
