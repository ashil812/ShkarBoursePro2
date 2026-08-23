import os
import time
import requests


URL = "https://tindex.app/api/public/stock-market/overview"

CACHE_SECONDS = 60

_cache_data = None
_cache_time = 0


def get_market_watch():
    global _cache_data, _cache_time

    now = time.time()

    # اگر داده کش‌شده هنوز معتبر است
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
            "source": "tindex.app",
            "message": "TINDEX_TOKEN پیدا نشد"
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ShkarBoursePro2/1.0"
    }

    try:
        response = requests.get(
            URL,
            headers=headers,
            timeout=30
        )

        if response.status_code == 429:
            return {
                "status": "error",
                "source": "tindex.app",
                "message": "TIndex محدودیت درخواست اعمال کرده؛ لطفاً حداقل 60 ثانیه صبر کنید."
            }

        if response.status_code == 401:
            return {
                "status": "error",
                "source": "tindex.app",
                "message": "توکن TIndex معتبر نیست."
            }

        response.raise_for_status()

        data = response.json()

        # ذخیره داده برای 60 ثانیه
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
            "source": "tindex.app",
            "message": str(e)
        }

    except ValueError:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": "پاسخ TIndex JSON معتبر نبود."
        }
