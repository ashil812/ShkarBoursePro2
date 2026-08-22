import requests


def get_market_watch():
    url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/فملی"

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=5
    )

    response.raise_for_status()

    return response.json()
