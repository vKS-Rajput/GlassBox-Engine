# GlassBox Discovery Engine — Development History

This document records the complete chronological history of the GlassBox Discovery Engine development, detailing every user request and engineering action taken.

---

## Project Inception

**User Goal:** Build a deterministic, "Glass Box" discovery engine for freelancers to find clients.
**Core Philosophy:**
- No black boxes (everything must be explainable).
- No scoring without Evidence.
- Precision over recall (reject ambiguity).
- Read-only, deterministic logic.

---

## Phase 0: Foundation (Evidence Ledger)

**User Request:** Establish the core data structures and invariants.

**Actions Taken:**
1.  **Created `glassbox/evidence.py`**:
    -   Implemented `Evidence` dataclass.
    -   Defined `EvidenceType` (OBS, INF, API).
    -   Implemented confidence logic constraints (must be 0.0-1.0).
    -   Added factory functions (`create_observation`, `create_inference`).
2.  **Created `glassbox/domain.py`**:
    -   Defined `Signal`, `Entity`, `Lead`, `Rejection` objects.
    -   Enforced that all Entity attributes must be Evidence objects.
3.  **Created `glassbox/validation.py`**:
    -   Implemented "Hard Rejection Rules" (R1-R8).
    -   Created `gate_signal` function to filter noise immediately.
4.  **Tests**: Created `tests/test_phase0.py` (24 tests passed).

---

## Phase 1: Signal Acquisition

**User Request:** Implement RSS feed ingestion.

**Actions Taken:**
1.  **Created `glassbox/ingestion/rss.py`**:
    -   Implemented XML parsing for RSS feeds.
    -   Implemented text normalization.
    -   Created `ingest_rss_feed` to convert RSS items into `Signal` objects.
    -   Integrated dedup hashing.
2.  **Tests**: Created `tests/test_phase1_ingestion.py` (24 tests passed).

---

## Phase 2: Entity Resolution

**User Request:** specific company identity from signals.

**Actions Taken:**
1.  **Created `glassbox/resolution/entity_resolver.py`**:
    -   Implemented logic to extract Company Name and Domain from signals.
    -   Added strictly validated TLD whitelist (rejecting generic emails like gmail.com).
    -   Implemented "Ambiguity Rejection" (if multiple companies found, reject).
2.  **Tests**: Created `tests/test_phase2_resolution.py` (30 tests passed).

---

## Phase 3: Waterfall Enrichment

**User Request:** Add context (Industry, Size, Country) without breaking trust.

**Actions Taken:**
1.  **Created `glassbox/enrichment/waterfall.py`**:
    -   Implemented strictly deterministic heuristics.
    -   **Industry**: Keyword mapping from signal text.
    -   **Size**: Regex matching for company size.
    -   **Country**: TLD mapping.
    -   Enforced rule: Enrichment failures do *not* reject the entity.
2.  **Tests**: Created `tests/test_phase3_enrichment.py` (26 tests passed).

---

## Phase 4: Deterministic Lead Ranking

**User Request:** Rank leads transparently and explain the score.

**Actions Taken:**
1.  **Created `glassbox/ranking/components.py`**:
    -   Implemented 5 Scoring Components:
        -   `Intent Strength` (Hiring > Funding).
        -   `Signal Freshness` (Decay over days).
        -   `Evidence Confidence` (Aggregated confidence).
        -   `Entity Completeness` (Bonus for optional fields).
        -   `Noise Penalty` (Validation checks).
2.  **Created `glassbox/ranking/scorer.py`**:
    -   Implemented `ScoreBreakdown` to sum components.
    -   Implemented `LeadTier` (A/B/C/D).
    -   Implemented `RankedLead.get_explanation()` (Plain english summary).
3.  **Tests**: Created `tests/test_phase4_ranking.py` (29 tests passed).
    -   *Correction*: Fixed a test case regarding confidence thresholds (0.35 confidence = Low Tier/5pts).

---

## Phase 5A: Public Alpha Interface (CLI)

**User Request:** Allow a freelancer to actually run this locally.

**Actions Taken:**
1.  **Created `glassbox/cli/pipeline.py`**:
    -   Orchestrated the full flow: Ingest → Resolve → Enrich → Rank.
    -   Added sample RSS data for demonstration.
2.  **Created `glassbox/cli/main.py`**:
    -   Implemented CLI commands: `glassbox run`, `leads`, `explain`, `evidence`.
    -   Ensured output is read-only and deterministic.
3.  **Tests**: Created `tests/test_phase5a_cli.py` (19 tests passed).
    -   *Correction*: Fixed `BatchIngestionResult` attribute naming (`rejections` → `rejected`) in the pipeline.
4.  **End-to-End Verification**: Confirmed CLI output matches internal logic.

---

## Documentation & Cleanup

**User Request:** Document everything for production and clean up.

**Actions Taken:**
1.  **Created Documentation Set**:
    -   `README.md`: User guide and philosophy.
    -   `DESIGN.md`: Defense of the architecture.
    -   `PIPELINE.md`: Detailed phase walkthrough.
    -   `TRUST_MODEL.md`: Why the system is verifiable.
    -   `CONTRIBUTING.md`: Rules for contributors.
2.  **Cleanup**:
    -   Updated `.gitignore`.
    -   Removed `glassbox_engine.egg-info`, `.pytest_cache`, and `__pycache__` folders.
    -   Created `setup.py`, `pyproject.toml`, and `LICENSE`.
3.  **Final Verification**:
    -   Ran full test suite: **152 tests passed**.
    -   Verified `pip install -e .` works.
    -   Verified `glassbox run` execution.

---

## Final Status

The system is feature-complete for Public Alpha.
- **Codebase**: Fully implemented (Phases 0-5A).
- **Quality**: 100% Test Pass Rate (152/152).
- **Documentation**: Production-ready.
- **Artifacts**: Clean and ready for GitHub push.
