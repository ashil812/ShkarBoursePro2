import requests


def get_market_watch():
    url = "https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx"

    response = requests.get(
        url,
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    return {
        "source": "TSETMC",
        "raw_length": len(response.text),
        "raw_data": response.text[:5000]
    }
