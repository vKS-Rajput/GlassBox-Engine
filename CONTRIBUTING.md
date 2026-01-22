# Contributing to GlassBox

GlassBox accepts contributions, but not all contributions.

This document explains who should contribute, what kinds of contributions are welcome, and what will be rejected.

---

## Who Should Contribute

**Good contributors:**
- Engineers who value explainability
- People who read DESIGN.md first
- Those who understand "less is more"
- Bug fixers with test cases
- Documentation improvers

**Not a good fit:**
- "Move fast and break things" mentality
- ML enthusiasts who want to add models
- Feature creep advocates
- Anyone who thinks "just add a flag" is a solution

---

## Contribution Philosophy

> **Correctness over features. Transparency over convenience.**

Before writing code, ask:

1. Does this preserve the Evidence invariant?
2. Is this deterministic?
3. Can every output be explained?
4. Does this add complexity?
5. Will this be obvious in 2 years?

If you're unsure, open an issue first.

---

## Rules for Proposing Changes

### For Bug Fixes

1. Describe the bug
2. Provide a failing test case
3. Explain the fix
4. Ensure all 152+ tests pass
5. Do not add new dependencies

### For New Features

1. Open an issue first
2. Explain why this belongs in GlassBox
3. Reference DESIGN.md to justify the change
4. Wait for maintainer approval
5. Submit PR with tests

### For Documentation

1. Fix typos freely
2. Clarify confusing sections
3. Do not add marketing language
4. Keep the tone: calm, confident, honest

---

## What Gets Rejected

| Type of PR | Why It's Rejected |
|------------|-------------------|
| Adding ML/AI | Violates explainability requirement |
| Adding configuration flags | Creates hidden state |
| "Smart defaults" | Determinism over convenience |
| Personalization | No user state allowed |
| External API integrations | Requires careful Evidence design |
| Performance optimizations without tests | Correctness first |
| Breaking changes to Evidence | Immutable invariant |

---

## How to Add a New Signal Source

New signal sources are welcome but must follow the pattern.

### Requirements

1. **Input**: Raw content (XML, JSON, etc.)
2. **Output**: `Signal` objects with Evidence
3. **Gating**: Must pass through Phase 1 validation
4. **Rejection**: Must produce `Rejection` objects for failures
5. **Tests**: Minimum 10 test cases

### File Structure

```
glassbox/
├── ingestion/
│   ├── __init__.py
│   ├── rss.py          # Existing
│   └── lever.py        # New source
tests/
├── test_phase1_ingestion.py
└── test_phase1_lever.py  # New tests
```

### Code Pattern

```python
@dataclass
class LeverItem:
    """Raw item from Lever API."""
    title: str
    company: str
    url: str
    posted_at: datetime

def lever_item_to_signal(item: LeverItem) -> Signal:
    """Convert Lever item to Signal with Evidence."""
    # Must create proper signal_id, dedup_hash
    # Must preserve source_url for Evidence
    ...

def ingest_lever_jobs(api_response: dict) -> BatchIngestionResult:
    """Ingest Lever jobs through gating pipeline."""
    ...
```

---

## How to Add a New Enrichment Field

Enrichment fields add optional context.

### Requirements

1. Must have Evidence (INF type)
2. Must be optional (Entity valid without it)
3. Must have conservative confidence (≤0.8)
4. Must not modify required fields
5. Must fail gracefully

### Code Pattern

```python
def infer_new_field(
    text: str,
    source_evidence_id: str,
) -> Optional[Evidence]:
    """Infer new field from signal text."""
    
    # 1. Attempt inference
    result = some_deterministic_logic(text)
    
    if result is None:
        return None  # Fail gracefully
    
    # 2. Create Evidence with conservative confidence
    return create_inference(
        field_name="new_field",
        value=result,
        source_evidence_ids=[source_evidence_id],
        inference_rule="new_field_inference",
        confidence=0.65,  # Conservative
    )
```

---

## How to Add a New Scoring Component

Scoring components must be:
- Independently computable
- Deterministic
- Bounded (known min/max)
- Documented

### Code Pattern

```python
def compute_new_component(
    entity: Entity,
    signal: Optional[Signal] = None,
) -> ComponentScore:
    """Compute new scoring component."""
    
    # 1. Compute raw value
    raw_value = some_deterministic_logic(entity, signal)
    
    # 2. Map to bounded contribution
    if raw_value >= threshold_high:
        contribution = 10
        reason = "High new_component value"
    else:
        contribution = 5
        reason = "Normal new_component value"
    
    # 3. Return with evidence references
    return ComponentScore(
        name="new_component",
        raw_value=raw_value,
        contribution=contribution,
        evidence_ids=[...],  # Must reference Evidence
        reason=reason,
    )
```

---

## Testing Requirements

All PRs must:

1. Pass all existing tests
2. Add new tests for new functionality
3. Include edge case tests
4. Test rejection paths, not just happy paths

Run tests:
```bash
python -m pytest tests/ -v
```

Coverage expectations:
- New modules: >80% coverage
- Core modules: >90% coverage

---

## Code Style

- Python 3.10+
- Type hints required
- Docstrings for public functions
- No magic numbers (use named constants)
- Prefer dataclasses over dicts
- Prefer explicit over clever

---

## Review Process

1. All PRs require maintainer review
2. Architecture changes require DESIGN.md update
3. Breaking changes require version bump discussion
4. Documentation changes can be merged faster

---

## What Makes a Great Contribution

The best contributions:
- Fix a real bug with a test
- Clarify confusing documentation
- Add meaningful tests
- Reduce complexity
- Ask good questions in issues

The goal is not to add features. The goal is to make GlassBox more correct, more clear, and more trustworthy.

---

*Protect the architecture. It's the only thing that matters.*
