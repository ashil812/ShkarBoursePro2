import os
import uvicorn
from fastapi import FastAPI

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
    return {
        "status": "ok",
        "message": "Market endpoint is working"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
