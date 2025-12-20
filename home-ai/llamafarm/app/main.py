# Placeholder for LlamaFarm orchestrator
from fastapi import FastAPI

app = FastAPI(title="LlamaFarm Orchestrator")

@app.get("/")
def root():
    return {"status": "llamafarm ok"}
