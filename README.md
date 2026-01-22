# GlassBox Discovery Engine

An **Explainable Client Discovery Search Engine** that discovers freelance clients from public web signals, explains *why* each was identified, and maps problems to services.

## Core Philosophy

> **"No Score Without Citation"**

Every recommendation traces back to a specific URL, sentence, and timestamp. If the engine cannot explain why it surfaced a lead, it does not surface that lead.

## Architecture

Built on the **Evidence Ledger** — a data contract ensuring no field exists without provenance:

| Evidence Type | Code | Description |
|---------------|------|-------------|
| Observation | `OBS` | Direct scrape from verifiable URL |
| Inference | `INF` | Derived from other evidence via documented rule |
| Third-Party | `API` | From external API with known lineage |

## Project Structure

```
glassbox/
├── evidence.py     # Evidence Ledger (system invariant)
├── domain.py       # Signal, Entity, Lead, Rejection
└── validation.py   # Binary accept/reject gating
tests/
└── test_phase0.py  # 24 tests verifying invariants
```

## Quick Start

```bash
# Install dependencies
pip install pytest

# Run tests
python -m pytest tests/ -v
```

## Status

- [x] Phase 0: Foundation (Evidence Ledger, Domain Objects, Hard Rejection)
- [ ] Phase 1: Signal Acquisition
- [ ] Phase 2: Relevance Gating
- [ ] Phase 3: Waterfall Enrichment
- [ ] Phase 4: Scoring & Storage
- [ ] Phase 5: Search & Presentation

## Constraints

- Zero-budget, open-source, local-first
- AI for classification/extraction only, never final decisions
- No scraping behind login walls
- Precision over recall

## License

MIT
