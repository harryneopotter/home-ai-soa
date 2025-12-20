# Placeholder for Memori API
from fastapi import FastAPI

app = FastAPI(title="Memori Service")

@app.get("/")
def root():
    return {"status": "memori ok"}
