import requests

BASE_URL = "https://cdn.tsetmc.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
}


def get_market_watch():
    try:
        response = requests.get(
            BASE_URL,
            headers=HEADERS,
            timeout=10
        )

        return {
            "status": "ok",
            "source": "TSETMC",
            "http_status": response.status_code,
            "message": "Connection to TSETMC works"
        }

    except Exception as e:
        return {
            "status": "error",
            "source": "TSETMC",
            "message": str(e)
        }
