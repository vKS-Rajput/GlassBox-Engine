# GlassBox Discovery Engine

**An explainable, logic-first client discovery engine for freelancers.**

GlassBox finds potential clients from public signals (job postings, funding announcements, hiring pages) and ranks them with full transparency. Every score is decomposable. Every rejection is explained. Nothing is hidden.

---

## What Problem Does This Solve?

Freelancers waste hours on lead research. Existing tools are either:
- **Black boxes** (scores you can't understand)
- **Data scrapers** (raw info with no prioritization)
- **Paid SaaS** (expensive, opaque, vendor-locked)

GlassBox is different: **every lead comes with a citation**.

### What GlassBox Does
- Ingests public signals (RSS job feeds)
- Resolves companies from signals
- Enriches with optional context
- Ranks leads with transparent scoring
- Explains every decision

### What GlassBox Does NOT Do
- Scrape behind logins
- Use ML or AI for decisions
- Provide "smart" recommendations
- Automate outreach
- Store data persistently
- Guarantee accuracy

---

## Who Is This For?

**Good fit:**
- Freelancers who want transparent lead discovery
- Engineers who value explainability over magic
- People who distrust black-box scoring

**Not a good fit:**
- Users who want one-click automation
- Users who want ML-powered predictions
- Users who need enterprise-scale volume
- Users who expect guaranteed leads

---

## Core Philosophy

### Glass Box, Not Black Box

Every piece of data in GlassBox has:
- **Evidence**: Where it came from
- **Confidence**: How certain we are
- **Lineage**: What it was derived from

If something cannot be explained, it does not exist in the system.

### Precision Over Recall

GlassBox aggressively rejects ambiguous data. We prefer:
- Fewer, higher-quality leads
- Explicit rejections over silent failures
- "I don't know" over "probably this"

### Determinism Over Learning

Scoring is rule-based, not trained. The same input always produces the same output. There are no tuning knobs, no personalization, no drift.

---

## Pipeline Overview

```
RSS Feed → [Phase 1] → Signals → [Phase 2] → Entities → [Phase 3] → Enriched
                                                                        ↓
CLI Output ← [Phase 5A] ← Ranked Leads ← [Phase 4] ←──────────────────────
```

| Phase | Name | Purpose |
|-------|------|---------|
| 0 | Evidence Ledger | Core data contract (all fields need Evidence) |
| 1 | Signal Ingestion | RSS parsing with gating |
| 2 | Entity Resolution | Company extraction with ambiguity rejection |
| 3 | Waterfall Enrichment | Optional context (industry, size, country) |
| 4 | Lead Ranking | Deterministic scoring with full breakdown |
| 5A | Public Alpha CLI | User-facing interface |

---

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/glassbox-engine.git
cd glassbox-engine

# Install dependencies (Python 3.10+)
pip install -e .

# Run tests
python -m pytest tests/ -v
```

---

## Usage

After installation, the `glassbox` command is available:

### Run the Pipeline

```bash
glassbox run
```

Output:
```
GlassBox Discovery Engine
==================================================
Running pipeline...

STATISTICS:
  Signals processed: 3
  Signals accepted:  2
  Entities resolved: 1
  Entities rejected: 1

REJECTIONS (for audit):
  • [missing_entity] Ambiguous entity: Multiple company references...

Run 'glassbox leads' to see ranked leads.
```

### View Ranked Leads

```bash
glassbox leads
```

Output:
```
GlassBox — Ranked Leads
======================================================================

[A-TIER] | Score:    88 | CloudCo (cloudco.com) | ID: e8ece688

Total: 1 leads

Use 'glassbox explain <id>' for detailed explanation.
```

### Explain a Lead

```bash
glassbox explain e8ece688
```

Output:
```
**CloudCo** is ranked as Tier A with a score of 88/95.

**Score Breakdown:**
- Detected hiring intent signal (+40 points)
- Very fresh signal (0 days old) (+25 points)
- Good evidence confidence (75%) (+15 points)
- Entity has 3 fields (company_name, domain, industry) (+8 points)
- Clean signal, no uncertainty markers

**Summary:** This is a high-priority lead with strong signals.
```

### View Evidence Lineage

```bash
glassbox evidence e8ece688
```

---

## Limitations

These are not bugs. They are intentional constraints.

| Limitation | Why |
|------------|-----|
| Only RSS input | Phase 1 scope; other sources require new modules |
| No persistence | Read-only architecture; storage is Phase 5B |
| No search | Indexing is not implemented |
| No API | Local CLI only for now |
| Conservative extraction | Ambiguity is rejected, not guessed |
| No contact enrichment | Requires external APIs (future phase) |

---

## Roadmap

> **These are not promises. They are directions.**

- [ ] Phase 5B: SQLite storage
- [ ] Phase 6: Search & filtering
- [ ] Additional signal sources (Lever, Crunchbase)
- [ ] Contact enrichment (with Evidence)
- [ ] Optional local API

---

## Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Current status: 152 tests passing
```

---

## Further Reading

- [DESIGN.md](./DESIGN.md) — Architecture & invariants
- [PIPELINE.md](./PIPELINE.md) — Phase-by-phase walkthrough
- [TRUST_MODEL.md](./TRUST_MODEL.md) — Why you should trust this system
- [CONTRIBUTING.md](./CONTRIBUTING.md) — How to contribute safely

---

## License

MIT License. See [LICENSE](./LICENSE).

---

*GlassBox is intentionally conservative, explainable, and boring — because trust scales better than hype.*
