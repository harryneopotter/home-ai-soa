# Placeholder for Cognee API
from fastapi import FastAPI

app = FastAPI(title="Cognee Service")

@app.get("/")
def root():
    return {"status": "cognee ok"}
