# 📋 RemAssist — Unified Task Queue
*Supersedes previous `next-tasks.md` and `NEXT_TASKS.md`. All queues now live here.*

_Last updated: December 23, 2025_

---

## 🔍 Current System Snapshot
- **✅ Working:** `secure_webui.py` on port 8080, API endpoints, basic monitoring stack, remote access (Tailscale + fixed port 8080), agent_webui-based interaction UI, services monitor dashboard.
- **⚠️ Needs Attention:** `main.py` templates (Jinja2/CSS conflicts), advanced features (multi-user auth, PDF upload flows in UI), PulseAudio stability, production security hardening.
- **🆕 New Requirements:** Finance Intelligence MVP (v2) build-out, Merchant Intelligence Dictionary for recurring statement terms, per-user data isolation for household deployments.

---

## 🚀 Immediate Priority Tasks
### 1. PulseAudio Stability Resolution
- [ ] Restart PulseAudio service cleanly and verify no respawn loops
- [ ] Inspect audio device conflicts / permissions
- [ ] Run end-to-end audio output test (TTS → speakers)
- [ ] Collect logs for regression tracking

### 2. TTS System Validation
- [ ] Download & cache VibeVoice model (>500 MB)
- [ ] Exercise VibeVoice TTS in isolation
- [ ] Verify API TTS endpoints (success + error cases)
- [ ] Document audio troubleshooting checklist

### 3. Remote Access & Web UI Verification
- [ ] Re-test setup script in sandbox
- [ ] Reconfirm Tailscale link + IP whitelist (100.84.92.33)
- [ ] Validate service monitor dashboard & agent web UI end-to-end
- [ ] Configure Nginx for remote access (Ready to Run)
- [ ] Finalize design templates (monitoring + chat)
- [ ] Produce services configuration addendum

---

## 🧠 Finance Intelligence MVP (v2) Build Queue
Refer to `FINANCE_MVP_PLAN_V2.md` for full spec. Key execution tasks:

### A. Day 0 / Prep (Status)
- [x] Document refreshed plan (hardware, models, household requirements)
- [ ] Stand up `finance-agent/` structure + venv

### B. Stage 1 — Foundation
- [ ] Implement `src/storage.py` (SQLite schema, merchant dictionary tables, user ownership metadata)
- [ ] Implement `src/models.py` (async Ollama clients pinned to GPU 0/1)
- [ ] Insert mock transaction + verify both models respond

### C. Stage 2 — Extraction Engine
- [ ] Build `src/parser.py` with staged awareness (`get_identity_context`, `get_structural_summary`, `extract_transactions`)
- [ ] Add Apple Card / Chase regex patterns + Nemotron fallback
- [ ] Wire Merchant Intelligence Dictionary lookups before LLM calls

### D. Stage 3 — Interleaved Orchestrator
- [ ] Implement `src/orchestrator.py` state machine streaming Stage 1→3 context to Nemotron
- [ ] Add per-user session routing + household access controls
- [ ] Generate `transactions.json` / `analysis.json` per user for `soa_dashboard.html`

### E. Post-MVP Safeguards
- [ ] Build role-based sharing rules (primary admin vs household member)
- [ ] Implement dictionary maintenance utility (promote high-confidence mappings, flag conflicts)
- [ ] Prepare sample data + demo script highlighting staged awareness UX

---

## 🌐 Web Interface & System Enhancements
### Web UI Improvements
- [ ] Add auth + session management to agent_webui.py / secure_webui.py
- [ ] Integrate PDF ingestion controls + processing feedback
- [ ] Extend service control + monitoring widgets
- [ ] Polish UI/UX (layout, theme, responsive behavior)

### API & Security Hardening
- [ ] Add API key auth + rate limiting
- [ ] Expand structured logging + error correlation
- [ ] Implement TLS / reverse proxy hardening
- [ ] Harden input validation paths

### Template Remediation (main.py)
- [ ] Audit current Jinja2 template/CSS pipeline
- [ ] Decide: external CSS vs alternate templating engine vs rewrite
- [ ] Prototype fix and regression test web views

---

## 🔊 Audio System Roadmap
- [ ] Configure persistent audio device permissions & priority
- [ ] Implement fallback/alternate TTS backend selection
- [ ] Create audio troubleshooting + recovery playbook
- [ ] Test multi-backend switching under load

---

## 📚 Documentation & Testing
### Documentation
- [ ] Remote access user guide
- [ ] TTS setup + troubleshooting doc
- [ ] Deployment + recovery guide
- [ ] Update SERVICES_CONFIG.md as features land

### Testing & Performance
- [ ] API + web regression suite
- [ ] Remote access reproducibility tests
- [ ] Performance benchmarking under concurrent workloads
- [ ] Load test finance pipeline (PDF batches)

---

## 🧭 Future / Backlog
- Multi-user voice command interface
- Mobile companion interface
- Calendar/email integrations
- Plugin / extension architecture
- Nightly self-healing audit system
- Resource-aware scheduling + observability upgrades

---

## ✅ Recently Completed
- secure_webui.py validated on port 8080
- Template issues documented in `TEMPLATE_ISSUES.md`
- Services inventory captured in `SERVICES_CONFIG.md`
- Agent interaction UI shipped (`agent_webui.py`)
- Remote access IP whitelist & directory structure fixes
- Finance Intelligence MVP spec refreshed (v2)

---

> **Note:** This file mirrors `NEXT_TASKS.md`. Update either file to keep them in sync.
