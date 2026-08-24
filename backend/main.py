```python
from fastapi import FastAPI

from tsetmc import get_market_watch


app = FastAPI(
    title="Shkar Bourse API",
    version="4.0.0"
)


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


def calculate_short_term_score(stock):
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


def calculate_six_month_score(stock):
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
    elif change > 0:
        reasons.append(
            "تغییر روزانه مثبت"
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
        elif pe_value < 0:
            reasons.append(
                "P/E منفی"
            )

    if not reasons:
        reasons.append(
            "نیازمند بررسی عمیق‌تر"
        )

    return reasons


# =========================================================
# MARKET ANALYSIS
# =========================================================

def analyze_market(data):

    if not isinstance(data, dict):
        return {
            "short_term_top_3": [],
            "six_month_top_10": [],
            "candidate_count": 0
        }

    boards = data.get(
        "boards",
        {}
    )

    if not isinstance(boards, dict):
        boards = {}

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
                stock
            )

            six_score = calculate_six_month_score(
                stock
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
        key=lambda item: item["short_term_score"],
        reverse=True
    )[:3]

    six_month = sorted(
        candidates,
        key=lambda item: item["six_month_score"],
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
        "version": "4.0.0",
        "source": "tindex.app"
    }


@app.get("/health")
def health():

    try:

        result = get_market_watch()

        if result.get("status") != "ok":

            return {
                "status": "healthy",
                "source": "tindex.app",
                "tindex_status": "not_ready",
                "details": result
            }

        data = result.get(
            "data",
            {}
        )

        breadth = data.get(
            "breadth",
            {}
        )

        return {

            "status": "healthy",

            "source": "tindex.app",

            "tindex_status": "ok",

            "cached": result.get(
                "cached",
                False
            ),

            "market_date": data.get(
                "as_of"
            ),

            "total_symbols": breadth.get(
                "total_symbols"
            ),

            "quoted_symbols": breadth.get(
                "quoted_symbols"
            ),

            "advancing": breadth.get(
                "advancing"
            ),

            "declining": breadth.get(
                "declining"
            )
        }

    except Exception as e:

        return {
            "status": "healthy",
            "source": "tindex.app",
            "tindex_status": "error",
            "message": str(e)
        }


@app.get("/market")
def market():

    try:

        return get_market_watch()

    except Exception as e:

        return {
            "status": "error",
            "source": "backend",
            "message": str(e)
        }


@app.get("/analysis")
def analysis():

    try:

        result = get_market_watch()

        if result.get("status") != "ok":
            return result

        data = result.get(
            "data",
            {}
        )

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
                "این موتور تحلیل نسخه اولیه است "
                "و سود یا رشد مشخصی را تضمین نمی‌کند."
            )
        }

    except Exception as e:

        return {
            "status": "error",
            "source": "analysis",
            "message": str(e)
        }


@app.get("/six-month-opportunities")
def six_month_opportunities():

    try:

        result = get_market_watch()

        if result.get("status") != "ok":
            return result

        data = result.get(
            "data",
            {}
        )

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

                "score": stock[
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

                "risk": (
                    "نیازمند بررسی عمیق‌تر"
                ),

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

    except Exception as e:

        return {
            "status": "error",
            "source": "six-month-analysis",
            "message": str(e)
        }


@app.get("/short-term-opportunities")
def short_term_opportunities():

    try:

        result = get_market_watch()

        if result.get("status") != "ok":
            return result

        data = result.get(
            "data",
            {}
        )

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

    except Exception as e:

        return {
            "status": "error",
            "source": "short-term-analysis",
            "message": str(e)
        }


# =========================================================
# SCANNER
# =========================================================

@app.get("/scanner/step")
def scanner_step():

    try:

        result = get_market_watch()

        if result.get("status") != "ok":
            return result

        data = result.get(
            "data",
            {}
        )

        boards = data.get(
            "boards",
            {}
        )

        detected_rows = 0

        if isinstance(boards, dict):

            for rows in boards.values():

                if isinstance(rows, list):
                    detected_rows += len(rows)

        return {

            "status": "ok",

            "source": "tindex.app",

            "message": (
                "مرحله اسکن با موفقیت اجرا شد."
            ),

            "cached": result.get(
                "cached",
                False
            ),

            "market_date": data.get(
                "as_of"
            ),

            "breadth": data.get(
                "breadth",
                {}
            ),

            "detected_board_rows": detected_rows,

            "next_step": (
                "پس از تأیید داده، "
                "اسکن کامل بازار ساخته می‌شود."
            )
        }

    except Exception as e:

        return {
            "status": "error",
            "source": "scanner",
            "message": str(e)
        }
```
