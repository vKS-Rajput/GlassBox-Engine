# GlassBox Trust Model

This document explains why GlassBox is designed to be trustworthy — and what kinds of trust it does not provide.

---

## The Trust Problem

Lead generation tools ask you to trust:
- Their data sources (often undisclosed)
- Their scoring algorithms (proprietary)
- Their enrichment providers (black boxes)
- Their freshness claims (unverifiable)

GlassBox takes a different approach: **don't trust, verify**.

---

## How Evidence Lineage Works

Every piece of data in GlassBox carries its history.

### Example: A Company Name

```
Evidence:
  field_name: company_name
  value: "CloudCo"
  evidence_type: INF (inference)
  meta:
    confidence: 0.75
    timestamp: 2026-01-22T10:00:00
    source_evidence_ids: ["evt_abc123"]
    inference_rule: "extracted_from_url_slug"
```

You can trace:
1. **What**: The value "CloudCo"
2. **How**: Extracted from URL slug
3. **When**: January 22, 2026
4. **Confidence**: 75%
5. **Source**: The original signal (evt_abc123)

No field exists without this chain.

---

## How Confidence Is Assigned

Confidence is not a guess. It follows explicit rules.

### Base Confidence by Evidence Type

| Type | Base Confidence | Rationale |
|------|-----------------|-----------|
| OBS (Observation) | 0.95 | Direct scrape from verifiable URL |
| INF (Inference) | 0.70 | Derived via rule, may have errors |
| API (Third-Party) | 0.85 | External service, generally reliable |

### Confidence Decay

Some fields decay over time:

| Field | Decay Rate | Invalidation |
|-------|------------|--------------|
| intent_signal | -0.25 per 7 days | Reaches 0 at 28 days |
| contact_email | -0.10 per 30 days | Slow decay |
| company_name | No decay | Static identifier |
| domain | No decay | Static identifier |

This means a 3-week-old hiring signal automatically has lower confidence than a fresh one.

---

## Why Every Rejection Is Explicit

GlassBox does not silently filter data. Every rejection includes:

1. **Rule**: Which rejection rule was triggered (R1-R8)
2. **Reason**: Human-readable explanation
3. **Signal ID**: Which input caused the rejection
4. **Snippet**: First 500 characters for debugging

Example rejection:
```
[R3_MISSING_ENTITY] Ambiguous entity: Multiple company references detected in signal. Cannot determine primary company.
Signal ID: sig_abc123
Snippet: "Join Acme Corp or our partner company Globex..."
```

You can audit every decision.

---

## Why Explanations Match Logic

The `explain` command does not generate marketing copy. It reads the actual score breakdown.

### Code Path

```
RankedLead.get_explanation()
  → Reads ScoreBreakdown
    → Iterates ComponentScore list
      → Returns each component.reason verbatim
```

There is no separate "explanation generator" that might diverge from the scorer. The same data structure produces both the score and the explanation.

---

## Errors GlassBox Avoids

| Error Type | How GlassBox Prevents It |
|------------|-------------------------|
| Silent failures | All rejections are logged |
| Orphan data | Evidence requirement prevents untracked fields |
| Score drift | No learned weights, no personalization |
| Stale recommendations | Confidence decay on time-sensitive fields |
| Black-box rankings | Every component is visible |
| Hidden biases | Deterministic rules, no training data |

---

## Errors GlassBox Does NOT Prevent

Being trustworthy means being honest about limitations.

| Error Type | Why It Can Still Occur |
|------------|------------------------|
| Incorrect extraction | Regex/heuristics may misparse edge cases |
| Missing signals | Only processes what's in the RSS feed |
| Wrong company match | URL slug inference may be wrong |
| Missed intent | Keyword lists are not exhaustive |
| Domain misattribution | Subdomains may not match company |

These are known limitations, not bugs. GlassBox responds to them with:
- Low confidence scores
- Explicit rejection when uncertain
- Visible evidence for manual review

---

## The Skeptic's Checklist

If you're skeptical of GlassBox (you should be), verify these claims:

| Claim | How to Verify |
|-------|---------------|
| Every field has Evidence | Read `glassbox/domain.py` — Entity requires Evidence |
| Scores are deterministic | Run pipeline twice, compare results |
| Rejections are visible | Check `result.rejections` after pipeline run |
| Explanations match logic | Compare `explain` output with `ScoreBreakdown` |
| No hidden weights | Read `glassbox/ranking/components.py` — all constants are visible |
| CLI is read-only | Check `main.py` — no mutation of pipeline logic |

---

## What "Trust" Means Here

GlassBox does not ask you to trust its accuracy.
GlassBox asks you to trust its **transparency**.

- You may find leads are wrong.
- You may find extraction is imperfect.
- You may find scores don't match your intuition.

But you will always be able to see **why**.

---

*Trust is not about being right. Trust is about being verifiable.*
