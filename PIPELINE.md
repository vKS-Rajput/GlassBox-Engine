# GlassBox Pipeline Documentation

This document describes each phase of the GlassBox pipeline in detail.

---

## Overview

```
[Input] → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5A → [Output]
           ↓          ↓         ↓          ↓           ↓
        Signals → Entities → Enriched → Ranked → CLI Display
```

Each phase has:
- Clear inputs and outputs
- Explicit rejection rules
- Documented limitations

---

## Phase 0: Evidence Ledger

### Purpose
Establish the core data contract. Every field must have Evidence.

### Key Components

```python
class EvidenceType(Enum):
    OBS = "observation"   # Direct scrape from URL
    INF = "inference"     # Derived via documented rule
    API = "third_party"   # From external service
```

### Confidence Values
- OBS: 0.95 base
- INF: 0.70 base
- API: 0.85 base (or provider confidence)

### Decay Rules
- Intent signals: -0.25 per 7 days
- Contact emails: -0.10 per 30 days
- Company/domain: No decay

### What Is NOT Done
- No storage (Evidence exists in memory only)
- No indexing
- No search

### Why This Matters
Without Evidence, data is just noise. The ledger ensures every piece of information can be traced to its source.

---

## Phase 1: Signal Ingestion

### Purpose
Convert raw RSS feeds into validated Signal objects.

### Inputs
- RSS XML content
- Feed source URL

### Outputs
- List of accepted `Signal` objects
- List of `Rejection` objects

### Processing Steps
1. Parse RSS XML
2. Extract title, link, description, pubDate
3. Normalize text (strip HTML, collapse whitespace)
4. Generate signal ID and dedup hash
5. Pass through gating

### Rejection Rules Applied
- R1: No intent signal (empty text)
- R2: Stale signal (>30 days)

### What Is NOT Done
- No scraping of linked pages
- No JavaScript rendering
- No authentication
- No rate limiting (single feed only)

### Why This Matters
Signals are the raw material. Bad signals = bad leads. Aggressive filtering here prevents pollution downstream.

---

## Phase 2: Entity Resolution

### Purpose
Extract company identity from signals with strict validation.

### Inputs
- Validated `Signal` objects

### Outputs
- Resolved `Entity` objects
- `Rejection` objects for failed resolution

### Processing Steps
1. Extract company name (from signal text or URL slug)
2. Extract domain (from signal text or URL)
3. Validate domain (TLD whitelist, blacklist checks)
4. Check for ambiguity (multiple companies/domains)
5. Create Entity with Evidence

### Rejection Rules Applied
- R3: Missing entity (no company or domain found)
- R4: Invalid domain (personal email, URL shortener, job board)

### Domain Validation
**Blacklisted:**
- Personal emails (gmail.com, yahoo.com, etc.)
- URL shorteners (bit.ly, tinyurl.com)
- Job boards (indeed.com, linkedin.com)

**Whitelist TLDs:**
- com, org, net, io, co, ai, dev, tech, app, etc.

### What Is NOT Done
- No DNS resolution
- No WHOIS lookup
- No website scraping
- No guessing when ambiguous

### Why This Matters
Entity resolution is the hardest problem. An incorrect company association would undermine all downstream value. Ambiguity rejection is aggressive by design.

---

## Phase 3: Waterfall Enrichment

### Purpose
Add optional context to entities without weakening trust.

### Inputs
- Resolved `Entity` objects
- Original `Signal` objects

### Outputs
- Enriched `Entity` objects (same reference, new fields)
- Enrichment status (success/partial/failed)

### Enrichment Fields

| Field | Method | Confidence |
|-------|--------|------------|
| industry | Keyword mapping | 0.70 |
| company_size_range | Text heuristics | 0.65 |
| country | Domain TLD mapping | 0.80 |

### Enrichment Rules
- Cannot create an entity
- Cannot rescue a rejected entity
- Cannot modify required fields (company_name, domain)
- Failed enrichment leaves entity unchanged
- All enriched fields require new Evidence

### What Is NOT Done
- No external API calls
- No web scraping
- No AI inference
- No paid services

### Why This Matters
Enrichment is a convenience, not a requirement. Entities are valid without it. This prevents enrichment from becoming a crutch or a source of errors.

---

## Phase 4: Deterministic Lead Ranking

### Purpose
Score and prioritize leads with full transparency.

### Inputs
- Enriched `Entity` objects
- Original `Signal` objects

### Outputs
- `RankedLead` objects with score breakdown
- Plain-English explanations

### Scoring Components

| Component | Points | Description |
|-----------|--------|-------------|
| Intent Strength | 0-40 | Hiring=40, Funding=30, Executive=20 |
| Signal Freshness | 0-25 | 0-3 days=25, 4-7=20, 8-14=15, 15-21=10, 22-30=5 |
| Evidence Confidence | 0-20 | Min confidence across all evidence |
| Entity Completeness | 0-10 | Base 5 + optional fields |
| Noise Penalty | -10 to 0 | Uncertainty markers in text |

### Tier Thresholds

| Tier | Score Range | Priority |
|------|-------------|----------|
| A | ≥60 | High |
| B | 40-59 | Medium |
| C | 20-39 | Low |
| D | <20 | Very Low |

### What Is NOT Done
- No ML or learned weights
- No personalization
- No hidden factors
- No ranking of rejected entities

### Why This Matters
Ranking answers the question: "Which lead should I contact first?" The answer must be defensible. Every component is visible and verifiable.

---

## Phase 5A: Public Alpha CLI

### Purpose
Expose the pipeline to real users without compromising integrity.

### Commands

| Command | Description |
|---------|-------------|
| `run` | Execute full pipeline |
| `leads` | Display ranked leads |
| `explain <id>` | Show score breakdown |
| `evidence <id>` | Show evidence lineage |

### Properties
- Read-only (cannot modify scoring)
- Deterministic (same output every time)
- Transparent (explanations match logic)
- Auditable (rejections visible)

### What Is NOT Done
- No configuration flags
- No tuning options
- No persistence
- No background jobs
- No API endpoints

### Why This Matters
The interface is a trust surface. If users can tweak scoring, they stop trusting the defaults. GlassBox removes that option intentionally.

---

## Pipeline Summary

| Phase | Input | Output | Can Reject? |
|-------|-------|--------|-------------|
| 0 | — | Evidence contracts | — |
| 1 | RSS XML | Signals | Yes (R1, R2) |
| 2 | Signals | Entities | Yes (R3, R4) |
| 3 | Entities | Enriched Entities | No |
| 4 | Enriched Entities | Ranked Leads | No |
| 5A | Ranked Leads | CLI Output | No |

---

*Each phase trusts only the phase before it. This is how correctness scales.*
