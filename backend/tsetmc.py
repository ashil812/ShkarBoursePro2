import os


def get_market_watch():
    env_keys = sorted(os.environ.keys())

    return {
        "status": "ok",
        "environment_check": {
            "tindex_token_key_found": "TINDEX_TOKEN" in env_keys,
            "total_environment_variables": len(env_keys)
        }
    }
