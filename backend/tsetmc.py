import requests


def get_market_watch():
    url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/فملی"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )

        return {
            "source": "TSETMC CDN",
            "status_code": response.status_code,
            "data": response.json()
        }

    except requests.exceptions.Timeout:
        return {
            "source": "TSETMC CDN",
            "status": "timeout"
        }

    except Exception as e:
        return {
            "source": "TSETMC CDN",
            "status": "error",
            "message": str(e)
        }
