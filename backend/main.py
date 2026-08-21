from fastapi import FastAPI, HTTPException
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
    try:
        data = get_market_watch()

        return {
            "status": "ok",
            "data": data
        }

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Market data error: {str(e)}"
        )
