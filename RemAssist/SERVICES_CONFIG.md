# 📋 Services Configuration

## 🎯 Overview

This document provides a comprehensive reference for all SOA1 services, their configurations, ports, and purposes.

## 🌐 Service Inventory

### 1. SOA1 API Service

**Purpose**: Core API for SOA1 agent functionality

**Configuration**:
- **Port**: 8001
- **Command**: `python3 api.py`
- **Location**: `home-ai/soa1/api.py`
- **Dependencies**: FastAPI, Pydantic, transformers, soundfile, torch
- **Features**: Agent interaction, TTS (optional), memory management

**Logging**:
- File: `home-ai/soa1/logs/api.log`
- Level: INFO
- Format: `[timestamp] [level] [name] message`

**Access**:
- Local: `http://localhost:8001`
- Tailscale: `http://<tailscale-ip>:8001`

**Endpoints**:
- `POST /ask` - Ask agent a question
- `POST /ask-with-tts` - Ask with TTS

### 2. LlamaFarm Framework

**Purpose**: Multi-agent orchestration framework

**Configuration**:
- **Location**: `/home/ryzen/projects/llamafarm/LlamaFarm/`
- **Virtual Environment**: `/home/ryzen/projects/llamafarm/venv/`
- **CLI Location**: `/home/ryzen/projects/llamafarm/LlamaFarm/cli/`
- **Go Module**: `/home/ryzen/projects/llamafarm/LlamaFarm/cli/go.mod`
- **Main CLI**: `/home/ryzen/projects/llamafarm/LlamaFarm/cli/main.go`

**Status**: ✅ Complete repository available, ❌ CLI not yet built

**Build Instructions**:
```bash
cd /home/ryzen/projects/llamafarm/LlamaFarm/cli/
go build -o lf main.go
```

**Features**:
- Multi-agent orchestration
- PDF processing via Smart Ingest
- Local-first architecture
- Docker-ready deployment

**GPU Requirements**: 4x NVIDIA RTX 3060 (12GB each)

**Dependencies**:
- Go 1.21+
- Docker
- NVIDIA Container Toolkit
- Ollama (for model serving)

**Access**:
- CLI: `./lf` (after building)
- Server: `http://localhost:8000` (default)

**Key Components**:
- `cli/` - Go-based CLI tool
- `server/` - FastAPI backend
- `designer/` - Web interface
- `rag/` - RAG processing pipeline
- `runtimes/` - Model runtimes

### 3. Service Monitoring Web UI

**Purpose**: Monitor SOA1 services and system status

**Configuration**:
- **Port**: 8080
- **Command**: `python3 /home/ryzen/projects/soa-webui/secure_webui.py`
- **Location**: `/home/ryzen/projects/soa-webui/secure_webui.py`
- **Dependencies**: FastAPI, psutil, requests
- **Logging**: `secure_webui.log` (INFO level)

**Actual Features (Verified)**:
- ✅ Service status monitoring (SOA1 API, Web Interface, Service Monitor)
- ✅ IP whitelisting and security indicators
- ✅ Tailscale integration with IP display
- ✅ Access control status (authorized/denied)
- ✅ System health indicators
- ✅ Refresh functionality
- ✅ Secure access information

**Missing Features (From Documentation)**:
- ❌ System metrics (CPU, memory, disk) - Not implemented
- ❌ Service management controls - Not implemented
- ❌ Technical system information - Not implemented

**Access**:
- Local: `http://localhost:8080`
- Tailscale: `http://<tailscale-ip>:8080`

**Current Status**: ✅ **ACTIVE** - Running and accessible

### 4. Agent Interaction Web UI

**Purpose**: Complete agent interaction with chat and PDF processing

**Configuration**:
- **Port**: 8081
- **Command**: `python3 /home/ryzen/projects/soa-webui/agent_webui.py`
- **Location**: `/home/ryzen/projects/soa-webui/agent_webui.py`
- **Dependencies**: FastAPI, requests, logging
- **Logging**: `agent_webui.log` (INFO level)
- **API Integration**: Connects to SOA1 API at port 8001

**Actual Features (Verified)**:
- ✅ Advanced chat interface with SOA1 agent
- ✅ Real-time agent responses via JavaScript
- ✅ IP whitelisting (100.64.0.0/10, 100.84.92.33)
- ✅ Tailscale integration with status display
- ✅ Agent status indicators (Online/Offline)
- ✅ Chat message history display
- ✅ User-friendly gradient interface
- ✅ Auto-focus on chat input
- ✅ Loading indicators during processing
- ✅ Error handling and display

**Missing Features (From Documentation)**:
- ❌ PDF processing capabilities - Not implemented
- ❌ Agent interaction history - Not implemented
- ❌ Document analysis - Not implemented
- ❌ Content creation tools - Not implemented

**Access**:
- Local: `http://localhost:8081`
- Tailscale: `http://<tailscale-ip>:8081`

**Current Status**: ✅ **ACTIVE** - Running and accessible

**Key Differences from Service Monitoring UI**:
- Focused on agent interaction vs system monitoring
- Includes chat interface and conversation features
- More user-friendly gradient interface
- Real-time JavaScript interaction
- Direct API integration for agent communication

### 4. Memlayer Service

**Purpose**: Memory management for SOA1

**Configuration**:
- **Port**: 8000
- **Command**: `python3 memlayer/main.py` (if exists)
- **Location**: (To be created)
- **Dependencies**: (To be determined)

**Status**: Not yet implemented

### 5. Nginx Reverse Proxy

**Purpose**: Web server and reverse proxy

**Configuration**:
- **Port**: 80/443
- **Command**: `systemctl start nginx`
- **Location**: `/etc/nginx/sites-available/soa1.conf`

**Status**: Not yet configured

## 🔧 Service Management

### Starting Services

```bash
# Start all services
cd /home/ryzen/projects/home-ai/soa1 && python3 api.py &
cd /home/ryzen/projects/soa-webui && python3 secure_webui.py &
cd /home/ryzen/projects/soa-webui && python3 agent_webui.py &
```

### Stopping Services

```bash
# Stop all services
pkill -f "api.py\|secure_webui.py\|agent_webui.py"
```

### Checking Status

```bash
# Check service status
ps aux | grep -E "(api.py|secure_webui.py|agent_webui.py)"
ss -tulnp | grep -E "(8001|8080|8081)"
```

## 🎯 GPU Configuration

**Available GPUs**: 4x NVIDIA GeForce RTX 3060 (12GB VRAM each)

**GPU Details**:
```
GPU 0: RTX 3060 - 12GB VRAM - Bus ID: 00000000:08:00.0
GPU 1: RTX 3060 - 12GB VRAM - Bus ID: 00000000:09:00.0  
GPU 2: RTX 3060 - 12GB VRAM - Bus ID: 00000000:42:00.0
GPU 3: RTX 3060 - 12GB VRAM - Bus ID: 00000000:43:00.0
```

**Total VRAM**: 48GB (12GB x 4)
**CUDA Version**: 13.0
**Driver Version**: 580.105.08

**GPU Usage Strategy**:
- GPU 0: Primary model inference (Ollama)
- GPU 1: Secondary tasks / backup
- GPU 2: RAG processing / embeddings
- GPU 3: Available for additional workloads

## 📁 Directory Structure

```
home-ai/soa1/
├── api.py                # Main API
├── agent.py              # Agent core
├── tts_service.py         # TTS service
├── utils/
│   └── logger.py         # Logging utility
└── logs/
    └── api.log           # API logs

soa-webui/
├── secure_webui.py       # Service monitoring (Port 8080)
├── agent_webui.py        # Agent interaction (Port 8081)
├── config.yaml           # Configuration
├── logs/
│   ├── secure_webui.log  # Monitoring UI logs
│   └── agent_webui.log   # Agent UI logs
├── templates/
│   ├── index.html        # HTML templates
│   ├── services.html     # Services page
│   └── status.html       # Status page
├── static/               # Static assets
│   └── (CSS, JS, images)
└── services/             # Service management
    └── (service scripts)
```

## 🎯 Port Reference

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| SOA1 API | 8001 | Core API | ✅ Active |
| Monitoring UI | 8080 | Service monitoring | ✅ Active |
| Agent UI | 8081 | Agent interaction | ✅ Active |
| Memlayer | 8000 | Memory service | ❌ Not implemented |
| Nginx | 80/443 | Web proxy | ❌ Not configured |

**Active Web UIs:**
- **Port 8080**: Service Monitoring UI (`secure_webui.py`)
- **Port 8081**: Agent Interaction UI (`agent_webui.py`)

**Both UIs are currently running and accessible** ✅

## 📋 Configuration Reference

### API Configuration (`home-ai/soa1/config.yaml`)

```yaml
# Example configuration
server:
  host: "0.0.0.0"
  port: 8001

agent:
  model: "qwen2.5:7b-instruct"
  temperature: 0.3

tts:
  enabled: false
```

### Web UI Configuration (`soa-webui/config.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 8080  # or 8081 for agent UI

services:
  api: "http://localhost:8001"
  web_interface: "http://localhost:8082"
  service_monitor: "http://localhost:8003"
  memlayer: "http://localhost:8000"

tailscale:
  enabled: true
  allowed_ips:
    - "100.64.0.0/10"
    - "100.84.92.33"
```

## 🎯 Best Practices

1. **Logging**: Always check logs first when debugging
2. **Ports**: Use different ports to avoid conflicts
3. **Security**: Use IP whitelisting and Tailscale
4. **Documentation**: Keep services documented
5. **Testing**: Test each service individually

## 🌐 Web UI Comparison

### Service Monitoring UI (Port 8080) vs Agent Interaction UI (Port 8081)

#### **Service Monitoring UI (secure_webui.py)**

**Primary Purpose**: System monitoring and administration

**Target Audience**: System administrators, developers, operators

**Key Features**:
- ✅ Service status monitoring
- ✅ System metrics (CPU, memory, disk)
- ✅ Service health indicators
- ✅ IP whitelisting and security
- ✅ Tailscale integration
- ✅ Technical system information
- ✅ Service management controls

**Use Cases**:
- Monitor system health and status
- Check service availability
- View system metrics and resources
- Technical troubleshooting
- System administration tasks

**Technical Details**:
- **Framework**: FastAPI
- **Authentication**: IP whitelisting
- **Access Control**: Tailscale + IP filtering
- **Logging**: `secure_webui.log`
- **Templates**: System-focused HTML templates
- **Port**: 8080

#### **Agent Interaction UI (agent_webui.py)**

**Primary Purpose**: Agent interaction and content processing

**Target Audience**: End users, content creators, agent operators

**Key Features**:
- ✅ Advanced chat interface
- ✅ Real-time agent responses
- ✅ PDF document processing
- ✅ Content analysis and generation
- ✅ Conversation history
- ✅ User-friendly interface
- ✅ Agent-specific functions

**Use Cases**:
- Chat with SOA1 agent
- Upload and analyze PDF documents
- Content creation and editing
- Document processing workflows
- End-user agent interaction
- Specialized agent functions

**Technical Details**:
- **Framework**: FastAPI
- **Authentication**: IP whitelisting
- **Access Control**: Tailscale + IP filtering
- **Logging**: `agent_webui.log`
- **API Integration**: Connects to SOA1 API (port 8001)
- **Templates**: User-focused HTML templates
- **Port**: 8081

#### **Feature Comparison Table**

| Feature | Monitoring UI (8080) | Agent UI (8081) |
|---------|---------------------|-----------------|
| **Purpose** | System monitoring | Agent interaction |
| **Audience** | Administrators | End users |
| **Chat Interface** | ❌ No | ✅ Advanced |
| **PDF Processing** | ❌ No | ❌ No |
| **System Metrics** | ❌ No | ❌ No |
| **Service Status** | ✅ Yes | ❌ No |
| **Content Creation** | ❌ No | ❌ No |
| **User Interface** | Technical | User-friendly |
| **Complexity** | Low | Medium |
| **Primary Use** | Administration | Interaction |
| **JavaScript** | ❌ No | ✅ Yes |
| **API Integration** | ❌ No | ✅ Yes |

#### **When to Use Each UI**

**Use Service Monitoring UI (8080) when you need to:**
- ✅ Check service status and availability
- ✅ Monitor which services are running
- ✅ View access control status
- ✅ Refresh service information
- ✅ Perform basic system monitoring

**Use Agent Interaction UI (8081) when you need to:**
- ✅ Chat with the SOA1 agent
- ✅ Get real-time agent responses
- ✅ Test agent functionality
- ✅ Debug agent communication
- ✅ Use the chat interface

## 📚 References

- **API Documentation**: `home-ai/soa1/README.md`
- **Web UI Documentation**: `/home/ryzen/projects/soa-webui/README.md`
- **Logging**: `home-ai/soa1/utils/logger.py`
- **Service Monitoring UI**: `/home/ryzen/projects/soa-webui/secure_webui.py`
- **Agent Interaction UI**: `/home/ryzen/projects/soa-webui/agent_webui.py`

## 🎉 Summary

This document provides a comprehensive reference for all SOA1 services, their configurations, and management. Use this as a guide for development, testing, and deployment.
