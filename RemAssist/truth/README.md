# Source of Truth Documents

These are the canonical documents for the RemAssist/SOA1 project. **Read these first.**

| Document | Purpose | Read When |
|----------|---------|-----------|
| `PROGRESSIVE_FLOW.md` | 4-phase upload/analysis pipeline | Any upload, batch, or analysis work |
| `IMPLEMENTATION_GUIDE.md` | Core invariants, consent rules | Any code change |
| `LLM_DRIVEN_RESPONSES.md` | All responses from LLM, not hardcoded | User-facing text work |
| `HARDWARE_SPECS.md` | VRAM limits, GPU allocation | Adding models or GPU features |
| `HYBRID_EXTRACTION_ARCHITECTURE.md` | Python calculates, LLM provides insights | Finance pipeline work |
| `PROJECT_STATE.md` | Current system state, services, ports | Understanding the system |

## Priority Order

If documents conflict, follow this priority:
1. `IMPLEMENTATION_GUIDE.md` (highest)
2. `PROGRESSIVE_FLOW.md`
3. Everything else

## Key Rules

- **Transactions extracted by Python regex, NOT LLM**
- **Transactions saved to DB ONLY after user consent**
- **All user-facing text from LLM, never hardcoded**
- **Upload ≠ consent, Silence ≠ consent**
