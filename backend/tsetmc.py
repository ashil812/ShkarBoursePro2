import requests


def get_market_watch():
    try:
        response = requests.get(
            "https://example.com",
            timeout=10
        )

        return {
            "status": "ok",
            "http_status": response.status_code,
            "message": "Render internet connection works"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
