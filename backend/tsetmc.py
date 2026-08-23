import os
import requests

URL = "https://tindex.app/api/public/stock-market/overview"

HEADERS = {
    "Authorization": f"Bearer {os.getenv('TINDEX_TOKEN', '')}",
    "Accept": "application/json",
}


def get_market_watch():
    try:
        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        payload = response.json()

        if not payload.get("success"):
            return {
                "status": "error",
                "source": "tindex.app",
                "message": payload.get("message", "TIndex API error"),
                "data": payload
            }

        return {
            "status": "ok",
            "source": "tindex.app",
            "data": payload.get("data")
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": str(e)
        }

    except ValueError as e:
        return {
            "status": "error",
            "source": "tindex.app",
            "message": f"Invalid JSON response: {str(e)}"
        }
