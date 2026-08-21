import requests

TSETMC_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"

def get_market_watch():
    response = requests.get(
        TSETMC_URL,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()
    return response.json()
