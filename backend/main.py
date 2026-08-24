```python
import os
import time
import requests
from fastapi import FastAPI

app = FastAPI(
    title="Shkar Bourse API",
    version="2.0.0"
)

TINDEX_URL = "https://tindex.app/api/public/stock-market/overview"

CACHE_SECONDS = 60

_cache_data = None
_cache_time = 0


def get_tindex_overview():
    global _cache_data, _cache_time

    now = time.time()

    if _cache_data is not None and (now - _cache_time) < CACHE_SECONDS:
        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": True,
            "data": _cache_data
        }

    token = os.getenv("TINDEX_TOKEN", "").strip()

    if not token:
        return {
            "status": "error",
            "message": "TINDEX_TOKEN پیدا نشد."
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ShkarBoursePro2/2.0"
    }

    try:
        response = requests.get(
            TINDEX_URL,
            headers=headers,
            timeout=30
        )

        if response.status_code == 429:
            return {
                "status": "error",
                "message": "محدودیت درخواست TIndex فعال شده است. لطفاً کمی صبر کنید."
            }

        if response.status_code == 401:
            return {
                "status": "error",
                "message": "توکن TIndex معتبر نیست."
            }

        response.raise_for_status()

        result = response.json()

        if not result.get("success"):
            return {
                "status": "error",
                "message": result.get(
                    "message",
                    "TIndex پاسخ موفقی ارسال نکرد."
                )
            }

        data = result.get("data")

        if not data:
            return {
                "status": "error",
                "message": "داده بازار از TIndex دریافت نشد."
            }

        _cache_data = data
        _cache_time = now

        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": False,
            "data": data
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


def safe_number(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def calculate_short_term_score(stock, market_data):
    """
    امتیاز اولیه برای فرصت ۱ تا ۲ ماهه.

    این نسخه هنوز پیش‌بینی قطعی دو برابر شدن نیست.
    فقط برای ساخت موتور رتبه‌بندی اولیه استفاده می‌شود.
    """

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

    market_change = 0.0

    for index in market_data.get("indices", []):
        name = str(index.get("name", ""))

        if "کل" in name:
            market_change = safe_number(
                index.get("change_percent"),
                0
            )
            break

    # مومنتوم روزانه
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

    # نقدشوندگی
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

    # مقایسه با وضعیت بازار
    if change > market_change:
        score += 10
    elif change < market_change - 2:
        score -= 5

    # سقف امتیاز
    return max(0, min(100, round(score)))


def calculate_six_month_score(stock, market_data):
    """
    امتیاز اولیه سرمایه‌گذاری ۶ ماهه.
    """

    score = 0.0

    change = safe_number(
        stock.get("change_percent"),
        0
    )

    trade_value = safe_number(
        stock.get("trade_value"),
        0
    )

    market_change = 0.0

    for index in market_data.get("indices", []):
        name = str(index.get("name", ""))

        if "کل" in name:
            market_change = safe_number(
                index.get("change_percent"),
                0
            )
            break

    # نقدشوندگی
    if trade_value >= 10_000_000_000_000:
        score += 25
    elif trade_value >= 5_000_000_000_000:
        score += 20
    elif trade_value >= 1_000_000_000_000:
        score += 14
    elif trade_value >= 100_000_000_000:
        score += 7

    # مومنتوم
    if change >= 3:
        score += 15
    elif change >= 2:
        score += 12
    elif change >= 1:
        score += 8
    elif change > 0:
        score += 4

    # P/E
    pe = stock.get("pe")

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

    # قدرت نسبت به بازار
    if change > market_change:
        score += 15
    elif change >= market_change:
        score += 8

    return max(0, min(100, round(score)))


def build_reasons(stock, score_type):
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
        reasons.append("مومنتوم روزانه مثبت و قدرتمند")
    elif change > 0:
        reasons.append("مومنتوم روزانه مثبت")

    if trade_value >= 10_000_000_000_000:
        reasons.append("ارزش معاملات بسیار بالا")
    elif trade_value >= 1_000_000_000_000:
        reasons.append("نقدشوندگی مناسب")

    if pe is not None:
        pe_value = safe_number(pe, 0)

        if 0 < pe_value <= 10:
            reasons.append("P/E در محدوده نسبتاً مناسب")
        elif pe_value > 30:
            reasons.append("P/E بالا؛ ریسک ارزش‌گذاری")

    if not reasons:
        reasons.append("نیازمند بررسی عمیق‌تر")

    return reasons


def analyze_market(data):
    boards = data.get("boards", {})

    candidates = []

    board_names = [
        "gainers",
        "most_active_value",
        "most_active_volume"
    ]

    seen = set()

    for board_name in board_names:

        rows = boards.get(board_name, [])

        for stock in rows:

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

            six_month_score = calculate_six_month_score(
                stock,
                data
            )

            candidates.append({
                "ticker": ticker,
                "name": stock.get("name", "---"),
                "sector": stock.get("sector", "---"),
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
                "pe": stock.get("pe"),
                "short_term_score": short_score,
                "six_month_score": six_month_score,
                "short_term_reasons": build_reasons(
                    stock,
                    "short"
                ),
                "six_month_reasons": build_reasons(
                    stock,
                    "six"
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
        "six_month_top_10": six_month
    }


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Shkar Bourse API is running",
        "version": "2.0.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "source": "tindex.app"
    }


@app.get("/market")
def market():
    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    return result


@app.get("/analysis")
def analysis():
    result = get_tindex_overview()

    if result["status"] != "ok":
        return result

    data = result["data"]

    analyzed = analyze_market(data)

    return {
        "status": "ok",
        "source": "tindex.app",
        "cached": result.get("cached", False),
        "market_date": data.get("as_of"),
        "analysis": analyzed,
        "warning": (
            "این امتیازها سیگنال تحلیلی هستند و "
            "سود یا رشد مشخصی را تضمین نمی‌کنند."
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
            "rank_score": stock["six_month_score"],
            "ticker": stock["ticker"],
            "name": stock["name"],
            "sector": stock["sector"],
            "current_price": stock["current_price"],
            "change_percent": stock["change_percent"],
            "trade_value": stock["trade_value"],
            "pe": stock["pe"],
            "risk": "نیازمند بررسی عمیق‌تر",
            "reasons": stock["six_month_reasons"]
        })

    return {
        "status": "ok",
        "source": "tindex.app",
        "section": "six_month_opportunities",
        "title": "۱۰ فرصت برتر سرمایه‌گذاری ۶ ماهه",
        "market_date": data.get("as_of"),
        "count": len(opportunities),
        "opportunities": opportunities,
        "warning": (
            "این رتبه‌بندی نسخه اولیه موتور تحلیل است "
            "و سود تضمینی نیست."
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
            "reasons": stock["short_term_reasons"]
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
            "این رتبه‌بندی سیگنال اولیه است و "
            "به معنی تضمین دو برابر شدن قیمت نیست."
        )
    }
```
