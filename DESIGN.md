# GlassBox Design Document

This document defends the architecture of GlassBox. Read this before proposing changes.

---

## System Goals

1. **Explainability**: Every output can be traced to its source
2. **Determinism**: Same input always produces same output
3. **Precision**: Reject ambiguity rather than guess
4. **Transparency**: No hidden logic, no black boxes
5. **Auditability**: Every rejection is logged with reason

---

## Non-Goals

These are intentionally excluded:

| Non-Goal | Reason |
|----------|--------|
| High recall | Precision is prioritized; false positives erode trust |
| ML/AI decisions | Cannot be explained line-by-line |
| Personalization | Creates hidden state and drift |
| Automation | Humans decide, system informs |
| Speed optimization | Correctness first |
| Scale | Designed for individual freelancers |

---

## Core Invariants

### 1. Evidence Ledger

> **No field, attribute, inference, or score may exist without Evidence.**

This is the foundational invariant. Every piece of data has:

```python
@dataclass
class Evidence:
    evidence_id: str        # Unique identifier
    field_name: str         # What this represents
    value: Any              # The actual data
    evidence_type: EvidenceType  # OBS, INF, or API
    meta: EvidenceMeta      # Timestamp, confidence, lineage
```

Evidence types:
- **OBS** (Observation): Scraped from verifiable URL
- **INF** (Inference): Derived from other Evidence via documented rule
- **API** (Third-Party): From external service with known lineage

### 2. Rejection Philosophy

> **Reject early, reject explicitly, reject with reason.**

Hard rejection rules (R1-R8):
- R1: No intent signal
- R2: Stale signal (>30 days)
- R3: Missing entity
- R4: Invalid domain
- R5: Out-of-scope industry
- R6: Size mismatch
- R7: LLM failure
- R8: Missing evidence (system invariant violation)

Rejection is not failure. Rejection is the system working correctly.

### 3. Determinism

> **The same input must always produce the same output.**

There are:
- No random seeds
- No learned weights
- No user preferences
- No A/B testing
- No time-dependent logic (except explicit staleness)

---

## Why ML and Vectors Are Excluded

| Technique | Problem for GlassBox |
|-----------|---------------------|
| Embeddings | Cannot explain why two things are "similar" |
| Classification models | Confidence scores are not probabilities |
| LLM extraction | Hallucination risk; cannot cite sources |
| Recommendation engines | Create filter bubbles; hidden state |

GlassBox uses ML only for extraction (future), never for decisions.

---

## Why Enrichment Is Optional and Defensive

Enrichment (Phase 3) adds context to resolved entities. But:

- Enrichment **cannot create** an entity
- Enrichment **cannot rescue** a rejected entity
- Enrichment **cannot modify** required fields
- Failed enrichment **leaves the entity unchanged**

This ensures the core entity resolution remains pure.

---

## Why Ranking Is Advisory

Scores exist to help prioritization, not to make decisions.

Properties of ranking:
- **Decomposable**: Each component is visible
- **Bounded**: Known min/max for each component
- **Stable**: Same inputs = same rank
- **Non-authoritative**: The freelancer decides

Ranking does not:
- Hide low-scoring leads
- Auto-dismiss anything
- Learn from user behavior
- Optimize for engagement

---

## Trust Boundaries

### What Can Change
- New signal sources (with proper Evidence)
- New enrichment fields (with Evidence)
- New rejection rules (explicit, documented)
- Output formatting

### What Cannot Change
- Evidence requirement (immutable invariant)
- Rejection philosophy (explicit > silent)
- Determinism (no learned state)
- Read-only interface (CLI cannot modify logic)

---

## Failure Philosophy

> **Failure should be visible, explicit, and recoverable.**

| Situation | Response |
|-----------|----------|
| Unparseable RSS | Return empty result, log error |
| Ambiguous company | Reject with R3_MISSING_ENTITY |
| Multiple domains | Reject with explanation |
| Low confidence | Assign lower score, explain why |
| Enrichment fails | Keep entity unchanged |

The system never:
- Retries silently
- Guesses when uncertain
- Hides rejections
- Pretends to succeed

---

## How GlassBox Differs from Lead-Gen SaaS

| Aspect | Typical SaaS | GlassBox |
|--------|--------------|----------|
| Scoring | Proprietary algorithm | Transparent components |
| Data source | Aggregated databases | Public signals only |
| Enrichment | Black-box APIs | Deterministic rules |
| Personalization | Heavy | None |
| Persistence | Cloud database | None (in-memory) |
| Pricing | Per-lead or subscription | Free/open-source |
| Trust model | "Trust us" | "Verify yourself" |

---

## Extending GlassBox

Before adding features, ask:

1. Does this require Evidence?
2. Can it be explained line-by-line?
3. Does it preserve determinism?
4. Does it respect the rejection philosophy?
5. Does it keep the interface read-only?

If any answer is "no" or "I'm not sure", the feature does not belong in GlassBox.

---

*The architecture is the product. Protect it.*
