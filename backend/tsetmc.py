import requests

TSETMC_URL = "https://cdn.tsetmc.com"


def get_market_watch():
    try:
        response = requests.get(
            TSETMC_URL,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=10
        )

        return {
            "status": "ok",
            "http_status": response.status_code,
            "message": "Connection to TSETMC CDN successful"
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": str(e)
        }
