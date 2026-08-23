import os
import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from tsetmc import get_market_watch

app = FastAPI(
    title="Shkar Bourse API",
    version="1.1.0"
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Shkar Bourse API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/test")
def test():
    return {
        "status": "ok",
        "message": "Test endpoint works"
    }


@app.get("/connection-test")
def connection_test():
    url = "https://webgw.tse.ir/InstrumentProvider/api/v1/MarketWatch/MarketWatchCash/fa"

    try:
        response = requests.get(url, timeout=30)

        return {
            "status": "ok",
            "http_status": response.status_code,
            "message": "Connection successful",
            "response_preview": response.text[:500]
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/market")
def market():
    result = get_market_watch()

    if result.get("status") == "error":
        raise HTTPException(
            status_code=502,
            detail=result
        )

    return result


@app.get("/six-month-opportunities")
def six_month_opportunities():
    """
    فرصت‌های سرمایه‌گذاری ۶ ماهه

    توجه:
    درصد رشد در این نسخه «پتانسیل تخمینی» است
    و به معنی سود تضمینی نیست.
    """

    result = get_market_watch()

    if result.get("status") == "error":
        raise HTTPException(
            status_code=502,
            detail=result
        )

    data = result.get("data", {})

    # ساختار پاسخ TIndex
    market_data = data.get("data", data)

    boards = market_data.get("boards", {})
    most_active_value = boards.get("most_active_value", [])
    most_active_volume = boards.get("most_active_volume", [])

    # ترکیب نمادهای مهم بازار
    symbols = {}

    for item in most_active_value:
        ticker = item.get("ticker")

        if ticker:
            symbols[ticker] = item

    for item in most_active_volume:
        ticker = item.get("ticker")

        if ticker:
            if ticker not in symbols:
                symbols[ticker] = item

    opportunities = []

    for ticker, item in symbols.items():

        price = item.get("last_price")
        change_percent = item.get("change_percent", 0)
        trade_value = item.get("trade_value", 0)
        pe = item.get("pe")

        if not price:
            continue

        score = 50
        reasons = []

        # مومنتوم قیمت
        if change_percent > 2:
            score += 10
            reasons.append("مومنتوم کوتاه‌مدت مثبت")
        elif change_percent < -2:
            score -= 5

        # ارزش معاملات
        if trade_value >= 10_000_000_000_000:
            score += 15
            reasons.append("ارزش معاملات بسیار بالا")
        elif trade_value >= 5_000_000_000_000:
            score += 10
            reasons.append("ارزش معاملات بالا")

        # P/E
        if isinstance(pe, (int, float)):
            if 1 <= pe <= 8:
                score += 12
                reasons.append("P/E نسبتاً مناسب")
            elif 8 < pe <= 12:
                score += 6
                reasons.append("P/E قابل قبول")
            elif pe > 30:
                score -= 8
                reasons.append("P/E بالا")

        # محدود کردن امتیاز
        score = max(0, min(100, score))

        # برآورد پتانسیل رشد
        if score >= 85:
            potential = 40
            risk = "متوسط"
        elif score >= 75:
            potential = 30
            risk = "متوسط"
        elif score >= 65:
            potential = 22
            risk = "متوسط"
        else:
            potential = 15
            risk = "بالا"

        target_price = round(price * (1 + potential / 100))

        opportunities.append({
            "rank_score": score,
            "ticker": ticker,
            "name": item.get("name"),
            "sector": item.get("sector"),
            "current_price": price,
            "target_price_6m": target_price,
            "estimated_growth_percent": potential,
            "risk": risk,
            "change_percent": change_percent,
            "trade_value": trade_value,
            "pe": pe,
            "reasons": reasons
        })

    # مرتب‌سازی بر اساس امتیاز
    opportunities.sort(
        key=lambda x: (
            x["rank_score"],
            x["estimated_growth_percent"],
            x["trade_value"]
        ),
        reverse=True
    )

    # فقط 10 فرصت برتر
    top_10 = opportunities[:10]

    # شماره رتبه
    for index, item in enumerate(top_10, start=1):
        item["rank"] = index

    return {
        "status": "ok",
        "section": "six_month_opportunities",
        "title": "فرصت‌های سرمایه‌گذاری ۶ ماهه",
        "warning": "درصد رشد، برآورد تحلیلی است و سود تضمینی نیست.",
        "count": len(top_10),
        "opportunities": top_10
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
