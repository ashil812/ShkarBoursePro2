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
