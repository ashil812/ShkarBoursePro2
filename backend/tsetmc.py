import os


def get_market_watch():
    return {
        "status": "ok",
        "environment_check": {
            "TINDEX_TOKEN_TEST": bool(os.getenv("TINDEX_TOKEN_TEST")),
            "TOTAL_ENVIRONMENT_VARIABLES": len(os.environ)
        }
    }
