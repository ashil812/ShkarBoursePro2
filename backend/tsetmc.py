import os
import time
import requests


TINDEX_URL = "https://tindex.app/api/public/stock-market/overview"

# محدودیت‌های TIndex
MIN_REQUEST_INTERVAL = 60       # حداقل 60 ثانیه بین درخواست‌ها
MAX_DAILY_REQUESTS = 100

# کش محلی
_cache_data = None
_cache_time = 0

# کنترل درخواست‌ها
_last_request_time = 0
_daily_requests_used = 0
_daily_date = None

_last_error = None


def _reset_daily_counter():
    global _daily_requests_used
    global _daily_date

    today = time.strftime("%Y-%m-%d")

    if _daily_date != today:
        _daily_date = today
        _daily_requests_used = 0


def _can_request():
    global _last_request_time
    global _daily_requests_used

    _reset_daily_counter()

    now = time.time()

    # محدودیت روزانه
    if _daily_requests_used >= MAX_DAILY_REQUESTS:
        return False, (
            "سقف 100 درخواست روزانه TIndex "
            "برای این سرویس محلی مصرف شده است."
        )

    # محدودیت یک درخواست در دقیقه
    if _last_request_time > 0:
        elapsed = now - _last_request_time

        if elapsed < MIN_REQUEST_INTERVAL:
            remaining = int(
                MIN_REQUEST_INTERVAL - elapsed
            )

            return False, (
                f"برای درخواست بعدی باید "
                f"{remaining} ثانیه صبر کنیم."
            )

    return True, None


def _request_tindex():
    global _last_request_time
    global _daily_requests_used
    global _last_error

    token = os.getenv("TINDEX_TOKEN", "").strip()

    if not token:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": "TINDEX_TOKEN پیدا نشد."
        }

    allowed, error_message = _can_request()

    if not allowed:
        return {
            "status": "error",
            "source": "local-rate-limit",
            "message": error_message,
            "daily_requests_used": _daily_requests_used,
            "daily_requests_remaining": max(
                0,
                MAX_DAILY_REQUESTS - _daily_requests_used
            )
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ShkarBoursePro2/2.0"
    }

    try:
        # درخواست واقعی به TIndex
        _last_request_time = time.time()
        _daily_requests_used += 1

        response = requests.get(
            TINDEX_URL,
            headers=headers,
            timeout=30
        )

        if response.status_code == 429:
            _last_error = "TIndex rate limit"

            return {
                "status": "error",
                "source": "tindex.app",
                "message": (
                    "TIndex درخواست را به دلیل "
                    "محدودیت Rate Limit رد کرد."
                ),
                "daily_requests_used": _daily_requests_used,
                "daily_requests_remaining": max(
                    0,
                    MAX_DAILY_REQUESTS - _daily_requests_used
                )
            }

        if response.status_code == 401:
            _last_error = "Invalid TINDEX_TOKEN"

            return {
                "status": "error",
                "source": "tindex.app",
                "message": "توکن TIndex معتبر نیست."
            }

        response.raise_for_status()

        result = response.json()

        if not isinstance(result, dict):
            _last_error = "Invalid response format"

            return {
                "status": "error",
                "source": "tindex.app",
                "message": "فرمت پاسخ TIndex معتبر نیست."
            }

        if result.get("success") is False:
            _last_error = result.get(
                "message",
                "TIndex پاسخ موفقی ارسال نکرد."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
            }

        # پاسخ TIndex معمولاً شامل data است
        data = result.get("data", result)

        if not data:
            _last_error = "Empty market data"

            return {
                "status": "error",
                "source": "tindex.app",
                "message": "داده بازار از TIndex دریافت نشد."
            }

        _last_error = None

        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": False,
            "data": data,
            "daily_requests_used": _daily_requests_used,
            "daily_requests_remaining": max(
                0,
                MAX_DAILY_REQUESTS - _daily_requests_used
            )
        }

    except requests.exceptions.RequestException as e:
        _last_error = str(e)

        return {
            "status": "error",
            "source": "tindex.app",
            "message": f"خطا در اتصال به TIndex: {str(e)}",
            "daily_requests_used": _daily_requests_used,
            "daily_requests_remaining": max(
                0,
                MAX_DAILY_REQUESTS - _daily_requests_used
            )
        }

    except ValueError:
        _last_error = "Invalid JSON"

        return {
            "status": "error",
            "source": "tindex.app",
            "message": "پاسخ TIndex JSON معتبر نبود."
        }


def get_market_watch():
    global _cache_data
    global _cache_time

    now = time.time()

    _reset_daily_counter()

    # اگر کش موجود باشد، اصلاً به TIndex درخواست نمی‌زنیم.
    if _cache_data is not None:
        return {
            "status": "ok",
            "source": "tindex.app",
            "cached": True,
            "data": _cache_data,
            "daily_requests_used": _daily_requests_used,
            "daily_requests_remaining": max(
                0,
                MAX_DAILY_REQUESTS - _daily_requests_used
            )
        }

    # اولین دریافت
    result = _request_tindex()

    if result["status"] == "ok":
        _cache_data = result["data"]
        _cache_time = now

    return result


def refresh_market_watch():
    """
    دریافت دستی داده جدید.
    فقط در صورت عبور از محدودیت 60 ثانیه
    و سقف روزانه درخواست ارسال می‌شود.
    """

    global _cache_data
    global _cache_time

    _reset_daily_counter()

    result = _request_tindex()

    if result["status"] == "ok":
        _cache_data = result["data"]
        _cache_time = time.time()

    return result


def get_status():
    _reset_daily_counter()

    return {
        "status": "healthy",
        "source": "tindex.app",
        "cached": _cache_data is not None,
        "cache_age_seconds": (
            round(time.time() - _cache_time)
            if _cache_data is not None
            else None
        ),
        "daily_requests_used": _daily_requests_used,
        "daily_requests_remaining": max(
            0,
            MAX_DAILY_REQUESTS - _daily_requests_used
        ),
        "last_error": _last_error
    }
