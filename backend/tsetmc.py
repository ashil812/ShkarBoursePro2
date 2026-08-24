import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


TINDEX_BASE_URL = "https://tindex.app/api/public"

OVERVIEW_URL = (
    f"{TINDEX_BASE_URL}/stock-market/overview"
)

STOCKS_URL = (
    f"{TINDEX_BASE_URL}/stocks/by-category/stock-energy"
)


# =========================================================
# SETTINGS
# =========================================================

DAILY_LIMIT = 100

# فاصله واقعی بین درخواست‌ها
REQUEST_INTERVAL = 75

# شروع بازار
MARKET_START_HOUR = 9
MARKET_START_MINUTE = 0

# پایان جمع‌آوری
MARKET_END_HOUR = 12
MARKET_END_MINUTE = 30


# =========================================================
# GLOBAL STATE
# =========================================================

_last_request_time = 0.0
_daily_requests_used = 0
_daily_date = None
_last_error = None

_state_lock = threading.Lock()


# =========================================================
# TIME
# =========================================================

def tehran_now():
    return datetime.now(
        ZoneInfo("Asia/Tehran")
    )


def trading_date():
    now = tehran_now()

    return now.strftime(
        "%Y-%m-%d"
    )


def is_trading_day():
    """
    شنبه تا چهارشنبه
    """

    return tehran_now().weekday() in (
        5,  # Saturday
        6,  # Sunday
        0,  # Monday
        1,  # Tuesday
        2   # Wednesday
    )


def market_start_datetime():

    now = tehran_now()

    return now.replace(
        hour=MARKET_START_HOUR,
        minute=MARKET_START_MINUTE,
        second=0,
        microsecond=0
    )


def first_request_datetime():

    return (
        market_start_datetime()
        .replace(
            second=0,
            microsecond=0
        )
        + __import__("datetime").timedelta(
            seconds=REQUEST_INTERVAL
        )
    )


def is_market_time():

    if not is_trading_day():
        return False

    now = tehran_now()

    start = market_start_datetime()

    end = now.replace(
        hour=MARKET_END_HOUR,
        minute=MARKET_END_MINUTE,
        second=0,
        microsecond=0
    )

    return start <= now <= end


def is_first_request_time_reached():

    if not is_trading_day():
        return False

    return tehran_now() >= first_request_datetime()


def seconds_until_first_request():

    if not is_trading_day():
        return 0

    now = tehran_now()
    target = first_request_datetime()

    if now >= target:
        return 0

    return max(
        0,
        int(
            (target - now).total_seconds()
        )
    )


# =========================================================
# DAILY COUNTER
# =========================================================

def _reset_daily_counter():

    global _daily_requests_used
    global _daily_date
    global _last_request_time

    today = trading_date()

    with _state_lock:

        if _daily_date != today:

            _daily_date = today
            _daily_requests_used = 0

            # مهم:
            # روز جدید فاصله درخواست قبلی را به ارث نمی‌برد.
            _last_request_time = 0.0


def daily_requests_used():

    _reset_daily_counter()

    with _state_lock:
        return _daily_requests_used


def daily_requests_remaining():

    return max(
        0,
        DAILY_LIMIT
        - daily_requests_used()
    )


# =========================================================
# REQUEST TIMING
# =========================================================

def seconds_until_next_request():

    _reset_daily_counter()

    with _state_lock:

        last_request = (
            _last_request_time
        )

    # اولین درخواست هر روز:
    # دقیقاً 75 ثانیه بعد از 09:00
    if last_request <= 0:

        return seconds_until_first_request()

    elapsed = (
        time.time()
        - last_request
    )

    remaining = (
        REQUEST_INTERVAL
        - elapsed
    )

    if remaining <= 0:
        return 0

    return int(remaining) + 1


def can_request_tindex():

    _reset_daily_counter()

    # خارج از روز معاملاتی
    if not is_trading_day():

        return (
            False,
            "امروز روز معاملاتی نیست."
        )

    # قبل از شروع بازار
    if not is_market_time():

        return (
            False,
            "در حال حاضر خارج از زمان بازار است."
        )

    # اولین درخواست
    if (
        _last_request_time <= 0
        and not is_first_request_time_reached()
    ):

        wait = (
            seconds_until_first_request()
        )

        return (
            False,
            (
                "اولین درخواست باید "
                "75 ثانیه بعد از شروع بازار ارسال شود. "
                f"{wait} ثانیه باقی مانده."
            )
        )

    # سقف روزانه
    if daily_requests_used() >= DAILY_LIMIT:

        return (
            False,
            "سقف 100 درخواست امروز مصرف شده است."
        )

    # فاصله درخواست‌ها
    wait = seconds_until_next_request()

    if wait > 0:

        return (
            False,
            (
                "برای درخواست بعدی باید "
                f"{wait} ثانیه صبر شود."
            )
        )

    return True, None


# =========================================================
# HEADERS
# =========================================================

def get_headers():

    token = os.getenv(
        "TINDEX_TOKEN",
        ""
    ).strip()

    if not token:
        return None

    return {
        "Authorization": (
            f"Bearer {token}"
        ),
        "Accept": "application/json",
        "User-Agent": (
            "ShkarBoursePro2/10.0"
        )
    }


# =========================================================
# REQUEST
# =========================================================

def make_tindex_request(
    url,
    params=None
):

    global _last_error
    global _last_request_time
    global _daily_requests_used

    headers = get_headers()

    if headers is None:

        _last_error = (
            "TINDEX_TOKEN تنظیم نشده است."
        )

        return {
            "status": "error",
            "source": "tindex.app",
            "message": _last_error
        }

    allowed, reason = (
        can_request_tindex()
    )

    if not allowed:

        return {
            "status": "error",
            "source": "local-rate-limit",
            "message": reason,
            "wait_seconds": (
                seconds_until_next_request()
            ),
            "daily_requests_used": (
                daily_requests_used()
            ),
            "daily_requests_remaining": (
                daily_requests_remaining()
            )
        }

    request_time = time.time()

    with _state_lock:

        _last_request_time = (
            request_time
        )

        _daily_requests_used += 1

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )

        if response.status_code == 401:

            _last_error = (
                "توکن TIndex معتبر نیست."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error,
                "daily_requests_used": (
                    daily_requests_used()
                ),
                "daily_requests_remaining": (
                    daily_requests_remaining()
                )
            }

        if response.status_code == 429:

            _last_error = (
                "محدودیت درخواست TIndex فعال شده است."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error,
                "daily_requests_used": (
                    daily_requests_used()
                ),
                "daily_requests_remaining": (
                    daily_requests_remaining()
                )
            }

        response.raise_for_status()

        result = response.json()

        if not isinstance(
            result,
            dict
        ):

            _last_error = (
                "پاسخ TIndex معتبر نیست."
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
            }

        if result.get(
            "success"
        ) is False:

            _last_error = str(
                result.get(
                    "message",
                    "TIndex پاسخ موفقی ارسال نکرد."
                )
            )

            return {
                "status": "error",
                "source": "tindex.app",
                "message": _last_error
            }

        _last_error = None

        return {
            "status": "ok",
            "source": "tindex.app",
            "data": result.get(
                "data"
            ),
            "meta": result.get(
                "meta"
            ),
            "daily_requests_used": (
                daily_requests_used()
            ),
            "daily_requests_remaining": (
                daily_requests_remaining()
            )
        }

    except requests.exceptions.RequestException as exc:

        _last_error = str(
            exc
        )

        return {
            "status": "error",
            "source": "tindex.app",
            "message": (
                "خطا در اتصال به TIndex: "
                + str(exc)
            ),
            "daily_requests_used": (
                daily_requests_used()
            ),
            "daily_requests_remaining": (
                daily_requests_remaining()
            )
        }

    except ValueError:

        _last_error = (
            "پاسخ TIndex JSON معتبر نبود."
        )

        return {
            "status": "error",
            "source": "tindex.app",
            "message": _last_error,
            "daily_requests_used": (
                daily_requests_used()
            ),
            "daily_requests_remaining": (
                daily_requests_remaining()
            )
        }


# =========================================================
# OVERVIEW
# =========================================================

def get_market_watch():

    return make_tindex_request(
        OVERVIEW_URL
    )


def refresh_market_watch():

    return make_tindex_request(
        OVERVIEW_URL
    )


# =========================================================
# STATUS
# =========================================================

def get_status():

    _reset_daily_counter()

    return {
        "status": "healthy",
        "source": "tindex.app",
        "market_start": "09:00",
        "first_request_after_seconds": 75,
        "request_interval_seconds": (
            REQUEST_INTERVAL
        ),
        "daily_limit": DAILY_LIMIT,
        "daily_requests_used": (
            daily_requests_used()
        ),
        "daily_requests_remaining": (
            daily_requests_remaining()
        ),
        "seconds_until_next_request": (
            seconds_until_next_request()
        ),
        "last_request_time": (
            time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(
                    _last_request_time
                )
            )
            if _last_request_time > 0
            else None
        ),
        "last_error": _last_error
    }
