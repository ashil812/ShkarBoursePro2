import os


def get_market_watch():
    return {
        "status": "ok",
        "environment_check": {
            "tindex_token": bool(os.getenv("TINDEX_TOKEN")),
            "test_render": bool(os.getenv("TEST_RENDER")),
            "total_environment_variables": len(os.environ)
        }
    }
