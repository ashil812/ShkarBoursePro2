import os
import uvicorn
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Shkar Bourse API",
    version="1.0.0"
)

TSETMC_TOKEN = os.getenv("TSETMC_TOKEN")


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Shkar Bourse API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/market")
def market():
    if not TSETMC_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="TSETMC_TOKEN is not configured"
        )

    return {
        "status": "ok",
        "message": "TSETMC token is configured"
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
