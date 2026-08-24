from fastapi import FastAPI
from tsetmc import get_market_watch

app = FastAPI(
    title="Shkar Bourse API",
    version="1.0.0"
)


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
    return get_market_watch()
