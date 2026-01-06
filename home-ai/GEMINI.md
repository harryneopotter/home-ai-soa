# Project Overview

This project is a local-only home assistant agent called `SOA1` ("Son of Anton"). It's designed to run on a private server and provides a conversational AI interface while ensuring user data remains entirely offline.

The core functionality revolves around a `SOA1Agent` that can:
- Receive user queries through a FastAPI-based REST API.
- Access a long-term memory system (`MemLayer`) to store and retrieve user-specific facts and conversation history.
- Use a local large language model (`Ollama`) to generate intelligent and context-aware responses.
- Delegate complex financial analysis to a specialized `Phinance` pipeline using a hybrid calculation engine.
- Ground its answers in stored memories to provide personalized and relevant assistance.

**Key Technologies:**
- **Backend:** Python 3.10+, FastAPI
- **AI Models:** Ollama (`NemoAgent:latest`, `phinance-json:latest`, `qwen2.5:7b-instruct`)
- **Memory:** MemLayer (Current), MemGraph (Planned)
- **Dependencies:** `fastapi`, `uvicorn`, `requests`, `pydantic`, `pyyaml`, `tenacity`, `pdfplumber`

**Architecture:**
The system is composed of several key components in `home-ai/soa1/`:
1.  **`api.py`:** Exposes REST endpoints (`/api/chat`, `/upload-batch`, `/ask`) to interact with the agent.
2.  **`agent.py`:** The Orchestrator. It handles intent detection, memory retrieval, and specialist invocation.
3.  **`batch_processor.py`:** Manages the background processing of uploaded financial documents.
4.  **`models.py`:** Clients for interacting with `Ollama` models.
5.  **`utils/financial_calculator.py`:** Pure Python math engine for 100% accurate aggregations.
6.  **`config.yaml`:** Central configuration file.

---

# Building and Running

### 1. Prerequisites
- Python 3.10+
- A running `Ollama` instance.
- A running `MemLayer` instance.

### 2. Installation
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 3. Configuration
- Create a `config.yaml` file based on `config.example.yaml` (TODO: create this file).
- Update the `config.yaml` with the correct URLs for your `Ollama` and `MemLayer` services.

### 4. Running the Server
Start the FastAPI server:
```bash
python soa1/api.py
```
The API will be available at `http://localhost:8001` by default.

### 5. Running Tests
TODO: Add instructions on how to run tests.

---

# Development Conventions

- **Logging:** The project uses a custom logger utility (`utils/logger.py`) to provide structured logging for different components (`api`, `agent`, `model`, `memory`).
- **Error Handling:** The agent uses `tenacity` for retrying failed requests to external services (`Ollama` and `MemLayer`).
- **Configuration:** All configuration is managed through the central `config.yaml` file. Avoid hardcoding values.
- **Modularity:** The application is split into distinct modules with clear responsibilities (API, agent logic, external service clients), making it easier to maintain and extend.
