import requests

BASE_URL = "https://cdn.tsetmc.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
}


def get_market_watch():
    url = f"{BASE_URL}/api/ClosingPrice/GetMarketWatch"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        return {
            "status": "ok",
            "http_status": response.status_code,
            "data": response.text[:2000]
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": str(e)
        }
