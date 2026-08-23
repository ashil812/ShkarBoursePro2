import os


def get_market_watch():
    return {
        "status": "ok",
        "environment_check": {
            "TINDEX_TOKEN": bool(os.getenv("TINDEX_TOKEN")),
            "TEST_RENDER": bool(os.getenv("TEST_RENDER")),
            "TOTAL_ENVIRONMENT_VARIABLES": len(os.environ)
        }
    }
