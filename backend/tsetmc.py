import requests

URL = "https://webgw.tse.ir/InstrumentProvider/api/v1/MarketWatch/MarketWatchCash/fa"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
}


def get_market_watch():
    try:
        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=15
        )

        return {
            "status": "ok",
            "http_status": response.status_code,
            "source": "webgw.tse.ir",
            "data": response.text[:5000]
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "source": "webgw.tse.ir",
            "message": str(e)
        }
