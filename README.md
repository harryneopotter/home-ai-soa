# 🏠 SOA1 (Son of Anton) - Your Privacy-First AI Home Assistant

<div align="center">

**A fully local, consent-based AI assistant that respects your privacy and puts you in control**

[![License](https://img.shields.io/badge/License-Private-blue.svg)]()
[![Status](https://img.shields.io/badge/Status-Active%20Development-green.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Local%20Only-orange.svg)]()

[Quick Start](#-for-non-technical-users) • [Technical Details](#-technical-details) • [Documentation](#-documentation)

</div>

---

## 📖 Table of Contents

### For Everyone
- [What is SOA1?](#what-is-soa1)
- [For Non-Technical Users](#-for-non-technical-users)

### For Developers
- [Technical Details](#-technical-details)
- [Development](#-development)

---

# What is SOA1?

**SOA1 (Son of Anton)** is your personal AI home assistant that runs entirely on your own computer. Unlike cloud-based assistants that send your data to remote servers, SOA1 processes everything locally, ensuring your financial documents, conversations, and personal information never leave your home.

Think of it as a knowledgeable, privacy-conscious assistant that can help you:
- 📊 Analyze your financial statements and spending patterns
- 💬 Answer questions about your documents
- 📝 Organize and remember important information
- 🎯 Provide insights without judgment or data collection

**Key Principle**: SOA1 never takes action without your explicit permission. It offers options, waits for your decision, and respects your choices.

---

# 👥 For Non-Technical Users

## 🎯 What Can SOA1 Do For You?

### 💰 Financial Analysis
Upload your bank or credit card statements (PDF format), and SOA1 can help you:
- **Understand your spending**: See where your money goes by category (groceries, dining, travel, etc.)
- **Identify patterns**: Discover your most frequent merchants and spending trends
- **Compare periods**: See how this month compares to previous months
- **Find insights**: Get suggestions for potential savings

**Example conversation:**
```
You: "I uploaded my credit card statement"
SOA1: "I've received your Chase statement for December 2025. 
       Would you like me to:
       • Answer a specific question about it
       • Get a quick summary
       • Analyze your spending in detail"

You: "Analyze my spending"
SOA1: "I can break down your transactions by category and show you 
       spending patterns. Should I proceed?"

You: "Yes"
SOA1: "Here's what I found from 127 transactions:
       💰 Total Spending: $3,847.23
       🍽️ Top Category: Dining ($892.50)
       🏪 Most Frequent: Whole Foods (15 visits)
       📈 +12% compared to last month"
```

### 💬 Document Question & Answer
Ask questions about any document you've uploaded:
- "How much did I spend at coffee shops?"
- "What were my largest expenses this month?"
- "Did I visit any new restaurants?"

### 📚 Memory & Context
SOA1 remembers your past conversations and can:
- Recall information from previous sessions
- Answer questions based on what you've told it before
- Maintain context across multiple documents

---

## 🚀 How to Use SOA1

### Getting Started

1. **Access the Interface**: Open your web browser and navigate to the SOA1 interface (typically at `http://localhost:8080`)

2. **Upload Documents**:
   - Click the "Upload PDF" button
   - Select your financial statement (PDF format)
   - Wait for confirmation (usually 2-3 seconds)

3. **Interact via Chat**:
   - Type your question or request in the chat box
   - SOA1 will respond and offer options
   - Confirm any analysis requests by saying "yes" or "proceed"

4. **Review Results**:
   - View spending breakdowns by category
   - See visual charts and summaries
   - Ask follow-up questions for deeper insights

### Important Things to Know

#### ✅ You're Always in Control
- SOA1 **never** automatically analyzes your documents
- It **always asks permission** before performing detailed analysis
- Uploading a file does NOT mean SOA1 will process it
- Silence is NOT consent - you must explicitly say "yes"

#### 🔒 Your Privacy is Protected
- **All processing happens locally** on your computer
- **No data is sent to the cloud** or external servers
- **Your documents stay on your machine** - never uploaded elsewhere
- **No tracking, no telemetry, no data collection**

#### 💡 Best Practices
- **Be specific**: "Analyze my dining expenses" works better than "tell me stuff"
- **Upload clean PDFs**: Bank statements work best (receipts and scanned documents may vary)
- **Ask follow-ups**: After an analysis, ask for clarification or deeper insights
- **Grant consent explicitly**: Say "yes", "proceed", or "go ahead" when asked

---

## 🎨 What You'll See

### The Chat Interface
- **Clean conversation view**: Your questions and SOA1's responses
- **Clear options**: SOA1 presents choices, you decide what happens next
- **Progress indicators**: See when analysis is happening
- **Results display**: Charts, tables, and summaries presented clearly

### Finance Dashboard
After analysis, you'll see:
- **Total spending** for the period
- **Category breakdown** (pie charts showing where money went)
- **Top merchants** ranked by frequency and amount
- **Spending trends** compared to previous periods
- **Actionable insights** and recommendations

---

## 🤔 Frequently Asked Questions

### Is my financial data safe?
**Absolutely.** SOA1 runs entirely on your local computer. Your documents never leave your machine, and no data is sent to any cloud service or external server.

### What file formats are supported?
Currently, SOA1 works best with **PDF files**, particularly:
- Bank statements
- Credit card statements
- Financial reports

### Can SOA1 connect to my bank directly?
No, and this is intentional. SOA1 requires you to manually upload statements, ensuring you control exactly what data it sees.

### Will SOA1 work offline?
Yes! Since everything runs locally, SOA1 works completely offline. No internet connection is required for analysis.

### How accurate is the spending analysis?
SOA1 uses specialized financial models trained on transaction data. For arithmetic calculations (totals, averages), it uses Python (100% accurate). For insights and categorization, it uses AI models that are generally very accurate but can occasionally misclassify merchants.

### Can multiple people use the same SOA1 instance?
Currently, SOA1 is designed for single-user/household use. Multi-user support with separate profiles is planned for future releases.

### What happens to my uploaded documents?
Documents are stored locally in the `finance-agent/data/uploads/` folder on your system. You can delete them anytime.

---

## 🛣️ What's Coming Next

SOA1 is actively being developed. Planned features include:

- 📊 **Budgeting Assistant**: Set budgets, track goals, get alerts
- 📅 **Scheduler**: Calendar management and reminders
- 📚 **Knowledge Base**: Deep document indexing and cross-reference
- 🎙️ **Voice Interface**: Talk to SOA1 instead of typing
- 📱 **Mobile App**: Access SOA1 from your phone
- 👥 **Multi-user Support**: Separate profiles for family members

---

# 🔧 Technical Details

> **For Developers, System Administrators, and Technical Users**

## 🏗️ System Architecture

SOA1 is a modular, service-oriented architecture (SOA) built on a consent-based, privacy-first foundation.

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE LAYER                      │
│  ├─ WebUI Dashboard (8080) - Main interface                     │
│  ├─ Chat Interface (8002) - Standalone chat                     │
│  └─ Monitoring (8003) - Service status                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                         SOA1 API (8001)                          │
│  FastAPI server with:                                            │
│  ├─ /api/chat - Conversation endpoint                           │
│  ├─ /upload-pdf - Document upload                               │
│  ├─ /api/consent - Consent management                           │
│  ├─ /health - Health checks                                     │
│  └─ Rate limiting, validation, error handling                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
┌──────────▼─────────┐  ┌────▼──────────┐  ┌──▼─────────────────┐
│  SOA1 Agent        │  │ MemLayer       │  │ SQLite Database    │
│  - Query handler   │  │ (8000)         │  │ - documents        │
│  - Memory search   │  │ - Vector DB    │  │ - transactions     │
│  - [INVOKE] detect │  │ - Long-term    │  │ - analysis_jobs    │
│  - Orchestration   │  │   memory       │  │ - chat_history     │
└──────────┬─────────┘  └───────────────┘  └────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                         OLLAMA (11434)                           │
│  ├─ NemoAgent (GPU 0, ~13GB VRAM) - Orchestrator               │
│  │   • Conversation & routing                                   │
│  │   • Intent classification                                    │
│  │   • Consent enforcement                                      │
│  │   • Response generation                                      │
│  └─ phinance-json (GPU 1, ~4GB VRAM) - Finance Specialist      │
│      • Transaction analysis                                     │
│      • Spending insights                                        │
│      • Category breakdown                                       │
│      • JSON-structured output                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Hardware Requirements

**Current Configuration:**
- **CPU**: Intel X670
- **GPU**: 2x NVIDIA RTX 5060 Ti (16GB VRAM each, 32GB total)
- **RAM**: 32GB+ recommended
- **Storage**: 100GB+ for models and data
- **OS**: Ubuntu 22.04 LTS (tested) or compatible Linux

**Minimum Specifications:**
- Modern multi-core CPU (Intel i5/Ryzen 5 or better)
- NVIDIA GPU with 16GB+ VRAM (for optimal performance)
- 16GB RAM minimum
- 50GB free disk space

### Software Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Core Runtime** | Python 3.9+ | Application logic |
| **API Framework** | FastAPI | HTTP endpoints |
| **LLM Inference** | Ollama | Local model serving |
| **Database** | SQLite | Transaction & document storage |
| **Memory Layer** | MemLayer | Vector database for long-term memory |
| **PDF Processing** | PyMuPDF, pdfplumber | Document parsing |
| **Networking** | Tailscale | Secure remote access (optional) |

---

## 🚀 Installation & Setup

### Prerequisites

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.9+
sudo apt install python3 python3-pip python3-venv -y

# Install NVIDIA drivers and CUDA (for GPU support)
sudo apt install nvidia-driver-535 nvidia-cuda-toolkit -y

# Install Ollama
curl https://ollama.ai/install.sh | sh
```

### Clone & Setup

```bash
# Clone repository
git clone https://github.com/harryneopotter/home-ai-soa.git
cd home-ai-soa

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables (create .env file if needed)
export PYTHONPATH=/path/to/home-ai-soa
```

### Download Models

```bash
# Pull the orchestrator model (NemoAgent - user swappable)
ollama pull nvidia/nemotron-mini:4b-instruct-q4_K_M

# Pull the finance specialist model
ollama pull phinance-json:latest
```

### Initialize Services

```bash
# Start MemLayer (memory service)
cd home-ai/memlayer
python3 server.py &

# Start SOA1 API
cd home-ai/soa1
PYTHONPATH=/path/to/home-ai-soa python3 api.py &

# Start WebUI
cd soa-webui
python3 main.py &
```

### Verify Installation

```bash
# Check service health
curl http://localhost:8001/health  # SOA1 API
curl http://localhost:8080/health  # WebUI
curl http://localhost:8000/health  # MemLayer

# Check Ollama models
ollama list

# Test chat endpoint
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

---

## ⚙️ Configuration

### SOA1 Configuration (`home-ai/soa1/config.yaml`)

```yaml
model:
  provider: "ollama"
  base_url: "http://localhost:11434"
  model_name: "NemoAgent:latest"  # User-swappable
  temperature: 0.3
  max_tokens: 512
  num_ctx: 32768

specialists:
  finance:
    enabled: true
    model_name: "phinance-json:latest"
    temperature: 0.05

services:
  memlayer_url: "http://localhost:8000"
  api_port: 8001
```

### WebUI Configuration (`soa-webui/config.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 8080

services:
  api: "http://localhost:8001"
  memlayer: "http://localhost:8000"

security:
  ip_whitelist:
    - "100.64.0.0/10"  # Tailscale network
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database
DATABASE_PATH=/path/to/finance-agent/data/finance.db

# Upload directory
UPLOAD_DIR=/path/to/finance-agent/data/uploads

# Logging
LOG_LEVEL=INFO
LOG_DIR=/path/to/logs

# API Rate Limits
RATE_LIMIT_GENERAL=100  # requests per minute
RATE_LIMIT_TTS=20
RATE_LIMIT_PDF=10
```

---

## 📊 System Architecture Deep Dive

### Design Principles

1. **Privacy-First**: All data processing happens locally
2. **Consent-Based**: No specialist actions without explicit user confirmation
3. **Modular**: Specialist agents are independent, swappable modules
4. **Resource-Aware**: Intelligent GPU allocation across specialists
5. **User Agency**: User always has control; silence ≠ consent
6. **LLM-Driven Communication**: All user-facing responses from LLM, never hardcoded

### The Orchestrator (Model-Agnostic)

The orchestrator is the main conversational interface that:
- Engages users in natural conversation
- Classifies intent through conversation analysis
- Routes requests to appropriate specialists
- Enforces consent before invoking specialists
- Maintains context across multi-domain conversations
- Synthesizes results from multiple specialists

**Key characteristic**: User-swappable model (currently NemoAgent, but any compatible model works)

**System prompt**: Loaded at runtime from `home-ai/soa1/prompts/orchestrator.md` (no Modelfile needed)

### Specialist Agents

Specialists are **callable modules**, NOT autonomous agents:

✅ Accept structured input only  
✅ Perform a single, scoped task  
✅ Return structured output  
❌ Do NOT handle user intent  
❌ Do NOT ask questions  
❌ Do NOT enforce consent  

**Current Specialists:**
- **Finance (phinance-json)**: Transaction analysis, spending insights ✅ Operational
- **Budgeting**: Budget planning, expense tracking ⏳ Planned
- **Knowledge**: Document indexing, cross-reference ⏳ Planned
- **Scheduler**: Calendar management, reminders ⏳ Planned

### Consent Framework

> **Core Invariant**: The assistant MUST NOT initiate any specialist action unless the user has explicitly requested or confirmed it.

**What requires consent:**
- Financial analysis
- Deep categorization
- Report generation
- Any specialist invocation

**What does NOT require consent:**
- File ingestion
- Metadata extraction
- Header parsing
- Preparing options

**Consent language:**
- ✅ Allowed: "Do you want me to...", "If you like, I can..."
- ❌ Forbidden: "I'll go ahead and...", "I've started analyzing..."

### Data Flow: PDF Upload to Analysis

```
1. User uploads PDF → POST /upload-pdf
2. File saved, metadata extracted
3. Analysis job created (status: "pending")
4. SOA1Agent generates acknowledgment via LLM
5. Returns: {status: "UPLOADED", doc_id, agent_response}

[User engagement via chat]

6. User: "analyze my spending"
7. NemoAgent: Asks for consent
8. User: "yes"
9. NemoAgent response includes: [INVOKE:phinance]
10. agent.py detects [INVOKE:phinance] tag
11. _invoke_phinance() loads transactions from SQLite
12. Calls phinance-json model
13. Returns formatted insights to user
```

### Database Schema

**Location**: `finance-agent/data/finance.db`

```sql
-- Document uploads
documents (
  document_id TEXT PRIMARY KEY,
  filename TEXT,
  pages INTEGER,
  upload_ts TEXT
)

-- Analysis tracking
analysis_jobs (
  job_id TEXT PRIMARY KEY,
  doc_id TEXT UNIQUE,
  status TEXT,  -- pending, running, completed, failed
  consent_given INTEGER,
  phinance_raw_response TEXT
)

-- Extracted transactions
transactions (
  id INTEGER PRIMARY KEY,
  doc_id TEXT,
  date TEXT,
  description TEXT,
  amount REAL,
  category TEXT,
  merchant TEXT
)

-- Chat history
chat_history (
  id INTEGER PRIMARY KEY,
  session_id TEXT,
  role TEXT,  -- user or assistant
  content TEXT,
  created_at TIMESTAMP
)
```

---

## 🔌 API Reference

### Chat Endpoint

```http
POST /api/chat
Content-Type: application/json

{
  "message": "What did I spend on groceries?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "response": "Based on your Chase statement, you spent $347.82 on groceries...",
  "session_id": "abc-123",
  "used_memories": [...]
}
```

### PDF Upload

```http
POST /upload-pdf
Content-Type: multipart/form-data

file: <PDF file>
```

**Response:**
```json
{
  "status": "UPLOADED",
  "document_id": "doc-abc123",
  "filename": "statement.pdf",
  "pages": 12,
  "agent_response": "I've received your Chase statement for December 2025..."
}
```

### Batch Upload

```http
POST /upload-batch
Content-Type: multipart/form-data

files: <multiple PDF files>
```

**Response:**
```json
{
  "status": "SUCCESS",
  "batch_id": "batch-abc123",
  "file_count": 5,
  "agent_response": "I've received 5 statements. Would you like me to analyze them?"
}
```

### Consent Management

```http
POST /api/consent
Content-Type: application/json

{
  "batch_id": "batch-abc123",
  "action": "analyze"
}
```

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "api": "up",
    "memory": "up",
    "ollama": "up"
  }
}
```

---

## 🔒 Security & Privacy

### Rate Limiting

Implemented via token bucket algorithm:
- **General API**: 100 requests/minute
- **TTS endpoints**: 20 requests/minute
- **PDF uploads**: 10 requests/minute

### Input Validation

- Maximum message length: 10,000 characters
- Maximum file size: 10 MB
- Supported formats: PDF only
- Pydantic models for request validation

### Data Protection

- **PII Redaction**: Automatic masking of credit card numbers, SSNs, emails in logs
- **Local-only processing**: No cloud connections
- **Encrypted storage**: (planned) for sensitive documents
- **IP whitelisting**: Tailscale network only (configurable)

### Error Handling

- Standardized error responses with error codes
- Comprehensive validation (input, files, queries)
- Service error isolation (memory, model, TTS)
- Client IP tracking in logs

---

## 🧪 Testing

### Run Tests

```bash
# Unit tests
python -m pytest home-ai/tests/

# Integration tests
python -m pytest home-ai/tests/integration/

# End-to-end tests
cd soa-webui
python test_finance_pipeline.py
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=home-ai --cov-report=html
```

### Manual Testing

```bash
# Test chat
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'

# Test upload
curl -X POST http://localhost:8001/upload-pdf \
  -F "file=@test_statement.pdf"

# Check models
ollama list

# Check GPU usage
nvidia-smi
```

---

## 📝 Development

### Project Structure

```
home-ai-soa/
├── home-ai/
│   ├── soa1/                    # Main SOA1 service
│   │   ├── api.py              # FastAPI server
│   │   ├── agent.py            # SOA1Agent class
│   │   ├── model.py            # ModelClient for Ollama
│   │   ├── models.py           # Specialist model calls
│   │   ├── orchestrator.py     # Consent management
│   │   ├── memory.py           # MemLayer client
│   │   ├── batch_processor.py  # Batch upload handling
│   │   └── prompts/
│   │       └── orchestrator.md # System prompt
│   │
│   ├── finance-agent/          # Finance specialist
│   │   └── src/
│   │       ├── storage.py      # SQLite operations
│   │       ├── parser.py       # PDF extraction
│   │       └── models.py       # Finance model calls
│   │
│   └── memlayer/               # Memory service
│
├── soa-webui/                   # Web interface
│   ├── main.py                 # Dashboard server
│   ├── templates/              # HTML templates
│   └── static/                 # CSS, JS, images
│
├── RemAssist/                   # Documentation
│   ├── PROJECT_STATE.md        # Current state
│   ├── ARCHITECTURE.md         # System architecture
│   ├── IMPLEMENTATION_GUIDE.md # Core invariants
│   ├── BATCH_FLOW.md           # Upload pipeline
│   ├── NEXT_TASKS.md           # Task queue
│   └── History.md              # Session history
│
└── README.md                    # This file
```

### Adding a New Specialist

1. Create specialist in `home-ai/agents/new_specialist.py`
2. Define input/output schemas (dataclasses)
3. Create adapter function for payload building
4. Add to orchestrator system prompt
5. Update orchestrator intent classification
6. Create Modelfile if using specialized model
7. Update documentation

**Example skeleton:**
```python
# home-ai/agents/medical_specialist.py
from dataclasses import dataclass
from typing import List

@dataclass
class MedicalDocument:
    doc_type: str
    date: str
    provider: str
    content: str

@dataclass
class MedicalInsight:
    summary: str
    key_findings: List[str]
    action_items: List[str]
    confidence: float

def analyze_medical_document(doc: MedicalDocument) -> MedicalInsight:
    """Analyze medical document (requires consent)"""
    # Implementation
    pass
```

### Code Style

- **Python**: PEP 8 compliance
- **Type hints**: Required for all functions
- **Docstrings**: Google style for public APIs
- **Comments**: Explain why, not what (code should be self-documenting)

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/new-specialist

# Make changes and commit
git add .
git commit -m "Add medical specialist module"

# Push and create PR
git push origin feature/new-specialist
```

---

## 🐛 Troubleshooting

### Services Won't Start

```bash
# Check port conflicts
sudo lsof -i :8001  # SOA1 API
sudo lsof -i :8080  # WebUI
sudo lsof -i :11434 # Ollama

# Check logs
tail -f /tmp/soa1.log
tail -f /tmp/webui.log

# Restart services
pkill -f "python.*api.py"
pkill -f "python.*main.py"
# Then restart manually
```

### GPU Not Detected

```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA
nvcc --version

# Check Ollama GPU usage
ollama ps

# Force GPU for Ollama
CUDA_VISIBLE_DEVICES=0 ollama serve
```

### Model Loading Issues

```bash
# List available models
ollama list

# Pull model again
ollama pull NemoAgent:latest
ollama pull phinance-json:latest

# Check model size vs available VRAM
nvidia-smi
```

### Upload Failures

```bash
# Check upload directory exists
ls -la finance-agent/data/uploads/

# Create if missing
mkdir -p finance-agent/data/uploads

# Check permissions
chmod 755 finance-agent/data/uploads
```

### Memory Service Unreachable

```bash
# Check MemLayer status
curl http://localhost:8000/health

# Restart MemLayer
cd home-ai/memlayer
python3 server.py &
```

---

## 📚 Documentation

### Core Documentation

- **[PROJECT_STATE.md](RemAssist/PROJECT_STATE.md)**: Current system state, services, ports, data flow
- **[ARCHITECTURE.md](home-ai/ARCHITECTURE.md)**: Detailed system architecture diagrams
- **[IMPLEMENTATION_GUIDE.md](RemAssist/IMPLEMENTATION_GUIDE.md)**: Core invariants, consent rules (MUST READ for development)
- **[BATCH_FLOW.md](RemAssist/BATCH_FLOW.md)**: 5-phase progressive upload pipeline
- **[LLM_DRIVEN_RESPONSES.md](RemAssist/LLM_DRIVEN_RESPONSES.md)**: Communication principles
- **[HARDWARE_SPECS.md](RemAssist/HARDWARE_SPECS.md)**: VRAM budget, model limits

### Session Documentation

- **[History.md](RemAssist/History.md)**: Session history, changes made
- **[NEXT_TASKS.md](RemAssist/NEXT_TASKS.md)**: Task queue, planned features
- **[errors.md](RemAssist/errors.md)**: Error tracking log

### Agent Guidelines

- **[AGENTS.md](AGENTS.md)**: Guidelines for AI agents working on this project

---

## 🤝 Contributing

SOA1 is currently a private project, but contributions are welcome from collaborators.

### Development Guidelines

1. **Read the docs first**: Especially `IMPLEMENTATION_GUIDE.md` and `AGENTS.md`
2. **Respect the principles**: Privacy-first, consent-based, user agency
3. **Test thoroughly**: Run tests, verify on real data
4. **Document changes**: Update relevant .md files
5. **Follow conventions**: Match existing code style

### Before Adding Features

- Check `NEXT_TASKS.md` for planned work
- Review `HARDWARE_SPECS.md` for resource constraints
- Ensure consent framework is maintained
- Verify LLM-driven responses (no hardcoded strings)

---

## 📄 License

This project is currently private. All rights reserved.

---

## 🙏 Acknowledgments

### Technologies Used
- [Ollama](https://ollama.ai/) - Local LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Tailscale](https://tailscale.com/) - Secure networking
- [NVIDIA](https://www.nvidia.com/) - GPU acceleration
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing

### Models
- **NVIDIA Nemotron** - Orchestrator model
- **Phinance** - Financial analysis specialist

---

## 📞 Support & Contact

For issues, questions, or collaboration inquiries, please refer to the internal project documentation or contact the development team.

---

## 🗺️ Roadmap

### Current Status (January 2026)
- ✅ Core orchestrator operational
- ✅ Finance specialist working
- ✅ Consent framework implemented
- ✅ PDF processing pipeline
- ✅ Chat history persistence
- ✅ Batch upload support
- ✅ Security hardening

### Q1 2026
- [ ] Budgeting specialist
- [ ] Enhanced batch processing UI
- [ ] Voice interface (TTS/STT)
- [ ] Mobile companion app (beta)

### Q2 2026
- [ ] Knowledge specialist
- [ ] Scheduler specialist
- [ ] Multi-user support
- [ ] Advanced analytics

### Future Vision
- Federation via Tailscale mesh → decentralized personal AI cloud
- Multiple specialized pods (Family, Finance, Study, Health, Creator)
- White-label deployment for clients
- Self-hosted "AI pods" as a product

---

<div align="center">

**Built with ❤️ for privacy, transparency, and user control**

⭐ **SOA1** - Your data, your AI, your rules ⭐

</div>
