import os
import requests

URL = "https://tindex.app/api/public/stock-market/overview"


def get_market_watch():
    token = os.getenv("TINDEX_TOKEN", "").strip()

    if not token:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": "TINDEX_TOKEN در Environment Variables پیدا نشد"
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            URL,
            headers=headers,
            timeout=30
        )

        try:
            response_data = response.json()
        except ValueError:
            response_data = response.text[:2000]

        if response.status_code != 200:
            return {
                "status": "error",
                "source": "tindex.app",
                "http_status": response.status_code,
                "message": "TIndex API request failed",
                "response": response_data
            }

        return {
            "status": "ok",
            "source": "tindex.app",
            "http_status": response.status_code,
            "data": response_data
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": str(e)
        }
