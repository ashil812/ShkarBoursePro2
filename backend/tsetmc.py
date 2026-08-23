import os
import requests


URL = "https://tindex.app/api/public/stock-market/overview"


def get_market_watch():
    token = os.getenv("TINDEX_TOKEN", "").strip()

    # تست Environment Variable
    if not token:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": "TINDEX_TOKEN پیدا نشد",
            "environment_check": {
                "token_exists": False
            }
        }

    # اگر توکن وجود دارد، فعلاً فقط آن را بررسی می‌کنیم
    return {
        "status": "ok",
        "source": "tindex.app",
        "message": "TINDEX_TOKEN با موفقیت از Render دریافت شد",
        "environment_check": {
            "token_exists": True,
            "token_length": len(token)
        }
    }
