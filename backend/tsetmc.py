import requests


def get_market_watch():
    url = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"

    params = {
        "market": 0,
        "industrialGroup": "",
        "paperTypes[0]": 1,
        "paperTypes[1]": 2,
        "paperTypes[2]": 3,
        "paperTypes[3]": 4,
        "paperTypes[4]": 5,
        "paperTypes[5]": 6,
        "paperTypes[6]": 7,
        "paperTypes[7]": 8,
        "paperTypes[8]": 9,
        "showTraded": "false",
        "withBestLimits": "false",
        "hEven": 0,
        "RefID": 0
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
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
            "status": "timeout",
            "message": "TSETMC CDN did not respond within 10 seconds"
        }

    except requests.exceptions.RequestException as e:
        return {
            "source": "TSETMC CDN",
            "status": "connection_error",
            "message": str(e)
        }

    except ValueError:
        return {
            "source": "TSETMC CDN",
            "status": "invalid_response",
            "message": response.text[:1000]
        }
