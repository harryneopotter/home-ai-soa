# 🖥️ System Hardware Specifications

*Reference document for AI agents to understand compute resources, limits, and constraints.*

---

## 🏠 System Identity

| Property | Value |
|----------|-------|
| **Hostname** | `intel-x670` |
| **OS** | Ubuntu 22.04.5 LTS (Jammy Jellyfish) |
| **Primary IP** | 192.168.68.61 |
| **Network** | Local + Tailscale VPN |

---

## 🧠 CPU

| Property | Value |
|----------|-------|
| **Model** | Intel Core i5-12600K (12th Gen Alder Lake) |
| **Cores** | 10 (6 P-cores + 4 E-cores) |
| **Threads** | 16 |
| **Base/Boost** | 800 MHz - 4900 MHz |
| **Architecture** | Hybrid (Performance + Efficiency cores) |

### CPU Guidance for Agents
- ✅ 16 threads available for parallel Python workloads
- ✅ Good for batch PDF processing, text extraction
- ⚠️ CPU-bound LLM inference is slow — always prefer GPU

---

## 🧮 Memory (RAM)

| Property | Value |
|----------|-------|
| **Total** | 128 GB DDR5 |
| **Available** | ~119 GB (typical) |
| **Swap** | 30 GB |

### Memory Guidance for Agents
- ✅ Ample RAM for large batch processing
- ✅ Can load multiple large datasets into memory
- ✅ Python processes can safely use 10-20GB without concern
- ⚠️ Ollama models load into VRAM, not system RAM

---

## 🎮 GPUs

### Dual NVIDIA GeForce RTX 5060 Ti

| GPU | VRAM Total | Typical Used | Typical Free | PCIe Slot |
|-----|------------|--------------|--------------|-----------|
| GPU 0 | 16 GB | ~10.7 GB | ~5.3 GB | 01:00.0 |
| GPU 1 | 16 GB | ~10.8 GB | ~5.2 GB | 05:00.0 |

| Property | Value |
|----------|-------|
| **Driver** | 580.95.05 |
| **CUDA Version** | 13.0 |
| **TDP** | 180W each (360W total) |
| **Architecture** | Blackwell |

### Current GPU Allocation

| Model | GPU | VRAM Used | Purpose |
|-------|-----|-----------|---------|
| **NemoAgent** | GPU 0 | ~10.7 GB | Orchestrator (Claude-4.5 distill) |
| **phinance-json** | GPU 1 | ~10.8 GB | Finance specialist |

### GPU Guidance for Agents

#### Available VRAM Budget
```
GPU 0: ~5 GB free (after NemoAgent)
GPU 1: ~5 GB free (after phinance-json)
Total free: ~10 GB across both GPUs
```

#### Model Size Limits
- ✅ **Can add**: Models up to ~4-5GB (MiniCPM-V, small Qwen, etc.)
- ⚠️ **Tight fit**: Models 6-8GB require evicting existing model
- ❌ **Cannot fit**: Models >10GB without major reconfiguration

#### Multi-GPU Considerations
- Ollama can split models across GPUs (tensor parallelism)
- Large models (>16GB) require both GPUs
- Smaller models should target single GPU for lower latency

---

## 💾 Storage

### NVMe SSDs

| Device | Size | Model | Mount Point |
|--------|------|-------|-------------|
| nvme0n1 | 1 TB | WD BLACK SN770 | (secondary) |
| nvme1n1 | 1 TB | WD BLACK SN770 | `/` (root) |

### Current Usage

| Filesystem | Size | Used | Available | Use% |
|------------|------|------|-----------|------|
| Root (`/`) | 94 GB | 65 GB | 25 GB | 73% |

### Storage Guidance for Agents
- ⚠️ **Root partition at 73%** — avoid creating large temp files
- ✅ 2 TB total NVMe storage available
- ✅ NVMe is fast — good for model loading, PDF processing
- 📁 Ollama models stored in `~/.ollama/models/`

---

## 🤖 Ollama Configuration

### Available Models (as of Jan 2, 2026)

| Model | Size | Purpose | Status |
|-------|------|---------|--------|
| `NemoAgent:latest` | 8.7 GB | Orchestrator | ✅ Primary |
| `phinance-json:latest` | 2.2 GB | Finance extraction | ✅ Primary |
| `qwen2.5:7b-instruct` | 4.7 GB | General assistant | Available |
| `llama3.3:latest` | 42 GB | Large reasoning | Available (needs both GPUs) |
| `qwq:latest` | 19 GB | Reasoning | Available |
| `deepseek-r1:8b` | 5.2 GB | Reasoning | Available |
| `nomic-embed-text:latest` | 274 MB | Embeddings | Available |

### Ollama Endpoints
- **API**: `http://localhost:11434`
- **Health**: `http://localhost:11434/api/tags`

---

## 🌐 Network Services

| Service | Port | Description |
|---------|------|-------------|
| SOA1 API | 8001 | FastAPI backend |
| WebUI | 80 | Nginx → soa-webui |
| Ollama | 11434 | LLM inference |
| MemLayer | 8000 | Memory service |

---

## 📊 Resource Planning Matrix

Use this when planning new features or models:

| Resource | Total | Currently Used | Available | Constraint Level |
|----------|-------|----------------|-----------|------------------|
| CPU Threads | 16 | ~2 (idle) | 14 | 🟢 Abundant |
| System RAM | 128 GB | ~5 GB | 119 GB | 🟢 Abundant |
| GPU 0 VRAM | 16 GB | 10.7 GB | 5.3 GB | 🟡 Moderate |
| GPU 1 VRAM | 16 GB | 10.8 GB | 5.2 GB | 🟡 Moderate |
| Root Disk | 94 GB | 65 GB | 25 GB | 🟠 Watch |

### Decision Guide: "Can I add model X?"

```
Model Size    Recommendation
─────────────────────────────────────────────
< 3 GB        ✅ Yes, fits easily on either GPU
3-5 GB        ✅ Yes, but choose GPU carefully
5-8 GB        ⚠️ Maybe, may need to evict a model
8-16 GB       ⚠️ Requires dedicated GPU, evict others
16-32 GB      ❌ Needs both GPUs, major reconfiguration
> 32 GB       ❌ Cannot fit, exceeds total VRAM
```

---

## 🔧 Useful Commands

### Check GPU Status
```bash
nvidia-smi
```

### Check Running Models
```bash
ollama ps
```

### Check Memory
```bash
free -h
```

### Check Disk
```bash
df -h /
```

---

*Last updated: January 2, 2026*
