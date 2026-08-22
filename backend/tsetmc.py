import os
import requests

TSETMC_TOKEN = os.getenv("TSETMC_TOKEN")

BASE_URL = "https://cdn.tsetmc.com"


def get_market_watch():
    if not TSETMC_TOKEN:
        return {
            "status": "error",
            "message": "TSETMC_TOKEN is not configured"
        }

    url = f"{BASE_URL}/api/ClosingPrice/GetMarketWatch"

    headers = {
        "Authorization": f"Bearer {TSETMC_TOKEN}",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        return {
            "status": "ok",
            "http_status": response.status_code,
            "data": response.json()
        }

    except requests.RequestException as e:
        return {
            "status": "error",
            "message": str(e)
        }

    except ValueError:
        return {
            "status": "error",
            "message": "TSETMC returned invalid JSON",
            "response": response.text[:500]
        }
