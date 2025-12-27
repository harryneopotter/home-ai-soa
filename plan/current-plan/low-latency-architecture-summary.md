# 🏗️ Low-Perceived-Latency Architecture Summary

## Core Concept: Two-Stage Pipeline with Self-Optimization

### The Low-Latency Approach

**Problem**: Large language models provide high accuracy but slow responses.
**Solution**: Two-stage pipeline with self-optimization loop.

### Daytime Operations (Fast Response - Sub-Second)
```
User Query → Nemotron Orchestrator (Parse/Reason) → Phinance (Analyze) → Instant Response
         ↓                         ↓
   Action Log                Decision Log
         ↓_________________________↓
           Unified Activity Log
```

**Key Features**:
- Nemotron Orchestrator (7B) handles parsing and reasoning
- Phinance (3.8B) performs specialized financial analysis
- Combined processing time: ~2-3 seconds (vs 5-6s with single large model)
- User receives immediate, context-aware response

### Nighttime Optimization (Thorough Review - High Accuracy)
```
Every 15 mins: Check system idle status
   ↓
If idle (CPU<20%, GPU<15%, RAM<60GB):
   ↓
Wake 14-32B Model → Review all logs from past 7-14 days
   ↓
Apply corrections → Update RAG → Prune old logs
```

**Key Features**:
- Large model (14-32B) reviews all daytime decisions
- Corrects errors and improves categorization
- Updates RAG knowledge base with new patterns
- System gets progressively more accurate over time
- No impact on daytime performance

## How It Achieves Low Perceived Latency

### The Secret: Cognitive Division of Labor

```
┌─────────────────────────────────────────────────────────────┐
│                    LOW PERCEIVED LATENCY                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  User Query → Nemotron (Fast Parse) → Phinance (Fast Analyze)
│       ↓              ↓                         ↓
│  Instant Response ← Synthesized ← Structured Data
│       │              │                         │
│       ▼              ▼                         ▼
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  │  Action Log  │ │ Decision Log│ │  Result Log  │
│  └─────────────┘ └─────────────┘ └─────────────┘
│       ↓              ↓                         ↓
│  ┌─────────────────────────────────────────────────────────┐
│  │               Unified Activity Log                      │
│  └─────────────────────────────────────────────────────────┘
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              NIGHTTIME OPTIMIZATION (No User Impact)         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Every 15 mins: Check if system is idle                      │
│       ↓                                                        │
│  If idle → Wake 14-32B Model                                   │
│       ↓                                                        │
│  Review all logs from past 7-14 days                          │
│       ↓                                                        │
│  Apply corrections → Update RAG → Prune old logs              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Why This Works

1. **Fast Daytime Response**
   - Nemotron Orchestrator (7B): Quick parsing and intent understanding
   - Phinance (3.8B): Specialized financial analysis
   - Combined: ~2-3 seconds total processing time
   - User gets immediate, useful response

2. **Thorough Nighttime Review**
   - Large model (14-32B): Reviews all daytime decisions
   - Corrects errors without user involvement
   - Updates knowledge base for future accuracy
   - Runs only when system is completely idle

3. **Self-Improving System**
   - Daytime errors become nighttime learning opportunities
   - RAG knowledge base continuously improves
   - System accuracy increases over time
   - No retraining required

## Key Components

### 1. Resource Monitoring
- **Frequency**: Every 5 minutes
- **Metrics**: CPU, GPU (per card), RAM, Disk I/O
- **Idle Thresholds**: CPU<20%, GPU<15%, RAM<60GB
- **Pattern Learning**: Detects user's actual quiet hours

### 2. Intelligent Scheduler
- **Check Frequency**: Every 15 minutes
- **Lookback Window**: 15 minutes of metrics
- **Conflict Avoidance**: Only starts audit when system is truly idle
- **Adaptive Timing**: Learns optimal audit windows

### 3. Unified Logging System
- **Structure**: SQLite database with JSON blobs
- **Content**: All agent actions, reasoning traces, confidence scores
- **Retention**: 14 days detailed, then compressed summaries

### 4. Overnight Audit Process
- **Model**: 14-32B parameter model (GPU 1/3)
- **Scope**: Reviews all agent logs from past 7-14 days
- **Output**: Corrections, RAG updates, system insights
- **Pruning**: Weekly/biweekly removal of verified logs

## Implementation Components

### Required Implementation
1. **Resource Monitor**
   - Collects system metrics every 5 minutes
   - Detects idle periods
   - Learns quiet hour patterns

2. **Intelligent Scheduler**
   - Checks idle status every 15 minutes
   - Starts audit only when system is truly idle
   - Monitors during audit to avoid conflicts

3. **Unified Logger**
   - Logs all agent actions
   - Stores reasoning traces and confidence scores
   - Handles cross-agent insights

4. **Log Pruner**
   - Weekly/biweekly pruning of verified logs
   - Compresses old data
   - Maintains sustainable database size

## System Requirements

### Hardware
- **Storage**: 916GB NVMe (nvme0n1p1) - Fast enough for quick model loading
- **GPU**: Dual RTX 5060 Ti (32GB VRAM total) - Handles multiple models
- **RAM**: 128GB - Sufficient for large model inference

### Software
- **Ollama**: Model serving and management
- **SQLite**: Lightweight database for logging
- **Systemd**: Service management for scheduling

## Benefits

1. **Low Perceived Latency**: Users get instant responses from 7B models
2. **High Accuracy**: Nighttime audit corrects errors with 14-32B models
3. **Resource Efficiency**: Only uses big models when system is idle
4. **Self-Improving**: System gets smarter over time through corrections
5. **Audit Trail**: All decisions are traceable and reviewable

## Implementation Timeline

### Phase 1: Core Infrastructure (Week 1)
- [ ] Resource monitoring system
- [ ] Basic logging infrastructure
- [ ] Idle detection logic

### Phase 2: Audit System (Week 2)
- [ ] Nighttime audit prototype
- [ ] Correction mechanism
- [ ] RAG update integration

### Phase 3: Optimization (Week 3)
- [ ] Pattern learning from corrections
- [ ] Cross-agent insight generation
- [ ] Performance monitoring

### Phase 4: Deployment (Week 4)
- [ ] Systemd service integration
- [ ] Automated scheduling
- [ ] Monitoring dashboard

## Monitoring and Maintenance

### Weekly Tasks
- Review audit reports
- Check system resource usage patterns
- Verify log pruning is working correctly

### Monthly Tasks
- Analyze pattern learning effectiveness
- Review cross-agent insights
- Optimize RAG knowledge base

## Success Metrics

1. **Accuracy Improvement**: Measure correction rate over time
2. **Resource Utilization**: Track GPU usage efficiency
3. **Response Time**: Maintain sub-second daytime responses
4. **System Stability**: Monitor for conflicts or resource contention

This architecture provides the best of both worlds: fast responses during active use and thorough optimization during idle periods, all while maintaining a complete audit trail for traceability and continuous improvement.