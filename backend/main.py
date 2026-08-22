import os
import uvicorn
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


@app.get("/test")
def test():
    return {
        "status": "ok",
        "message": "Test endpoint works"
    }


@app.get("/market")
def market():
    result = get_market_watch()

    if result.get("status") == "error":
        raise HTTPException(
            status_code=502,
            detail=result
        )

    return result


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
