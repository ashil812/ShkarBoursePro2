import requests

BASE_URL = "https://cdn.tsetmc.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def get_market_watch():
    url = (
        f"{BASE_URL}/api/ClosingPrice/GetMarketWatch"
        "?market=0"
        "&industrialGroup="
        "&paperTypes%5B0%5D=1"
        "&paperTypes%5B1%5D=2"
        "&paperTypes%5B2%5D=3"
        "&paperTypes%5B3%5D=4"
        "&paperTypes%5B4%5D=5"
        "&paperTypes%5B5%5D=6"
        "&paperTypes%5B6%5D=7"
        "&paperTypes%5B7%5D=8"
        "&paperTypes%5B8%5D=9"
        "&showTraded=false"
        "&withBestLimits=false"
        "&hEven=0"
        "&RefID=0"
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if "marketwatch" in data:
            return {
                "status": "ok",
                "source": "TSETMC",
                "count": len(data["marketwatch"]),
                "data": data["marketwatch"]
            }

        return {
            "status": "ok",
            "source": "TSETMC",
            "data": data
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "source": "TSETMC",
            "message": str(e)
        }

    except ValueError:
        return {
            "status": "error",
            "source": "TSETMC",
            "message": "TSETMC returned invalid JSON",
            "response": response.text[:500]
        }
