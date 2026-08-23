from fastapi import FastAPI

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
                "change_percent": 2.95,
                "trade_value": 16375040313207,
                "pe": 3.1,
                "reasons": [
                    "مومنتوم کوتاه‌مدت مثبت",
                    "ارزش معاملات بسیار بالا",
                    "P/E نسبتاً مناسب"
                ],
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
                "change_percent": 2.96,
                "trade_value": 13740663451477,
                "pe": 5,
                "reasons": [
                    "مومنتوم کوتاه‌مدت مثبت",
                    "ارزش معاملات بسیار بالا",
                    "P/E نسبتاً مناسب"
                ],
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
                "change_percent": 3.78,
                "trade_value": 49413771956585,
                "pe": None,
                "reasons": [
                    "مومنتوم کوتاه‌مدت مثبت",
                    "ارزش معاملات بسیار بالا"
                ],
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
                "change_percent": 3.78,
                "trade_value": 13120029429798,
                "pe": None,
                "reasons": [
                    "مومنتوم کوتاه‌مدت مثبت",
                    "ارزش معاملات بسیار بالا"
                ],
                "rank": 4
            },
            {
                "rank_score": 70,
                "ticker": "خودرو",
                "name": "ایران‌خودرو",
                "sector": "خودرو و ساخت قطعات",
                "current_price": 666,
                "target_price_6m": 813,
                "estimated_growth_percent": 22,
                "risk": "متوسط",
                "change_percent": 2.94,
                "trade_value": 9007630418254,
                "pe": -13.6,
                "reasons": [
                    "مومنتوم کوتاه‌مدت مثبت",
                    "ارزش معاملات بالا"
                ],
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
                "change_percent": 2.02,
                "trade_value": 6463174284855,
                "pe": -4.3,
                "reasons": [
                    "مومنتوم کوتاه‌مدت مثبت",
                    "ارزش معاملات بالا"
                ],
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
                "change_percent": 2.94,
                "trade_value": 3162907481125,
                "pe": 8.3,
                "reasons": [
                    "مومنتوم کوتاه‌مدت مثبت",
                    "P/E قابل قبول"
                ],
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
                "change_percent": 0.14,
                "trade_value": 17390043962552,
                "pe": None,
                "reasons": [
                    "ارزش معاملات بسیار بالا"
                ],
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
                "change_percent": -1.58,
                "trade_value": 16766541059262,
                "pe": None,
                "reasons": [
                    "ارزش معاملات بسیار بالا"
                ],
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
                "change_percent": 0.14,
                "trade_value": 16227890626689,
                "pe": None,
                "reasons": [
                    "ارزش معاملات بسیار بالا"
                ],
                "rank": 10
            }
        ]
    }
