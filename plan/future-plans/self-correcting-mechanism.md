# 🤖 Self-Correcting Mechanism Design

## Overview

This document outlines a comprehensive self-correcting mechanism for the AI system, enabling automatic error detection, correction, and continuous improvement through a three-tier audit system.

## 1. Logging System Architecture

### Format Specification

**Recommended Format**: Structured JSON with confidence scores

```json
{
  "action_id": "act_20250101_001",
  "timestamp": "2025-01-01T14:23:45.123Z",
  "agent": "NemoAgent",
  "action_type": "intent_classification",
  "input": {
    "user_query": "Analyze my spending",
    "context": ["uploaded_chase_statement.pdf"]
  },
  "output": {
    "classified_intent": "SPECIALIST_ANALYSIS",
    "target_specialist": "phinance",
    "confidence": 0.87
  },
  "reasoning_trace": [
    "Detected 'analyze' + 'spending' keywords",
    "Context shows financial document upload",
    "No explicit consent yet recorded"
  ],
  "resource_usage": {
    "processing_time_ms": 124,
    "gpu_utilization": 15,
    "memory_mb": 48
  },
  "consent_state": {
    "user_confirmed": false,
    "required": true,
    "blocked": true
  }
}
```

### Storage Recommendation

**Database**: SQLite with JSON extension

```sql
CREATE TABLE agent_actions (
  id TEXT PRIMARY KEY,
  timestamp INTEGER,
  agent TEXT,
  action_type TEXT,
  input_json TEXT,
  output_json TEXT,
  confidence REAL,
  reasoning_trace TEXT,
  resource_usage TEXT,
  consent_state TEXT,
  corrected_by TEXT,
  correction_reason TEXT
);
```

**Retention Policy**:
- 30 days: Detailed logs
- 90 days: Compressed summaries
- 1 year: Aggregated statistics

## 2. Backtracking Triggers

### Trigger Conditions

1. **Low Confidence**: `confidence < 0.75`
2. **User Disagreement**: Explicit user correction
3. **Inconsistent Results**: Same input → different outputs (>20% variance)
4. **Resource Anomalies**: Unexpectedly high usage (>1.5x expected)
5. **Timeout Exceeded**: Processing > 5 seconds
6. **Error Recovery**: After any failure

### Implementation

```python
class BacktrackMonitor:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.triggers = {
            'low_confidence': 0.75,
            'user_disagreement': True,
            'inconsistency': 0.20,
            'resource_anomaly': 1.5,
            'timeout': 5.0,
            'error_recovery': True
        }

    def should_backtrack(self, action_id):
        """Check if action needs review"""
        action = self._get_action(action_id)

        if action['confidence'] < self.triggers['low_confidence']:
            return {'reason': 'low_confidence', 'severity': 'medium'}

        if self._has_user_disagreement(action_id):
            return {'reason': 'user_disagreement', 'severity': 'high'}

        if self._check_inconsistency(action_id):
            return {'reason': 'inconsistency', 'severity': 'medium'}

        return None
```

## 3. Night Auditor Architecture

### Three-Tier Audit System

```python
class AuditSystem:
    def __init__(self):
        self.tier1 = OllamaClient("qwen2.5:14b")  # First pass
        self.tier2 = OllamaClient("qwen2.5:32b")  # Conflict resolution
        self.tier3 = HumanReviewQueue()          # Final arbiter

    async def audit_day_actions(self, date):
        """Three-tier audit process"""
        actions = self._load_days_actions(date)
        
        # Tier 1: Initial review by 14B model
        tier1_results = await self._tier1_audit(actions)

        # Tier 2: Review conflicts and low-confidence
        conflicts = self._find_conflicts(tier1_results)
        tier2_results = await self._tier2_audit(conflicts)

        # Tier 3: Human review for remaining issues
        unresolved = self._find_unresolved(tier2_results)
        await self._tier3_audit(unresolved)

        # Apply corrections
        self._apply_corrections(tier1_results, tier2_results)
```

### Audit Process Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      NIGHT AUDIT PROCESS FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Load day's actions from database                                        │
│       ↓                                                                      │
│  2. Tier 1: 14B model reviews all actions                                   │
│       │                                                                      │
│       ▼                                                                      │
│  3. Identify conflicts and low-confidence cases                             │
│       │                                                                      │
│       ▼                                                                      │
│  4. Tier 2: 32B model resolves conflicts                                    │
│       │                                                                      │
│       ▼                                                                      │
│  5. Identify remaining unresolved issues                                    │
│       │                                                                      │
│       ▼                                                                      │
│  6. Tier 3: Queue for human review                                          │
│       │                                                                      │
│       ▼                                                                      │
│  7. Apply corrections to database                                           │
│       │                                                                      │
│       ▼                                                                      │
│  8. Update RAG knowledge base                                               │
│       │                                                                      │
│       ▼                                                                      │
│  9. Notify admin of human review needs                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4. Conflict Resolution Strategy

### Confidence-Weighted Voting

```python
class ConflictResolver:
    def __init__(self):
        self.weights = {
            'day_model': 0.6,    # Original decision
            'night_model': 0.8,   # Audit review
            'human': 1.0          # Human override
        }

    def resolve(self, original, audit, human=None):
        """Weighted confidence resolution"""
        scores = {
            'original': original['confidence'] * self.weights['day_model'],
            'audit': audit['confidence'] * self.weights['night_model']
        }

        if human:
            scores['human'] = human['confidence'] * self.weights['human']

        winner = max(scores, key=scores.get)
        
        if winner == 'audit':
            return self._apply_audit_correction(original, audit)
        elif winner == 'human':
            return self._apply_human_override(original, human)
        else:
            return self._keep_original(original)
```

### Resolution Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONFLICT RESOLUTION WORKFLOW                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Day Model (0.6): "Category = Dining (confidence: 0.72)"                   │
│       ↓                                                                      │
│  Night Model (0.8): "Category = Groceries (confidence: 0.88)"              │
│       ↓                                                                      │
│  Calculate weighted scores:                                                 │
│     Dining: 0.72 × 0.6 = 0.432                                              │
│     Groceries: 0.88 × 0.8 = 0.704                                           │
│       ↓                                                                      │
│  Winner: Groceries (higher weighted score)                                 │
│       ↓                                                                      │
│  Apply correction to database                                               │
│       ↓                                                                      │
│  Update RAG with new pattern                                                │
│       ↓                                                                      │
│  Notify user of correction (if appropriate)                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5. Confidence Scoring System

### Action Confidence Calculation

```python
class ConfidenceCalculator:
    @staticmethod
    def calculate_action_confidence(action):
        """Multi-factor confidence score"""
        base = 0.5  # Baseline

        # Add factors
        if action['has_consent']:
            base += 0.1

        if action['reasoning_depth'] > 3:
            base += 0.1

        if action['similar_cases'] > 5:
            base += 0.1

        if not action['flags']:
            base += 0.1

        # Penalize
        if action['resource_usage']['anomaly']:
            base -= 0.2

        if action['processing_time'] > 3.0:
            base -= 0.1

        return min(max(base, 0.1), 0.99)  # Clamp to 0.1-0.99
```

### Correction Confidence

```python
@staticmethod
def calculate_correction_confidence(original, correction):
    """Confidence in correction"""
    improvement = correction['confidence'] - original['confidence']
    
    base = 0.6
    
    if improvement > 0.2:
        base += 0.1

    if correction['evidence_count'] > 3:
        base += 0.1

    if correction['reviewed_by_human']:
        base += 0.2

    return min(max(base, 0.5), 0.95)
```

## Implementation Roadmap

### Phase 1: Logging Infrastructure

**Week 1 Tasks**:
```bash
# 1. Set up SQLite database
sqlite3 /home/ryzen/projects/home-ai/logs/agent_actions.db < schema.sql

# 2. Create logger service
touch logger_service.py
# - Implements structured logging
# - Handles confidence scoring
# - Manages database connections

# 3. Integrate with agents
# - Add logging to NemoAgent
# - Add logging to Phinance adapter
# - Add logging to orchestrator
```

### Phase 2: Backtrack Monitor

**Week 2 Tasks**:
```bash
# 1. Implement trigger system
touch backtrack_monitor.py
# - Low confidence detection
# - Inconsistency detection
# - Resource anomaly detection

# 2. Create correction interface
touch correction_engine.py
# - Database updates
# - Notification system
# - User communication
```

### Phase 3: Night Auditor

**Week 3 Tasks**:
```bash
# 1. Set up audit scheduler
touch audit_scheduler.py
# - Idle detection
# - Resource monitoring
# - Audit triggering

# 2. Implement tiered audit
touch audit_system.py
# - Tier 1: 14B model
# - Tier 2: 32B model
# - Tier 3: Human queue

# 3. Create correction applier
touch correction_applier.py
# - Database updates
# - RAG updates
# - Notification system
```

### Phase 4: Conflict Resolution

**Week 4 Tasks**:
```bash
# 1. Implement resolver
touch conflict_resolver.py
# - Weighted voting
# - Confidence calculation
# - Correction application

# 2. Add human review interface
touch human_review.py
# - Admin dashboard
# - Notification system
# - Resolution interface

# 3. Test end-to-end
# - Simulate conflicts
# - Test resolution
# - Validate corrections
```

## Key Design Decisions

### 1. Who Audits the Auditor?
**Solution**: Three-tier system with escalation
- Tier 1: 14B model (most cases)
- Tier 2: 32B model (conflicts)
- Tier 3: Human review (final arbiter)

### 2. Conflict Resolution
**Solution**: Confidence-weighted voting
- Day model: 0.6 weight
- Night model: 0.8 weight
- Human: 1.0 weight
- Winner takes all, with correction logging

### 3. Storage Strategy
**Solution**: SQLite with pruning
- Keep 30 days detailed logs
- Keep 90 days compressed summaries
- Prune verified corrections after 14 days

### 4. Trigger Sensitivity
**Solution**: Adjustable thresholds
- Low confidence: < 0.75
- High variance: > 20%
- Resource anomaly: > 1.5x expected
- Timeout: > 5 seconds

## Success Metrics

### 1. Correction Rate
- **Target**: 5-10% of actions corrected
- **Measure**: Weekly audit effectiveness

### 2. Confidence Improvement
- **Target**: +0.15 average confidence gain
- **Measure**: Pre vs post correction scores

### 3. Human Intervention Rate
- **Target**: < 2% of conflicts
- **Measure**: Tier 3 escalation rate

### 4. System Accuracy
- **Target**: 95% final accuracy
- **Measure**: Post-correction validation

## Benefits of This Approach

1. **Continuous Improvement**: System gets better over time
2. **Error Recovery**: Automatic correction of mistakes
3. **Quality Assurance**: Nightly review catches issues
4. **Audit Trail**: Complete history of all decisions
5. **Human Oversight**: Final arbiter for difficult cases
6. **Resource Efficiency**: Only uses large models when idle

## Risks and Mitigations

### Risk 1: Audit Overhead
**Mitigation**: Only audit when system is idle

### Risk 2: Correction Loops
**Mitigation**: Limit correction attempts (max 3)

### Risk 3: Human Review Bottleneck
**Mitigation**: Only escalate truly difficult cases

### Risk 4: Database Bloat
**Mitigation**: Aggressive pruning policy

### Risk 5: False Positives
**Mitigation**: Adjustable confidence thresholds

## Conclusion

This self-correcting mechanism provides a **comprehensive, implementable** approach to automatic error detection and correction. By combining structured logging, confidence scoring, tiered auditing, and conflict resolution, the system can continuously improve while maintaining accountability and transparency.
