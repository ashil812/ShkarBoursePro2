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
        "User-Agent": "ShkarBoursePro2/1.0"
    }

    try:
        response = requests.get(
            URL,
            headers=headers,
            timeout=30
        )

        if response.status_code == 401:
            return {
                "status": "error",
                "source": "tindex.app",
                "message": "TIndex توکن را نپذیرفت (401 Unauthorized)"
            }

        response.raise_for_status()

        data = response.json()

        return {
            "status": "ok",
            "source": "tindex.app",
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
            "message": "پاسخ TIndex JSON معتبر نبود"
        }
