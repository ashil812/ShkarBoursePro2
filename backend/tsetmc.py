import requests


def get_market_watch():
    url = "https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx"

    try:
        response = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        return {
            "source": "TSETMC",
            "status_code": response.status_code,
            "raw_length": len(response.text),
            "raw_data": response.text[:5000]
        }

    except requests.exceptions.Timeout:
        return {
            "source": "TSETMC",
            "status": "timeout",
            "message": "TSETMC did not respond within 8 seconds"
        }

    except requests.exceptions.RequestException as e:
        return {
            "source": "TSETMC",
            "status": "connection_error",
            "message": str(e)
        }
