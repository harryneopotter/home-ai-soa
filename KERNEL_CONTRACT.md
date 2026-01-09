# Kernel Contract v0.1

## Intent

The Kernel Contract defines the frozen interfaces between SOA1's orchestrator (kernel) and its agents/specialists. It guarantees that agents can rely on stable CONTROL header schemas, capability semantics, and memory type rules without breaking changes. Any component built against this contract will continue to work until an explicit version bump.

## Tagged Commit

```
git show kernel-contract-v0.1
```

Commit: `62ec823` — "chore: strengthen BOOT_CONTEXT enforcement + update docs"

## What's Frozen

1. **CONTROL schema** (`soa1/control_header.py`) — PipelineStage enum, build_control_header() signature
2. **Capability semantics** (`soa1/orchestrator.py`) — 6 capabilities, implicit vs explicit consent rules
3. **Memory type rules** (`soa1/memory/memory_manager.py`) — BOOT_CONTEXT readonly, SESSION ephemeral, USER_PROFILE durable

## Version Bump Rules

| Change Type | Action Required |
|-------------|-----------------|
| Add new optional field to CONTROL | Patch bump (v0.1 → v0.1.1) |
| Add new capability | Minor bump (v0.1 → v0.2) |
| Add new memory type | Minor bump (v0.1 → v0.2) |
| Change existing field semantics | Major bump (v0.1 → v1.0) |
| Remove or rename existing field | Major bump (v0.1 → v1.0) |
| Change capability consent level | Major bump (v0.1 → v1.0) |

**Process**: Update this file, create new annotated tag, update `RemAssist/History.md`.
