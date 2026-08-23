import os
import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from tsetmc import get_market_watch

app = FastAPI(
title="Shkar Bourse API",
version="1.0.0"
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

```
try:
    response = requests.get(
        url,
        timeout=30
    )

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
```

@app.get("/market")
def market():
result = get_market_watch()

```
if result.get("status") == "error":
    raise HTTPException(
        status_code=502,
        detail=result
    )

return result
```

@app.get("/six-month-opportunities")
def six_month_opportunities():
return {
"status": "ok",
"section": "six_month_opportunities",
"title": "فرصت‌های سرمایه‌گذاری ۶ ماهه",
"warning": "درصد رشد، برآورد تحلیلی است و سود تضمینی نیست.",
"count": 10,
"opportunities": [
{
"rank_score": 87,
"ticker": "وبملت",
"name": "بانک ملت",
"sector": "بانک‌ها و موسسات اعتباری",
"current_price": 1397,
"target_price_6m": 1956,
"estimated_growth_percent": 40,
"risk": "متوسط",
"rank": 1
},
{
"rank_score": 87,
"ticker": "فولاد",
"name": "فولاد مبارکه اصفهان",
"sector": "فلزات اساسی",
"current_price": 2608,
"target_price_6m": 3651,
"estimated_growth_percent": 40,
"risk": "متوسط",
"rank": 2
},
{
"rank_score": 75,
"ticker": "عیار",
"name": "صندوق طلای عیار مفید",
"sector": "صندوق سرمایه‌گذاری قابل معامله",
"current_price": 611990,
"target_price_6m": 795587,
"estimated_growth_percent": 30,
"risk": "متوسط",
"rank": 3
},
{
"rank_score": 75,
"ticker": "طلا",
"name": "صندوق س. کالای پارسیان",
"sector": "صندوق سرمایه‌گذاری قابل معامله",
"current_price": 1547000,
"target_price_6m": 2011100,
"estimated_growth_percent": 30,
"risk": "متوسط",
"rank": 4
},
{
"rank_score": 70,
"ticker": "خودرو",
"name": "ایران خودرو",
"sector": "خودرو و ساخت قطعات",
"current_price": 666,
"target_price_6m": 813,
"estimated_growth_percent": 22,
"risk": "متوسط",
"rank": 5
},
{
"rank_score": 70,
"ticker": "خساپا",
"name": "سایپا",
"sector": "خودرو و ساخت قطعات",
"current_price": 657,
"target_price_6m": 802,
"estimated_growth_percent": 22,
"risk": "متوسط",
"rank": 6
},
{
"rank_score": 66,
"ticker": "وتجارت",
"name": "بانک تجارت",
"sector": "بانک‌ها و موسسات اعتباری",
"current_price": 875,
"target_price_6m": 1068,
"estimated_growth_percent": 22,
"risk": "متوسط",
"rank": 7
},
{
"rank_score": 65,
"ticker": "فیروزا",
"name": "صندوق ارمغان فیروزه آسیا-ثابت",
"sector": "صندوق سرمایه‌گذاری قابل معامله",
"current_price": 89042,
"target_price_6m": 108631,
"estimated_growth_percent": 22,
"risk": "متوسط",
"rank": 8
},
{
"rank_score": 65,
"ticker": "اهرم",
"name": "صندوق س سهامی کاریزما- اهرمی",
"sector": "صندوق سرمایه‌گذاری قابل معامله",
"current_price": 52170,
"target_price_6m": 63647,
"estimated_growth_percent": 22,
"risk": "متوسط",
"rank": 9
},
{
"rank_score": 65,
"ticker": "پاسارگاد",
"name": "صندوق س.درآمد ثابت پاسارگاد-د",
"sector": "صندوق سرمایه‌گذاری قابل معامله",
"current_price": 16894,
"target_price_6m": 20611,
"estimated_growth_percent": 22,
"risk": "متوسط",
"rank": 10
}
]
}

if **name** == "**main**":
port = int(os.environ.get("PORT", 8000))
uvicorn.run(
app,
host="0.0.0.0",
port=port
)
