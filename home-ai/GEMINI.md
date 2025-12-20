# Project Overview

This project is a local-only home assistant agent called `SOA1` ("Son of Anton"). It's designed to run on a private server and provides a conversational AI interface while ensuring user data remains entirely offline.

The core functionality revolves around a `SOA1Agent` that can:
- Receive user queries through a FastAPI-based REST API.
- Access a long-term memory system (`MemLayer`) to store and retrieve user-specific facts and conversation history.
- Use a local large language model (`Ollama`) to generate intelligent and context-aware responses.
- Ground its answers in stored memories to provide personalized and relevant assistance.

**Key Technologies:**
- **Backend:** Python, FastAPI
- **AI Model:** Ollama (configurable, e.g., `qwen2.5:7b-instruct`)
- **Memory:** MemLayer service
- **Dependencies:** `fastapi`, `uvicorn`, `requests`, `pydantic`, `pyyaml`, `tenacity`

**Architecture:**
The system is composed of three main components:
1.  **`api.py`:** Exposes a `/ask` endpoint to interact with the agent. It handles HTTP requests and responses.
2.  **`agent.py`:** Contains the core agent logic. It orchestrates the process of searching memory, querying the model, and storing new memories.
3.  **`memory.py` & `model.py`:** These are clients for interacting with the external `MemLayer` and `Ollama` services, respectively. They handle the direct communication with these dependencies.
4.  **`config.yaml`:** A central configuration file to manage all settings, including server ports, model names, and service URLs.

---

# Building and Running

### 1. Prerequisites
- Python 3.8+
- An running `Ollama` instance.
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
