# Glass Box Discovery Engine — Implementation Specification

> **Document Type**: Internal Design Specification  
> **Status**: Awaiting Approval  
> **Constraint**: Zero-budget, self-hosted, explainable, logic-first

---

## 1. System Mental Model

### How the Engine Thinks

The Glass Box Discovery Engine is not a crawler. It does not blindly scrape and index. It is a **reasoning pipeline** that transforms raw web signals into defensible conclusions about client fit.

The engine operates on a single core premise: **No score without citation.** Every recommendation traces back to a specific URL, a specific sentence, a specific timestamp. If the engine cannot explain why it surfaced a lead, it does not surface that lead.

```
Signal → Evidence → Conclusion → Explanation
```

**Stage 1 — Signal Acquisition**: The engine monitors structured feeds (RSS, job boards, funding announcements). These are not arbitrary websites. They are curated sources of ephemeral business events—hiring, fundraising, executive changes—that imply immediate need.

**Stage 2 — Entity Extraction**: A local LLM parses the signal. It does not hallucinate. It extracts structured entities (company name, domain, role) and classifies relevance against predefined criteria. The output is JSON or discard.

**Stage 3 — Enrichment Cascade**: If the entity passes relevance gating, the engine attempts to resolve contact information via a strict waterfall—scrape first, inference second, paid API only as fallback. Every data point is tagged with its source.

**Stage 4 — Deterministic Ranking**: Leads are not sorted by opaque scores. They are grouped by discrete signals (Hiring+Stack+Verified vs. Hiring+Stack vs. Hiring). Ties break by recency, then by confidence.

**Stage 5 — Evidence Ledger Construction**: The lead record is not raw data. It is an evidence object—every field wrapped in provenance metadata. When presented to the user, the system generates a plain-English explanation from this ledger.

### Why This Is a Search Engine

This is not scraping. Scraping is indiscriminate: visit URL, extract DOM, store.

This is search + reasoning:

- **Retrieval**: Curated sources are queried for signals matching predefined intent patterns.
- **Ranking**: Retrieved entities are ranked by deterministic business logic, not by keyword frequency.
- **Explanation**: Every result is accompanied by a machine-generated citation chain.

The engine answers a query: *"Who needs my services right now, and why do I believe that?"* It does not merely return data.

---

## 2. Minimal Core Components

### 2.1 Signal Ingestion

| Attribute | Value |
|-----------|-------|
| **Purpose** | Ingest ephemeral business events from curated, public sources |
| **Inputs** | RSS feeds (Google Alerts, Grants.gov, Greenhouse, Lever); scheduled Firecrawl runs on target company career pages |
| **Outputs** | Raw text payloads with source URL and timestamp |
| **Why it must exist** | Without structured signal acquisition, the engine has nothing to reason over. Ad-hoc scraping is brittle and illegal at scale. |
| **Excluded complexity** | Full-web crawling. Real-time streaming. Login-walled platforms. |

---

### 2.2 Entity Resolution & Semantic Filtering

| Attribute | Value |
|-----------|-------|
| **Purpose** | Determine if a signal is relevant and extract structured entities |
| **Inputs** | Raw text from ingestion; relevance criteria (industry, service type, role keywords) |
| **Outputs** | Structured JSON: `{company, domain, role, relevance_flag, confidence}` or `null` |
| **Why it must exist** | Most signals are noise. Without aggressive filtering, the pipeline floods downstream stages with irrelevant data. LLM inference is expensive—must gate early. |
| **Excluded complexity** | Multi-hop entity resolution. Coreference across documents. Entity linking to external KGs. |

---

### 2.3 Waterfall Enrichment

| Attribute | Value |
|-----------|-------|
| **Purpose** | Resolve contact information for the decision-maker at the identified entity |
| **Inputs** | Company domain; decision-maker role (e.g., "CTO", "Head of Marketing") |
| **Outputs** | Contact record: `{name, email, phone, source_type, source_url, confidence}` |
| **Why it must exist** | Discovery without outreach is useless. Contact resolution is the bridge. Waterfall maximizes fill rate while minimizing paid API spend. |
| **Excluded complexity** | LinkedIn scraping. Social graph traversal. Phone number verification. |

**Waterfall Sequence (strict order):**
1. Scrape `/about` or `/team` page for names and emails (Firecrawl)
2. If name found, generate email permutations (inference)
3. Validate via SMTP handshake (free)
4. If all fail AND lead score ≥ threshold, call paid API (Hunter/Apollo) as last resort

---

### 2.4 Deterministic Scoring

| Attribute | Value |
|-----------|-------|
| **Purpose** | Rank leads by explicit business rules, not black-box models |
| **Inputs** | Evidence ledger for each lead |
| **Outputs** | Tier assignment: `{tier: 1/2/3, sort_keys: [timestamp, confidence]}` |
| **Why it must exist** | Users cannot debug probabilistic scores. Deterministic tiers are explainable and tunable. |
| **Excluded complexity** | ML-based scoring models. Composite numeric scores. Personalization. |

**Tier Logic:**
- **Tier 1**: Hiring Signal + Tech Stack Match + Verified Email
- **Tier 2**: Hiring Signal + Tech Stack Match (no email yet)
- **Tier 3**: Hiring Signal only

Ties within tier: sort by signal recency (newest first), then by email confidence (highest first).

---

### 2.5 Evidence Ledger (SYSTEM INVARIANT)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Enforce provenance as a first-class data contract for every field in the system |
| **Inputs** | Data value + extraction context |
| **Outputs** | Wrapped evidence object: `{value, meta: {confidence, source_type, source_url, timestamp, method}}` |
| **Why it must exist** | This is the core of the "Glass Box" philosophy. Without provenance, the system is a black box. |
| **Excluded complexity** | Version history. Audit trails. Multi-source conflict resolution. |

> **SYSTEM INVARIANT**: No field, attribute, inference, or conclusion may exist in the database without an attached Evidence Object. This is not a guideline. It is an architectural law. Any write operation that attempts to store a raw value without provenance metadata must fail.

**Violation handling**: If any pipeline stage cannot produce a valid Evidence Object for a required field, the lead is rejected. Nullable fields (e.g., `contact_email`) may be absent, but if present, must carry full provenance.

---

### 2.6 Search Layer

| Attribute | Value |
|-----------|-------|
| **Purpose** | Allow users to query the lead corpus by intent, problem, service, freshness, and confidence |
| **Inputs** | User query (structured or natural language) |
| **Outputs** | Ranked list of leads with embedded explanations |
| **Why it must exist** | The engine is not a notification feed. Users must be able to retrieve and filter leads on demand. |
| **Excluded complexity** | Vector similarity search. Semantic embedding indices. Personalized ranking. |

---

## 3. Canonical Logic Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GLASS BOX LOGIC PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │ SIGNAL ACQUISITION│  RSS/Cron triggers → Raw text + URL + timestamp      │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐  Deduplication check (Redis/Postgres)                │
│  │ DEDUPLICATION    │  → If seen before: DISCARD                            │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐  Local LLM (Ollama) + strict JSON schema             │
│  │ ENTITY RESOLUTION│  Prompt: "Is this relevant? Extract entities."       │
│  │ & FILTERING      │  → If confidence < 0.8: DISCARD + log reason          │
│  └────────┬─────────┘  → If valid: {company, domain, role, confidence}     │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐  Tier 1: Scrape → Tier 2: Inference → Tier 3: SMTP   │
│  │ WATERFALL        │  → Tier 4: Paid API (only if score threshold met)    │
│  │ ENRICHMENT       │  → Output: {contact_email, name, source_meta}         │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐  Hierarchical tier assignment, NOT a sum             │
│  │ DETERMINISTIC    │  Rule 1: Hiring present? → Rule 2: Stack match?       │
│  │ SCORING          │  → Rule 3: Contact verified? → Tier 1/2/3            │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐  Wrap every field in provenance metadata             │
│  │ EVIDENCE LEDGER  │  → {value, confidence, source_type, source_url, ts}  │
│  │ CONSTRUCTION     │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐  Store to Postgres/SQLite                            │
│  │ SEARCHABLE       │  → Index by: tier, industry, signal_type, recency    │
│  │ RECORD           │  → Expose via query interface                         │
│  └──────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Decision Thresholds

| Checkpoint | Threshold | Action if Failed |
|------------|-----------|------------------|
| Deduplication | URL+timestamp hash exists | Discard silently |
| Relevance confidence | < 0.8 | **HARD REJECT** + log reason |
| Entity extraction | Missing company OR domain | **HARD REJECT** |
| Time-sensitive signal | Signal age > 30 days | **HARD REJECT** |
| Waterfall enrichment | All tiers return null | Store lead WITHOUT contact (can retry later) |
| Tier assignment | No hiring signal | **HARD REJECT** |

---

### Relevance Gating (PRECISION GATE)

Relevance gating is the **primary quality control mechanism**. It operates on a binary accept/reject model. There is no "maybe" state.

**Minimum acceptance requirements (ALL must be true):**
1. At least one **time-sensitive intent signal** (hiring, funding, executive change) with age ≤ 30 days
2. At least one **resolvable entity**: company name AND valid domain (resolves to live website)
3. LLM classification confidence ≥ 0.8
4. Valid JSON output from LLM (schema-conformant)

**Hard reject rules (ANY triggers immediate discard):**

| Rule | Trigger | Rationale |
|------|---------|----------|
| R1: No intent signal | Signal text lacks hiring/funding/change keywords | No time-sensitive need |
| R2: Stale signal | Signal timestamp > 30 days old | Opportunity likely closed |
| R3: Missing entity | Company name OR domain not extractable | Cannot enrich or contact |
| R4: Invalid domain | Domain parked, for-sale, or non-resolving | Not a real company |
| R5: Out-of-scope industry | Industry not in target list | Precision over recall |
| R6: Size mismatch | Company size < 2 or > 1000 employees (if detectable) | Budget fit disqualification |
| R7: LLM failure | Invalid JSON or confidence < 0.8 | Unreliable classification |

**Rejection logging (for auditability, not reuse):**

Every rejected signal is logged with:
- `signal_id`: Hash of source URL + timestamp
- `rejection_rule`: Which rule triggered (R1–R7)
- `rejection_reason`: Human-readable explanation
- `raw_signal_snippet`: First 500 chars (for debugging)
- `timestamp`: When rejected

Rejected signals are **not** stored in the leads table. They exist only in a rejection log for pipeline debugging. They are **never** retried or reconsidered.

---

### Confidence Handling

Confidence is **not a composite score**. It is attached per-field and subject to decay:

| Field | Source | Initial Confidence | Decay Rule |
|-------|--------|-------------------|------------|
| `relevance_confidence` | LLM classification | 0.0–1.0 | No decay (static at extraction) |
| `email_confidence` | Waterfall tier | Scraped=0.95, Inferred=0.7, API=0.9 | Decays 0.1 per 30 days |
| `signal_freshness` | Timestamp delta | 1.0 if < 7 days | Drops to 0.5 at 14 days, 0.0 at 30 days |

**Confidence invalidation:**
- If `signal_freshness` reaches 0.0, the lead is moved to an **archive** queue and excluded from active search results
- If `email_confidence` falls below 0.5, the contact is marked `stale` and excluded from outreach suggestions

---

### Where Human Trust Is Preserved

The system never acts autonomously beyond data collection. It:
- Does NOT send emails without human review
- Does NOT infer problems that aren't explicit in signals
- Does NOT generate outreach copy without human sign-off
- Does NOT escalate to paid APIs without explicit configuration

---

## 4. Explainability & Evidence Model (DATA CONTRACT)

### The Evidence Ledger as First-Class Contract

The Evidence Ledger is not a logging mechanism. It is the **canonical data structure** of the system. Every piece of information stored must conform to this contract.

> **INVARIANT**: No field, attribute, inference, or conclusion may exist without an attached Evidence Object. This is enforced at write time. Violations cause hard failures.

---

### Evidence Type Taxonomy

Every Evidence Object must declare its type. There are exactly three valid types:

| Type | Code | Definition | Trust Level | Example |
|------|------|------------|-------------|---------|
| **Direct Observation** | `OBS` | Text scraped from a specific, verifiable URL | Highest | "Hiring Head of Engineering" from `boards.greenhouse.io/acme/jobs/123` |
| **Inference** | `INF` | Value derived from observed data via documented, reproducible rule | Medium | `jane@acme.com` inferred from name "Jane Doe" + domain "acme.com" via pattern `{first}@{domain}` |
| **Third-Party Enrichment** | `API` | Value returned from external service with known data lineage | Variable | Email verified via Hunter.io API response |

**Type-specific requirements:**

| Type | Required Metadata |
|------|------------------|
| `OBS` | `source_url` (verifiable), `timestamp`, `extraction_method` |
| `INF` | `source_evidence_ids` (references to OBS objects used), `inference_rule` (named rule) |
| `API` | `provider_name`, `api_response_id`, `timestamp`, `provider_confidence` |

---

### Evidence Object Schema (Canonical)

```json
{
  "evidence_id": "evt_abc123",
  "field_name": "contact_email",
  "value": "jane@acme.com",
  "type": "INF",
  "meta": {
    "confidence": 0.70,
    "source_evidence_ids": ["evt_xyz789"],
    "inference_rule": "email_permutation_first_at_domain",
    "timestamp": "2026-01-22T10:30:00Z",
    "validated": true,
    "validation_method": "smtp_handshake"
  }
}
```

**Schema enforcement**: Any write that omits `evidence_id`, `type`, `meta.timestamp`, or `meta.confidence` is rejected.

---

### Confidence: Attachment, Decay, and Invalidation

**Attachment**: Confidence is assigned at evidence creation time based on source type and extraction method.

| Source Type | Base Confidence |
|-------------|----------------|
| Direct scrape (OBS) | 0.95 |
| Inference from OBS (INF) | 0.70 |
| Third-party API (API) | Use provider confidence or 0.85 default |

**Decay**: Confidence decays over time for time-sensitive fields.

| Field | Decay Schedule |
|-------|---------------|
| `intent_signal` | -0.25 per 7 days (reaches 0 at 28 days) |
| `contact_email` | -0.10 per 30 days |
| `company_name`, `domain` | No decay |

**Invalidation**: When confidence reaches 0, the evidence is marked `invalidated: true`. Invalidated evidence:
- Remains in the ledger (for audit)
- Is excluded from search results
- Is excluded from tier calculations
- May trigger a re-enrichment attempt if configured

---

### What Happens When Evidence Is Missing or Insufficient

| Scenario | System Response |
|----------|----------------|
| Required field has no Evidence Object | **HARD REJECT**: Lead not stored |
| Evidence Object missing required metadata | **HARD REJECT**: Write fails |
| Confidence below minimum threshold | **HARD REJECT** for required fields; mark `low_confidence` for optional fields |
| Evidence type is unrecognized | **HARD REJECT**: Invalid data |

Required fields: `company_name`, `domain`, `intent_signal`
Optional fields: `contact_email`, `contact_name`

---

### Tracing Conclusions to Sources

Every conclusion the system makes can be reverse-traced via `evidence_id` references:

1. **Why was this lead surfaced?** → `intent_signal.evidence_id` → `source_url`
2. **Why is this a "Tier 1" lead?** → Tier logic references `intent_signal.evidence_id` + `contact_email.evidence_id`
3. **Where did this email come from?** → `contact_email.source_evidence_ids` → original OBS evidence
4. **How fresh is this signal?** → `intent_signal.meta.timestamp` + decay calculation

---

### Explanation Generation

Explanations are **views**, not stored data. They are generated at render time from the Evidence Ledger.

**Template:**
```
Lead {company_name.value} identified via {intent_signal.type}.
Signal: "{intent_signal.value}" (Source: {intent_signal.meta.source_url}).
Contact {contact_name.value} found via {contact_email.type}.
Email: {contact_email.value} (Confidence: {contact_email.meta.confidence}).
```

**Example Output:**
> Lead **Acme Corp** identified via direct observation (OBS).  
> Signal: "Hiring Head of Engineering" (Source: [boards.greenhouse.io/acme/jobs/123](https://boards.greenhouse.io/acme/jobs/123)).  
> Contact **Jane Doe** found via inference (INF) from team page.  
> Email: jane@acme.com (Confidence: 0.70).

> **CRITICAL**: Explanations are ephemeral views. They are never indexed, never stored as separate records, and never used as search input. Only the underlying Evidence Objects are authoritative.

---

## 5. Search Behavior (CONSTRAINED)

### Indexability Rules

Not all data in the system is searchable. The search layer operates only on ledger-backed fields with explicit indexing permission.

**What MAY be indexed:**

| Field | Type | Searchable As |
|-------|------|---------------|
| `company_name.value` | String | Exact match, prefix |
| `domain.value` | String | Exact match |
| `intent_signal.value` | String | Keyword match (extracted keywords only) |
| `intent_signal.meta.timestamp` | DateTime | Range filter (freshness) |
| `contact_email.meta.confidence` | Float | Range filter |
| `tier` | Integer | Exact match, range |
| `intent_signal.type` | Enum | Exact match (hiring, funding, executive_change) |

**What MUST NEVER be indexed:**

| Data Type | Reason |
|-----------|--------|
| AI-generated explanations | Views, not truth. Would create circular reasoning. |
| Raw signal text | Unbounded, unstructured. Would devolve to keyword search. |
| Rejection log contents | Not leads. Debugging data only. |
| Inference rules | Internal logic, not user-facing. |
| Evidence metadata (except confidence, timestamp) | Over-indexing creates noise. |

> **INVARIANT**: If a field is not in the "MAY be indexed" list, it cannot appear in search queries. The search layer rejects queries referencing non-indexed fields.

---

### Structured Reasoning, Not Keyword Matching

This is **not** a keyword search engine. It is a structured query system.

**Keyword search (PROHIBITED)**: "Find leads containing 'React Native'"

**Glass Box search (REQUIRED)**: "Find leads WHERE tier = 1 AND intent_signal.type = 'hiring' AND freshness ≤ 7 days"

The difference:
- Keyword search matches text anywhere, ignoring structure
- Glass Box search matches **evidence-backed attributes** with known provenance

Free-text search is permitted only as a **secondary** filter after structured filters have been applied. It may search within `intent_signal.value` and `company_name.value` only—never across raw text.

---

### Searchable Dimensions (Exhaustive List)

| Dimension | Evidence Field | Query Type | Example |
|-----------|---------------|------------|----------|
| **Intent Type** | `intent_signal.type` | Enum match | `intent_type = 'hiring'` |
| **Freshness** | `intent_signal.meta.timestamp` | Range | `signal_age ≤ 7 days` |
| **Tier** | `tier` | Exact/Range | `tier = 1` |
| **Email Confidence** | `contact_email.meta.confidence` | Range | `email_confidence ≥ 0.8` |
| **Company** | `company_name.value` | Prefix/Exact | `company starts_with 'Acme'` |
| **Has Contact** | `contact_email` | Exists check | `has_contact = true` |

**NOT searchable** (explicitly excluded):
- Inferred problem statements
- Service mappings (future feature, not MVP)
- LLM-generated content of any kind

---

### Deterministic Tie-Breaking

When multiple leads match a query with the same tier:

1. **First sort**: Signal timestamp (newest first)
2. **Second sort**: Email confidence (highest first)
3. **Third sort**: Company name (alphabetical, for stability)

This is **not** a weighted sum. It is a strict priority queue. The user can reason about ordering without understanding a model.

> **PROHIBITED**: No "relevance score" may be computed or displayed. No ML-based ranking. No personalization. The sort order is deterministic and reproducible.

---

### Preventing Drift to RAG or Keyword Search

The research papers warn against black-box AI search. The following constraints prevent architectural drift:

1. **No embedding-based retrieval**: Vector similarity is not used for lead ranking
2. **No LLM in the query path**: LLM is used for extraction, never for search
3. **No semantic expansion**: Query terms are not expanded via synonyms or embeddings
4. **No "smart" relevance**: System does not guess what user wants
5. **Explanations are views**: Never stored, never indexed, never used as search input

---

## 6. MVP Scope Lock

### Included in MVP

| Component | Scope |
|-----------|-------|
| Signal ingestion | 5–10 RSS feeds (job boards, funding news) |
| Entity filtering | Single-industry focus (e.g., "SaaS companies") |
| Waterfall enrichment | Tiers 1–3 only (scrape, inference, SMTP validation) |
| Scoring | 3-tier deterministic model |
| Evidence ledger | Full provenance on all fields |
| Search | CLI or Google Sheets query interface |
| Output | Slack notification or Sheet row per lead |

### Explicitly Excluded (Even If Tempting)

| Feature | Why Excluded |
|---------|--------------|
| Paid API enrichment | Adds cost, removes "zero-budget" constraint |
| Vector semantic search | Over-engineering for < 10k leads |
| Multi-industry classification | Adds complexity without validation |
| Automated outreach | Violates "human trust" principle |
| Real-time streaming | Unnecessary for freelancer scale |
| UI dashboard | Premature; validate logic first |
| Multi-hop entity linking | Requires external KG, adds latency |
| Phone number resolution | Low ROI for email-first outreach |

### Features That Would Damage Explainability

| Feature | Damage |
|---------|--------|
| ML-based lead scoring | Black box, not debuggable |
| Composite numeric scores | "What does 73 mean?" |
| Auto-generated outreach | Trust requires human review |
| Inferred problem statements | LLM hallucination risk |
| Automated send | Legal and ethical exposure |

---

## 7. Trade-offs & Limits

### What the Engine Cannot Detect

| Blind Spot | Reason |
|------------|--------|
| Intent behind login walls | LinkedIn, Crunchbase Pro, etc. are inaccessible |
| Private funding rounds | Not announced publicly |
| Internal hiring (no public job post) | No signal exists |
| Stealth-mode companies | No public presence |
| Budget or timing readiness | Cannot be inferred from public signals |

### Where Inference May Fail

| Failure Mode | Mitigation |
|--------------|------------|
| LLM misclassifies relevance | Confidence threshold (0.8) + human review queue |
| Email permutation wrong | SMTP validation before storage |
| Stale job post (already filled) | Signal freshness decay (< 7 days = fresh) |
| Company domain parked or for sale | Domain validation in enrichment |
| Person left company | No mitigation—static snapshot |

### Explainability vs. Automation Trade-offs

| Automation Level | Explainability Cost |
|------------------|---------------------|
| Fully automated scoring | Impossible to debug |
| Fully automated outreach | Legal risk, ethical breach |
| Fully automated enrichment | Cost overruns, API abuse |
| Human-in-loop at tier assignment | Slows throughput |
| Human-in-loop at outreach | **Required** — no trade-off |

The architecture **intentionally avoids full autonomy**. A solo builder cannot afford to fix automation errors at scale. Human review is cheaper than reputation damage.

### Why This Architecture Rejects Full Autonomy

1. **Legal exposure**: Automated outreach to EU contacts without GDPR compliance is liability.
2. **Reputation risk**: One bad cold email can burn a domain.
3. **Cost risk**: Runaway API calls can exceed zero-budget constraint.
4. **Trust risk**: Clients who discover they were "AI-scraped" lose trust.

The engine is a **force multiplier**, not a replacement for judgment.

---

## 8. Execution Order (CORRECTED)

### Phase 0: Environment Setup
- [ ] Install Docker Desktop
- [ ] Deploy n8n container (local)
- [ ] Deploy Ollama container with Mistral 7B or Llama 3 8B
- [ ] Configure `host.docker.internal` networking between containers
- [ ] Deploy Firecrawl (self-hosted or free tier)
- [ ] Provision PostgreSQL or SQLite

### Phase 1: Evidence Ledger Schema (MUST BE FIRST)
> **Rationale**: The Evidence Ledger is the system invariant. All downstream components write to it. It must be designed and locked before any data flows.

- [ ] Define Evidence Object schema (JSON structure with required fields)
- [ ] Define evidence type taxonomy (OBS, INF, API) with required metadata per type
- [ ] Implement database schema with Evidence columns (not raw strings)
- [ ] Implement write-time validation: reject any write missing required Evidence metadata
- [ ] **STOP. Validate**: Attempt to write a raw string. Does it fail? Attempt to write Evidence without `evidence_id`. Does it fail?

### Phase 2: Signal Acquisition (validate input structure)
- [ ] Define 5 target RSS feeds (Greenhouse, Lever, TechCrunch, Grants.gov, Google Alerts)
- [ ] Build n8n workflow: RSS trigger → raw text extraction → deduplication check
- [ ] Store raw signals as Evidence Objects (type=OBS) with full metadata
- [ ] **STOP. Validate**: Are signals stored with valid Evidence structure? Can you query by source_url?

### Phase 3: Relevance Gating (validate precision before volume)
- [ ] Write relevance prompt with strict JSON schema enforcement
- [ ] Implement hard reject rules (R1–R7) as explicit checks
- [ ] Build rejection log table (separate from leads)
- [ ] Build n8n node: Ollama call → JSON parse → confidence check → reject or pass
- [ ] **STOP. Validate**: Feed 20 signals. How many pass? How many reject per rule? Is precision > 80%?

### Phase 4: Waterfall Enrichment (validate data quality before scaling)
- [ ] Build Tier 1: Firecrawl scrape → produce Evidence Object (type=OBS)
- [ ] Build Tier 2: Email permutation → produce Evidence Object (type=INF) with `source_evidence_ids`
- [ ] Build Tier 3: SMTP validation → update Evidence Object with `validated: true`
- [ ] Wire waterfall: if null → next tier; output must always be Evidence Object or null
- [ ] **STOP. Validate**: Every contact has Evidence Object? Can you trace email back to original OBS?

### Phase 5: Scoring & Storage (validate logic before exposure)
- [ ] Implement tier assignment logic referencing Evidence Objects
- [ ] Store complete leads with all Evidence columns populated
- [ ] Implement confidence decay scheduler (optional for MVP, but design now)
- [ ] **STOP. Validate**: Query a lead. Can you explain every field from Evidence Ledger alone?

### Phase 6: Search & Presentation (validate usefulness last)
- [ ] Build query interface with ONLY indexed fields (per Section 5 constraints)
- [ ] Implement explanation template (view generation from Evidence)
- [ ] Output to Slack channel or Sheet
- [ ] **STOP. Validate**: Is free-text search disabled or secondary? Does a real lead make sense?

### What Should NOT Be Built Until Users Validate

| Feature | Precondition |
|---------|--------------|
| Paid API fallback (Tier 4) | Fill rate < 30% after 50 leads |
| Multi-industry classification | MVP is validated on one industry |
| Automated outreach drafts | User confirms they want this |
| UI dashboard | CLI/Sheets workflow proves inadequate |
| Vector search | Lead corpus exceeds 10k |
| Real-time monitoring | Batch mode proves too slow |

---

## Verification Plan

### Automated Tests
This is an architecture-only document. No code is produced. Verification will occur during implementation:

1. **Signal ingestion test**: Run RSS trigger, confirm raw signals stored with correct source URLs
2. **LLM output test**: Feed 10 sample signals, confirm valid JSON output with >80% accuracy
3. **Waterfall test**: Provide 5 known company domains, verify email fill rate ≥ 60%
4. **Evidence ledger test**: Query database, confirm every field has attached metadata
5. **Explanation generation test**: Render 3 leads, confirm plain-English output matches template

### Manual Verification
1. **User review**: Present 10 leads to user and ask: "Would you reach out to this lead? Why or why not?"
2. **Provenance audit**: Pick any lead field, user traces it back to source URL manually
3. **Tier logic review**: User confirms tier assignments match their mental model of lead quality

---

## Summary

This specification operationalizes the Glass Box philosophy from the research papers into a buildable system:

- **Signals, not scraping**: Curated feeds, not full-web crawling
- **Evidence, not scores**: Every datum traced to source
- **Tiers, not probabilities**: Deterministic, debuggable ranking
- **Explanation by default**: No lead without citation
- **Human in the loop**: No automation beyond collection

Build in order. Validate at each phase. Do not proceed until the current stage is trustworthy.

# Architectural Blueprint for the Glass Box Discovery Engine: A Comparative Analysis and Design Specification

## 1. Executive Summary
The contemporary landscape of Client Discovery and Lead Intelligence is bifurcated into two
distinct, often incompatible, technological paradigms. On one side lies the domain of
Advanced AI Search and Reasoning, exemplified by platforms like Perplexity and Glean,
which prioritize semantic understanding, retrieval-augmented generation (RAG), and the
synthesis of unstructured data into coherent narratives. On the other side sits the Lead
Intelligence and Enrichment sector, dominated by tools like Apollo.io, Clay, and
PhantomBuster, which operate on the principles of massive structured databases,
deterministic waterfall enrichment, and aggressive signal acquisition.
For freelancers and small agencies, neither paradigm offers a complete solution. AI Search
engines, while excellent at reasoning, often lack the structured precision required for
high-volume prospecting and CRM integration. Conversely, Lead Intelligence platforms
frequently operate as "black boxes," providing probabilistic lead scores without transparent
provenance, often relying on decaying static databases that fail to capture real-time intent.
The result is a discovery process that is either manually exhaustive or computationally
opaque, leading to wasted resources on low-intent prospects.
This report proposes a convergence of these architectures: the Explainable Client
Discovery Search Engine, or the "Glass Box Discovery Engine" (GBDE). This proposed
architecture rejects the "black box" nature of traditional lead scoring in favor of a transparent,
evidence-based pipeline. By synthesizing the reasoning capabilities of Perplexity, the visual
extraction logic of Diffbot, the deterministic ranking of Algolia, and the waterfall orchestration
of Clay, we define a system that not only identifies high-value clients but provides a rigorous
"Evidence Ledger" explaining the why behind every recommendation.
The following analysis exhaustively dissects the architectural patterns of eight market-leading
systems, distills their high-leverage engineering practices, and reassembles them into a
coherent, low-code, zero-budget pipeline deployable by individual builders. This pipeline
leverages self-hosted orchestration (n8n), local Large Language Models (Ollama), and
open-source scraping (Firecrawl) to democratize access to enterprise-grade client
intelligence.
- Comparative Analysis of Advanced Systems
To engineer a best-in-class solution, one must first deconstruct the prevailing architectures.

We analyze these systems not merely as products, but as assemblies of engineering
decisions, examining their reasoning logic, explainability approaches, and inherent
constraints.
2.1 Domain 1: AI Search, Indexing, and Reasoning
This domain is characterized by the challenge of retrieving relevant information from vast,
unstructured corpora and synthesizing it into accurate, trustworthy responses. The primary
architectural tension here is between hallucination (generative creativity) and grounding
(factual accuracy).
2.1.1 Perplexity: The Citation-First RAG Engine
Architecture Pattern: Retrieval-Augmented Generation (RAG) with Strict Attribution
Perplexity AI represents a fundamental shift from keyword-based information retrieval to
answer-based synthesis. Its architecture is built upon the Retrieval-Augmented Generation
(RAG) framework, which blends real-time external data sources with Large Language Models
(LLMs) to generate responses that are both accurate and up-to-date.
## 1
Unlike traditional
search engines that return a list of links, or standard chatbots that rely solely on pre-trained
parametric memory, Perplexity executes a real-time web search for every query, treating the
web as a dynamic extension of its knowledge base.
Reasoning Logic and Query Execution The technical journey of a Perplexity query is
sophisticated. Upon receiving a user input, the system does not immediately query the index.
Instead, it employs a query understanding module that decomposes complex questions into
sub-queries. This allows the system to conduct parallel searches across different vectors of
the topic.
## 2
The architecture combines hybrid retrieval mechanisms, utilizing both sparse
(keyword) and dense (semantic vector) embeddings to ensure high recall.
## 3
A critical differentiator is the "Deep Research" mode. This feature elevates the system from a
passive retrieval engine to an active reasoning agent. In this mode, the system iterates
through a loop of searching, reading, and reasoning. It identifies gaps in the initial retrieved
information and autonomously formulates follow-up queries to fill those gaps, mimicking the
workflow of a human researcher.
## 4
This agentic behavior allows for the synthesis of
"comprehensive reports" rather than simple summaries, involving dozens of searches and the
reading of hundreds of sources per interaction.
Explainability Approach: The Trust Ledger Perplexity places a premium on explainability
through its citation mechanics. Every assertion made in the generated answer is linked via
inline citations to the source document.
## 5
This creates a "truth ledger" where the user can
verify the provenance of any claim. The system’s UI reinforces this by displaying source cards
and superscript numbers, driving a high click-through rate to the original publishers.
## 6
## This
approach mitigates the "black box" problem of LLMs by exposing the retrieval context directly
to the user.
Constraints and Latency The reliance on real-time web search introduces significant latency
compared to pre-indexed database lookups. While Perplexity has optimized its infrastructure
to process 200 million daily queries with state-of-the-art latency
## 3
, the physics of making

multiple external HTTP requests, parsing the DOM, and feeding tokens into an LLM imposes a
floor on response time. Furthermore, the system’s performance degrades as the context
window grows; "frontier LLMs" struggle as context size increases, making efficient
segmentation and re-ranking of sub-document units critical.
## 3
One-Line Design Summary: Iterative, agentic query planning coupled with rigorous,
real-time source attribution to ensure factual grounding in unstructured web data.
## 2.1.2 Diffbot: The Visual Knowledge Graph
Architecture Pattern: Computer Vision-Augmented Scraping & Global Knowledge Graph
Diffbot approaches the problem of web understanding from a radically different angle. While
most crawlers treat the web as a stream of HTML text, Diffbot treats the web as a visual
medium. Its core innovation is the use of Computer Vision (CV) to "render" a page in a
headless browser and analyze its visual layout before extracting data.
## 7
This mimics how a
human perceives a webpage, identifying headers, bylines, sidebars, and main content based
on their pixel coordinates and visual hierarchy rather than just their DOM tag structure.
Reasoning Logic: Visual-to-Semantic Translation The reasoning logic here is grounded in
visual cognition. Diffbot’s system renders a page and uses machine learning models to
segment the visual blocks. It determines that a block of text is a "product description" not
because it is inside a <div> with a specific ID, but because it is visually positioned next to an
image and above a "Buy" button. This allows Diffbot to extract structured entities (people,
organizations, articles, products) from any URL without requiring site-specific scraping rules.
## 7
Once extracted, these entities are not merely stored as documents but are fused into the
"Diffbot Knowledge Graph" (DKG). This is a massive, interconnected web of entities where a
"Person" node is linked to an "Organization" node via an "Employment" edge. This structure
allows for multi-hop reasoning (e.g., "Find all CEOs of companies in San Francisco that use
## Shopify").
## 9
## Explainability Approach: Structural Confidence
Diffbot’s explainability is rooted in the structure of the data itself. Because the data is
normalized into a rigid schema (ontology), the user understands exactly what relationships
exist. However, the extraction process itself—the CV model—is a "black box" to the end user.
One cannot easily ask why Diffbot classified a specific text block as a "summary" versus a
"body," other than trusting the model’s visual heuristics.
Constraints: The Cost of Rendering The primary constraint of the Diffbot architecture is the
computational cost. Rendering the web visually is orders of magnitude more expensive than
parsing raw HTML. This "capital intensive" crawling strategy
## 8
means that Diffbot is best suited
for massive, batch-scale extraction or building a global index, rather than low-latency,
real-time queries on a zero-budget infrastructure.
One-Line Design Summary: Visual structure recognition to transform unstructured, messy
web pages into clean, interconnected Knowledge Graph entities.
2.1.3 Algolia: The Deterministic Tie-Breaker
Architecture Pattern: Deterministic Inverted Index with Tie-Breaking Ranking Algolia

represents the pinnacle of "Transparent Search." In an era of vector embeddings and opaque
semantic relevance, Algolia champions a strictly deterministic approach. Its engineering
philosophy posits that search relevance should be a function of predictable, understandable
rules rather than a probabilistic "relevance score".
## 10
Reasoning Logic: The Tie-Breaking Algorithm
Algolia’s reasoning is governed by a unique "Tie-Breaking" algorithm. Instead of calculating a
single composite score for every document and sorting by that score, Algolia applies a
sequence of sorts.
- All matching records are sorted by the first criterion (e.g., Typo Tolerance).
- Only the records that are tied on this first criterion are passed to the second sorter
(e.g., Geo-Location).
- The tied records from the second step are passed to the third (e.g., Attribute Weight),
and so on.
## 10
This strictly hierarchical sorting mechanism ensures that the most important business rules
are never overridden by an accumulation of minor signals. For example, an exact match on a
"Title" will always outrank a partial match on a "Description," regardless of other factors.
Explainability Approach: Absolute Determinism Algolia offers the highest level of
explainability among the analyzed systems. Because the ranking is rule-based, an engineer
can explain exactly why Record A ranks higher than Record B (e.g., "Record A matched the
'Name' attribute with 0 typos, while Record B had 1 typo").
## 11
This transparency allows for
fine-tuning and debugging of the search experience that is impossible with "black box" vector
search engines.
## Constraints: Structured Data Dependency
The constraint of this approach is its rigidity. Algolia requires clean, structured data (JSON
records) to function. It cannot "reason" over unstructured text or infer meaning that isn't
explicitly present in the index attributes. It is an information retrieval engine, not a knowledge
synthesis engine.
One-Line Design Summary: Transparent, hierarchical, rule-based ranking that prioritizes
explicit business logic and predictability over opaque probabilistic scoring.
## 2.1.4 Glean: The Enterprise Context Engine
Architecture Pattern: Permission-Aware RAG & Federated Indexing Glean addresses the
unique challenge of "Enterprise Search," where data is fragmented across hundreds of SaaS
applications (Slack, Jira, Salesforce, Drive) and protected by complex Access Control Lists
(ACLs). Its core architectural contribution is "permission-aware indexing," ensuring that the
search engine respects the security boundaries of the organization.
## 12
Reasoning Logic: The Work Graph Glean builds a "Work Graph" that maps the relationships
between people, documents, and activities. It utilizes a crawler framework that standardizes
data from diverse APIs into a unified index. When a query is executed, Glean uses RAG to
retrieve documents relevant to the query and permissible to the user. It then synthesizes an
answer using an LLM, grounded in this retrieved context.
## 13
The system understands the
"freshness" and "authority" of documents based on internal signals (e.g., how many people

viewed this doc?).
## 15
## Explainability Approach: Contextual Relevance
Glean preserves explainability by referencing the internal documents used to generate an
answer. Because it operates on an internal corpus, the "provenance" is the document ID
within the company's file system. However, the specific ranking signals (why did this Slack
thread appear above that Jira ticket?) are a mix of semantic similarity and behavioral signals,
which can be less transparent than Algolia’s strict rules.
Constraints: Infrastructure Complexity The primary constraint is the immense complexity
of the connector framework. Maintaining real-time state synchronization and permission
mapping across hundreds of evolving SaaS APIs is a massive engineering burden
## 16
, making
this architecture difficult to replicate for a small-scale builder without significant resources.
One-Line Design Summary: Secure, context-aware retrieval that unifies fragmented data
silos into a single index while strictly enforcing complex access control permissions.
2.2 Domain 2: Lead Intelligence and Client Discovery
This domain shifts the focus from "finding information" to "identifying entities." The goal is to
discover potential clients (leads) and enrich them with actionable data (emails, phone
numbers, intent signals).
## 2.2.1 Clay: The Waterfall Enrichment Orchestrator
Architecture Pattern: Sequential "Waterfall" Logic Clay has revolutionized the data
enrichment market by acting not as a primary data provider, but as a "Meta-Provider" or
aggregator. Its core architectural innovation is the "Waterfall." In a waterfall configuration, the
user defines a sequence of data providers to query for a specific data point (e.g., an email
address). The system queries Provider A; if A returns a null result, it automatically queries
Provider B, and so on, until a result is found or the list is exhausted.
## 17
Reasoning Logic: Conditional Workflows Clay allows users to construct complex,
conditional workflows. For example: "If the Company is in the 'Software' industry AND uses
'HubSpot', THEN trigger a waterfall to find the CTO's email." This logic allows for highly
targeted data spending, ensuring that expensive API calls are only made for high-value
prospects.
## 18
Explainability Approach: The Source Log Clay provides high explainability regarding data
provenance. The interface explicitly shows which provider in the waterfall yielded the result
(e.g., "Email found via Hunter.io"). This allows users to audit the quality of different vendors
and adjust their waterfall priorities accordingly.
## 19
Constraints: Cost Stacking and Dependency The waterfall model can become expensive.
While it maximizes "fill rate" (coverage), chaining multiple premium APIs means the cost per
lead can escalate quickly. Furthermore, the system is entirely dependent on the uptime and
API changes of third-party vendors.
## 20
One-Line Design Summary: Maximizing data coverage and accuracy through sequential,
conditional querying of multiple decentralized data vendors.

## 2.2.2 Apollo.io: The Monolithic Database
Architecture Pattern: Proprietary Database with Intent Signals Apollo operates on the
"Monolithic Database" model. It maintains a massive, proprietary index of hundreds of millions
of contacts and companies. Over this static layer, it layers dynamic "Intent Data"—signals
derived from third-party cookies, IP resolution, and bidstream data that indicate a company is
actively researching specific topics.
## 21
Reasoning Logic: Probabilistic Fit + Intent Scoring Apollo’s reasoning is probabilistic. It
assigns a "Lead Score" based on a composite of demographic fit (Does this company match
my ICP?) and behavioral intent (Are they searching for my competitors?). This scoring model is
customizable, allowing users to weight different factors.
## 21
Explainability Approach: The "Black Box" Score Apollo’s explainability is its weak point.
While users see the final score, the precise calculation is often opaque. A user might see a
high intent score but not know which employee visited their website or exactly what search
term triggered the signal. This "black box" nature forces users to trust the platform's
algorithm without the ability to verify the underlying evidence.
## 21
Constraints: Data Decay Static databases suffer from entropy. People change jobs,
companies go out of business, and emails bounce. Apollo’s primary constraint is data
freshness. Compared to real-time scraping (like Clay or Firecrawl), database-first solutions
often lag behind reality by months, leading to lower deliverability rates.
## 23
One-Line Design Summary: All-in-one engagement platform leveraging a massive,
pre-indexed database to provide high-volume prospecting and intent scoring.
2.2.3 PhantomBuster: The Browser Automation Engine
Architecture Pattern: Cloud-Based Headless Browser Scripting PhantomBuster
automates the "manual" layer of the web. It is a library of scripts ("Phantoms") that spin up
headless browsers to execute specific tasks on social platforms, such as visiting a LinkedIn
profile, clicking "Contact Info," and scraping the resulting DOM elements.
## 24
Reasoning Logic: Procedural Automation The logic is purely procedural. The system does
not "understand" the data; it simply executes a sequence of pre-programmed steps (Go to
URL -> Wait for Selector -> Extract Text). It bridges the gap between the public web and
structured data files (CSV/JSON).
## 25
## Explainability Approach: Direct Observation
Explainability is inherent. The user knows exactly where the data came from because the bot
explicitly visited the URL. There is no hidden inference layer; the output is a direct
transcription of the webpage.
Constraints: The "Grey Zone" Risk PhantomBuster operates in a legal and ethical grey zone.
Platforms like LinkedIn aggressively fight such automation with rate limits, IP bans, and legal
threats (Cease & Desist letters). The architecture is fragile; a single UI change by the target
platform can break the script instantly.
## 26
One-Line Design Summary: Direct extraction from primary sources via headless browser
automation to bypass API limitations and access public data.

- Cross-System Synthesis: Patterns and Anti-Patterns
By synthesizing the analysis of these eight systems, we can distill the engineering choices
that drive success (Best Practices) and those that introduce fragility (Anti-Patterns). This
synthesis forms the theoretical basis for our proposed GBDE pipeline.
## 3.1 Best Practices & High Leverage Features
3.1.1 The Waterfall Enrichment Pattern (Derived from Clay)
● Insight: No single data provider allows for 100% coverage or 100% accuracy. Data
fragmentation is a feature of the B2B web, not a bug. Relying on a single source (e.g.,
just Apollo) creates a single point of failure and lowers the total addressable market.
● Architectural Implication: A robust discovery engine must implement Sequential
Fallback Logic. The pipeline should be designed as: Try Source A (High
Confidence/Low Cost) -> If Null -> Try Source B (Medium Confidence/Medium Cost) -> If
Null -> Try Source C (High Cost/High Coverage). This significantly increases the "fill
rate" of contact data.
## 28
3.1.2 Deterministic Tie-Breaking (Derived from Algolia)
● Insight: Users struggle to interpret probabilistic relevance scores (e.g., "Why is this lead
0.874?"). They prefer predictable, rule-based outcomes.
● Architectural Implication: The scoring engine should use Hierarchical Sorting. A lead
with a confirmed "Hiring Signal" should always outrank a lead with only "Industry Fit,"
regardless of vector similarity. This effectively hard-codes business values into the
ranking logic.
## 10
3.1.3 The Evidence Ledger (Derived from Perplexity)
● Insight: AI hallucinations destroy trust in B2B tools. If an engine says "This company is a
good fit," the user needs to see the evidence to believe it.
● Architectural Implication: The system must generate a Citation Object for every
claim. If a client is classified as "High Value," the system must store and display the
specific URL (e.g., the job post or news article) that triggered that classification. This
moves the system from a "Black Box" to a "Glass Box".
## 2
3.1.4 Visual/Structural Parsing (Derived from Diffbot)
● Insight: The semantic meaning of text is often encoded in its visual presentation (e.g., a
name in a "Leadership" grid implies a role differently than a name in a blog byline).
● Architectural Implication: Leveraging Multimodal LLMs (like GPT-4o or Llama
3-Vision) to "see" the page structure can replace brittle DOM-based scrapers. The
system should classify page types (e.g., "Team Page" vs. "Press Release") before

attempting text extraction.
3.2 Anti-Patterns to Avoid
3.2.1 The "Black Box" Composite Score (Apollo Anti-Pattern)
● Critique: Aggregating ten different variables into a single integer (e.g., "Lead Score:
85") hides the actionable signal. Users cannot determine if the score is high because of
fit or intent.
● Correction: Use discrete flags (e.g., "Signal: Hiring", "Fit: Strong") rather than a single
number.
3.2.2 Static Database Reliance (ZoomInfo/Apollo Anti-Pattern)
● Critique: Pre-indexed databases are snapshots of the past. For ephemeral signals like
"Just Funded" or "New Job Opening," they are often weeks or months out of date.
● Correction: Implement Just-In-Time (JIT) Retrieval. The engine should query live
sources (via search or scraping) for dynamic signals, using databases only for static
contact info.
3.2.3 Fragile Browser Automation (PhantomBuster Anti-Pattern)
● Critique: Scripts that rely on specific CSS selectors (div.class-name) are brittle. They
break whenever the target site updates its UI.
● Correction: Use LLM-driven extraction. Instead of looking for a specific class, feed
the page text to an LLM and ask it to "Extract the email address," which is robust to UI
changes.
- The Strongest Logical Pipeline: "The Glass Box
## Discovery Engine"
Drawing from the synthesis above, we propose the Glass Box Discovery Engine (GBDE).
This architecture is designed for "Explainable Discovery," prioritizing transparency and
evidence over volume. It is an Event-Driven, Agentic RAG Pipeline that orchestrates
open-source tools to deliver enterprise-grade intelligence on a freelancer's budget.
## 4.1 System Overview
● Name: The Glass Box Discovery Engine (GBDE)
● Core Philosophy: "No Score Without Citation."
## ● Architecture: Hybrid Agentic Workflow (n8n + Ollama + Firecrawl).
● Goal: Identify high-probability clients based on real-time triggers, enrich them with
verified data, and generate a human-readable explanation of the fit.
## 4.2 Detailed Decision Logic

The pipeline operates in five sequential stages, each transforming the data state.
Stage 1: Signal Acquisition (The Trigger)
● Objective: Ingest raw events from the web that imply potential need for services.
## ● Inputs:
○ RSS Feeds: Google Alerts ("New Marketing Director"), Grants.gov (New Funding),
## Nasdaq News.
## 29
○ Scheduled Crawl: Firecrawl exploring "Careers" pages of a target list of 100
dream clients.
## 31
● Mechanism: n8n Webhook Trigger or n8n Cron Trigger.
## ● Logic:
## ○ Ingest Text.
○ Deduplicate: Check against Redis/Postgres to ensure this event hasn't been
processed.
○ Pass to Stage 2.
Stage 2: Entity Resolution & Semantic Filtering (The Gatekeeper)
● Objective: Use a Local LLM to determine if the signal is relevant and extract the entity.
● Mechanism: Ollama (running Llama 3 or Mistral) calling the n8n AI Agent Node.
## 32
● Logic (Agentic Evaluation):
○ Input: Raw Text from Stage 1.
○ Prompt: "Analyze this text. Is this a company hiring for? Is the company in
[Industry]? If yes, extract Company Name and Domain. Return strict JSON."
○ JSON Schema Enforce: Use strict mode to ensure the LLM outputs valid JSON.
## 34
## ○ Decision:
■ IF Match == True AND Confidence > 0.8 -> Pass to Stage 3.
■ ELSE -> Discard and Log Reason.
Stage 3: Waterfall Enrichment (The Data Miner)
● Objective: Find contact information for the Decision Maker at the identified company.
● Mechanism: n8n HTTP Requests executing a Waterfall logic.
## 17
● Logic (The Waterfall):
- Tier 1 (Scrape): Firecrawl scans company.com/about or company.com/team for
names/emails.
- Tier 2 (Inference): If a name is found (e.g., "Jane Doe"), use a Python script node
to generate permutations (jane@company.com, j.doe@company.com).
- Tier 3 (Validation): Use an SMTP handshake (via a free tool or script) to validate
the existence of the email.
- Tier 4 (API Fallback): If Tiers 1-3 fail, call a paid API (like Apollo or Hunter) only if
the lead score potential is high.
● Data Provenance: For every field found, the system appends a metadata tag: source:
"Firecrawl_AboutPage" or source: "Inference_Pattern_Matching".

Stage 4: Deterministic Scoring (The Analyst)
● Objective: Rank the lead using Algolia-style Tie-Breaking rules.
● Mechanism: n8n Code Node (JavaScript/Python).
## ● Logic:
○ Rule 1 (Critical): Hiring Signal Present? (Yes/No).
○ Rule 2 (High): Tech Stack Match? (e.g., Do they use the software I specialize in?).
○ Rule 3 (Medium): Decision Maker Email Verified? (Yes/No).
○ Calculation: Unlike a sum, this is a sort. Group A (Hiring+Stack+Email) > Group B
(Hiring+Stack) > Group C (Hiring).
Stage 5: Presentation & Action (The Deliverable)
● Objective: Present the lead to the user with the "Evidence Ledger."
● Mechanism: n8n Slack/Notion Node.
● Output: A structured card containing:
## ○ Entity: Acme Corp.
○ Signal: "Job Post: Head of Engineering."
○ Evidence: Link to the specific job post URL (Provenance).
○ Contact: jane@acme.com (Source: Company Team Page).
○ Draft Message: An LLM-generated cold email referencing the specific signal.
4.3 Concrete Example: "The Freelance React Developer"
Consider a freelancer specializing in React Native mobile apps.
- Trigger: An RSS feed from a job board picks up a post: "Seeking Mobile Engineer to
lead our iOS migration."
- Filter (Ollama): The LLM analyzes the description. It sees "iOS" and "migration." It
infers "Mobile Development" context. It extracts Company: FinTechStartup.io.
- Enrichment (Waterfall):
○ Firecrawl scrapes FinTechStartup.io.
○ It finds a "Team" page with "David Smith, CTO."
○ The inference script generates david@fintechstartup.io.
○ The SMTP check confirms the email exists.
## 4. Scoring:
○ Hiring Signal: Yes (Mobile Engineer).
○ Tech Match: Yes (React Native fits "Mobile Engineer").
○ Contact: Yes (CTO Verified).
## ○ Result: Top Tier Lead.
- Explanation: "High Priority. Active hiring for mobile roles (Source: Greenhouse Job
Board). CTO identified and verified (Source: Website Scraping)."
- Minimal Design Constraints for a Zero-Budget

## Builder
For a freelancer with zero capital, we replace expensive SaaS subscriptions with "Sweat
Equity" (setup time) and self-hosted open-source software.
5.1 Essential Components (The Stack)

Component Tool Selection Why this choice? Cost
Orchestrator n8n (Self-Hosted) Visual workflow builder,
handles HTTP
requests, native AI
integration, massive
ecosystem.
## 35
$0 (Local) / $5 (VPS)
## Intelligence Ollama Runs "frontier-class"
models (Mistral, Llama
3) locally. No per-token
cost.
## 33
## $0
Scraper Firecrawl Turns websites into
LLM-ready markdown.
Can be self-hosted to
avoid API limits.
## 31
## $0
Database PostgreSQL / SQLite Robust structured
storage. Included in
many Docker setups.
## $0
## Interface Google Sheets /
## Notion
Free, familiar UI for
viewing leads. Easy to
integrate via n8n.
## $0
474: 5.2 Open-Source Patterns & Setup Details
## Docker Configuration:
The critical challenge in a self-hosted stack is networking. When running n8n and Ollama in
Docker containers, they cannot communicate via localhost because each container has its
own isolated localhost.
● Solution: Use the Docker internal host gateway.
● Configuration: In the n8n Docker setup, set the Ollama URL to
http://host.docker.internal:11434 instead of localhost:11434. This allows the n8n
container to talk to the Ollama service running on the host machine.
## 38
Model Selection: For the "Filter" stage, use Mistral 7B or Llama 3 8B. These models are
small enough to run on consumer hardware (e.g., a MacBook Air or a $20/mo GPU VPS) but
smart enough to follow basic JSON schemas for entity extraction.
## 40

5.3 What to Avoid (Budget Killers)
● Paid All-in-One Data Suites: Avoid subscriptions to ZoomInfo or Apollo (starting at
thousands/year). Their value is in the database, but for a niche freelancer, a database is
overkill. You need a sniper rifle (custom scraper), not a carpet bomb.
● High-Frequency Scraping: Do not attempt to scrape LinkedIn profiles directly at scale
using cheap proxies. This will lead to account bans. Stick to scraping company websites
and job boards, which are generally more permissible and technically easier to access.
● Complex Vector Databases: For a freelancer managing < 10,000 leads, a full Vector
DB (like Pinecone) is unnecessary overhead. Use simple keyword matching or
PostgreSQL's pgvector extension if semantic search is absolutely needed.
## 6. Explainability & Evidence Model
To make the system "Explainable," we must treat Evidence as a first-class citizen in the data
schema.
## 6.1 Evidence Types
- Direct Observation: "We saw this text on this URL."
- Inference: "We guessed this email based on the domain pattern."
- Third-Party: "This data came from the Hunter.io API."
6.2 The Ledger Format (JSON Schema)
Every data field in the system should be wrapped in an "Evidence Object" rather than being a
raw string.

## JSON


## {
"entity_name": "Acme Corp",
## "contact_email": {
## "value": "jane@acme.com",
## "meta": {
## "confidence": 0.95,
## "source_type": "Scraped",
## "source_url": "https://acme.com/team",
"timestamp": "2025-10-27T14:30:00Z",
"extraction_method": "Firecrawl_Markdown_Parse"
## }
## },

## "intent_signal": {
"value": "Hiring Head of Product",
## "meta": {
## "confidence": 1.0,
"source_type": "RSS",
## "source_url": "https://boards.greenhouse.io/acme/jobs/12345",
"timestamp": "2025-10-27T09:00:00Z"
## }
## }
## }

## 6.3 Explanation Templates
When presenting this data to the user (e.g., in a Slack notification), the system should use a
template to parse the Ledger into a human-readable sentence.
● Template: "Lead [Entity Name] identified via ****. Contact [Email Value] found on
## ****."
● Output: "Lead Acme Corp identified via Greenhouse Job Board. Contact
jane@acme.com found on Company Team Page."
This template structure ensures that the user never has to ask "Where did this email come
from?"—the answer is intrinsic to the presentation.
## 7. Scoring & Relevance Rubric
We eschew opaque ML scoring for a Deterministic Weighted Model. This allows the user to
debug and tune the scoring logic ("Why is this score low? Oh, it's missing the Tech Stack
match").
## 7.1 The Rubric
## Criteria Category Condition Points Weighting Logic
## Intent
(Time-Sensitive)
"Hiring" or "Funding"
detected < 7 days ago
## +40 High Priority:
## Immediate
actionability.
Intent (Stale) "Hiring" detected > 30
days ago
## +10 Low Priority:
Opportunity likely
closed.
ICP Fit (Industry) Industry matches
"Target List" (e.g.,
SaaS)
## +20 Base Relevance:
Necessary for general
fit.
Decision Maker Verified Email of
Decision Maker found
+20 Access: Enables the
outreach.

Tech Stack Website uses target
tech (e.g., Shopify)
## +10 Context: Improves
email personalization.
Negative Filter Company size < 2 or >
## 1000
## -100 Disqualification: Bad
budget fit.
## 7.2 Deterministic Combination Logic
The Final Score is calculated as: Sum(Positive Factors) - Sum(Negative Factors).
Tie-Breaking Rule:
If two leads have the same score (e.g., 60), the system applies the Recency Tie-Breaker:
- Sort by Intent Timestamp (Newest First).
- If timestamps are equal, Sort by Email Confidence (Highest First).
This ensures that the "freshest" opportunities always appear at the top of the freelancer's
dashboard, aligning with the "Speed to Lead" principle of sales.
- MVP vs Scale Plan
8.1 Phase 1: The MVP (Freelancer / Localhost)
● Infrastructure: A personal laptop.
## ● Components:
○ Docker Desktop running n8n and Ollama.
○ Google Sheets as the "Database" and "Dashboard."
## ● Workflow:
○ User manually inputs 5 URLs of target companies into Google Sheets.
○ n8n watches the Sheet, triggers Firecrawl to scrape the "About" page.
○ Ollama extracts emails.
○ Results are written back to the Sheet.
## ● Cost: $0.
● Goal: Validate the extraction quality of the Local LLM.
8.2 Phase 2: The "Agency" Scale (Cloud)
● Infrastructure: A Cloud VPS (e.g., Hetzner or DigitalOcean Droplet, ~4GB RAM).
## ● Components:
○ n8n running in Production Mode (Docker Compose).
○ PostgreSQL for persistent data storage.
○ Firecrawl (Self-hosted instance) for higher volume scraping.
## ● Workflow:
○ Automated ingestion of 50+ RSS feeds (Job boards, News).
○ Continuous monitoring loop.
○ Output to a dedicated Slack channel or CRM (HubSpot Free Tier).

● Cost: ~$20 - $50 / month (mostly for VPS hosting).
● Goal: Automated, hands-free generation of 10-50 high-quality leads per week.
## 9. Risks, Legal & Ethical Notes
Building a discovery engine requires careful navigation of data privacy laws and terms of
service.
9.1 GDPR & Data Privacy (The "Legitimate Interest" Defense)
● The Risk: Processing the personal data (names, emails) of EU citizens without explicit
consent is restricted under GDPR.
● Mitigation: For B2B outreach, Recital 47 of the GDPR acknowledges "direct marketing"
as a potential Legitimate Interest.
## 41
● Requirement: To rely on this, you must conduct a Legitimate Interest Assessment
## (LIA).
## 42
This involves a three-part test:
- Purpose Test: Is there a legitimate interest? (Yes, business growth).
- Necessity Test: Is processing necessary? (Yes, you cannot email without an email
address).
- Balancing Test: Do the individual's rights override the interest? (Usually No, if the
email is a business email jane@company.com and the outreach is relevant to their
job).
● Actionable Implementation: Build a "Retention Policy" into the n8n workflow. If a lead
does not reply within 30 days, automatically delete their data from your Postgres
database to minimize liability.
## 43
9.2 Scraping Legality (The "Login Wall" Barrier)
● Public Data: Scraping publicly available data (e.g., a company's public "About" page)
has generally been upheld as legal in the US, most notably in the hiQ Labs v. LinkedIn
case, where the court ruled that accessing public data does not violate the CFAA.
## 26
● Login-Walled Data: Scraping data behind a login (e.g., logging into LinkedIn Sales
Navigator and scraping profiles) is a violation of Terms of Service and can be
interpreted as "unauthorized access."
● Strict Recommendation: Limit the GBDE to public web sources only. Do not build
bots that log into social media accounts. Rely on the "Open Web" (Company websites,
News sites, Job boards) or use official APIs where available.
## 10. Final Recommendation & Immediate Next Steps
To achieve a "best-in-class" discovery engine without the enterprise price tag, the
recommendation is to build a modular, self-hosted pipeline rather than renting an

all-in-one "Black Box."
## Why?
- Ownership: You build a proprietary asset (your Knowledge Graph) rather than renting
access to a decaying database.
- Accuracy: By using Real-Time RAG (Firecrawl + LLM), your data is fresh to the minute,
whereas ZoomInfo/Apollo data may be months old.
- Explainability: You trust the data because you see the source of every single field.
## Immediate Next Steps:
- Deploy the Stack: Install Docker Desktop. Pull the n8n/n8n and ollama/ollama images.
- Configure Networking: Set up the host.docker.internal bridge so n8n can talk to
## Ollama.
## 38
- Build the "Hello World" Agent: Create a workflow that takes a single URL, scrapes it,
and asks Ollama: "What is this company's product?"
- Implement the Evidence Ledger: Modify the workflow to output the result as a JSON
object containing { "answer": "...", "source": "URL" }.
This architecture transforms the chaotic noise of the web into a structured, transparent, and
highly valuable stream of business intelligence.
[... Truncated ...]

# Comparative Analysis of Advanced Search and Lead Intelligence Systems

## Perplexity AI (AI Search Engine)
Perplexity uses a multi-stage hybrid retrieval pipeline that combines traditional indexing with vector search.
At query time it performs lexical and semantic retrieval, then applies heuristics and embedding-based
scorers before a final cross-encoder reranker. Rather than processing full documents, it indexes
granular “snippets” (short text fragments) so that each query retrieves tens of thousands of relevant tokens
to fill an LLM’s context window. This “sub-document” approach forces the model to rely on retrieved
facts, reducing hallucination. The system is powered by large LLMs (GPT-5, Claude 4.0 Sonnet, etc.) for
understanding intent and summarizing answers. Perplexity emphasizes  explainability  by citing
sources: every answer links to original web references so users can “follow the logic”. The
architecture is a pipeline (indexing → retrieval → ML ranking → LLM answer) designed for real-time use. It
mixes deterministic signals (keyword ranking, PageRank hints) with probabilistic embeddings and
generation. This enables very fast answers (sub-20ms responses at scale) but requires a huge
infrastructure (hundreds of servers, massive crawls). In practice, we see trade-offs: Perplexity had to
optimize cost and latency in its index pipeline. Key lessons: use  hybrid  retrieval, saturate context
windows to force factual answers, and attach citations for transparency.

## Diffbot (Automated Knowledge Graph)
Diffbot builds a web-scale knowledge graph via an  autonomous   pipeline  of crawling, classification,
extraction, and linking. It crawls the entire public web regularly (creating a new graph every 4–5 days)
and uses ML models to recognize page entities (people, companies, products, etc.) and extract structured
facts from them. Those facts are then fused and linked into a graph. The system is graph-based, not a
traditional search index: queries over Diffbot’s API traverse the KG. Because it relies on ML extraction,
Diffbot records provenance and confidence with each fact. In fact, Diffbot explicitly provides metadata
about the “origin and scoring of the projected validity” for every extracted entity. This built-in
traceability means users (or downstream apps) can “follow the logic” of how a data point was obtained.
Architecturally it’s a pipeline (crawl → extract → graph), heavily ML-driven. Trade-offs include needing huge
compute to crawl/parse constantly (hundreds of millions of pages) and potential lag between updates.
Over-engineering risks arise if one tries to build a full web KG from scratch; Diffbot shows this demands
sophisticated parsing and a massive ML stack. Still, its use of structured graphs and provenance exemplifies
strong explainability and data fusion: every result can be traced to source pages and confidence scores.

## Algolia (Vector-Enhanced Search-as-a-Service)
Algolia provides a hosted, API-first search engine that blends  keyword   and   vector   search. It ingests
developers’ content (product catalogs, documents, etc.) into a multi-dimensional index and answers queries
with a hybrid algorithm. The logic pipeline is roughly: index documents, compute embeddings (for semantic
meaning), and at query time use lexical matching plus similarity scoring. Algolia’s “AI Ranking” feature also
applies machine-learned signals (user click/conversion behavior) to adjust relevance. Crucially, Algolia
emphasizes control and transparency: it explicitly exposes a Ranking Formula and dashboard so users see
why results appear and can tweak rules. This human-in-the-loop design avoids a black-box: one can
combine business logic with AI ranking. The architecture is cloud-hosted with real-time indexing and
sub-20ms query latencies. It is largely probabilistic (cosine similarities, embedding models) but supports
many deterministic controls (synonyms, custom ranking rules). Algolia scales to massive traffic (billions of
queries) and offers tools like A/B testing and personalization. Constraints include vendor lock-in (closed
source) and cost at large scale. But for a minimal explainable engine, Algolia’s rule+vector hybrid with
exposed ranking weights is a strong model: it shows how to score signals (features + business metrics) and
track relevance explanations without sacrificing AI smarts.

## Glean (Enterprise Knowledge Graph Search)
Glean is an AI-enabled enterprise search platform built on a rich knowledge graph of corporate data. It
continuously crawls and indexes all internal content (documents, apps, communications) via connectors,
storing a unified graph of people, projects, and documents. Queries go through a hybrid search
engine: lexical + semantic retrieval is overlaid by graph queries. In practice Glean uses ML (LLMs) for entity
recognition and intent parsing, then executes structured graph queries to satisfy precise requests.
For example, after understanding a query’s intent, it traverses graph edges to fetch answers exactly (e.g.
“find all employees with role X in region Y”). Explainability is baked in via the graph: edges carry provenance,
confidence, timestamps and even access controls. Glean notes that knowledge graphs eliminate many
LLM errors (hallucinations or mis-joins) by grounding answers in verified entities. The architecture is
a  crawler + graph (a form of pipeline feeding a graph database) with auxiliary “personal graph” layers
. It is largely deterministic at query time (structured queries on KG) with ML used for NLU and graph
building. Constraints are complexity and cost: building such an enterprise graph required years of
development and real-time infrastructure. A key lesson is that indexing and unifying data first is
essential  – as Glean notes, simple federated search lacks the structure and signals for multi-source
reasoning. In sum, Glean demonstrates that a KG-driven pipeline yields highly explainable results (via
graph metadata), but is heavyweight for a solo dev.

## Clearbit (B2B Data Enrichment)
Clearbit is a lead intelligence API that enriches contacts/companies by aggregating many data sources. Its
logic is ETL-like: combine data from 250+ public and private databases (websites, social profiles, job listings,
etc.), then transform and clean it into attributes. Crucially, Clearbit  scores and weights  each source
dynamically: when merging data it “weights and scores each data source in real time” to decide which value
to trust for a field. Each record is verified through checks (recency, cross-source agreement, anomaly
detection, and even human review) to maximize accuracy. The product delivers deterministic attributes
(e.g. company size, industry, tech stack) via an API lookup. There is no LLM or free-text reasoning: it’s a rule/
heuristic pipeline. Explainability is indirect – users don’t see source weights, but Clearbit’s process implies
traceability (data points come from known sources). Key traits: near-real-time updates (every 30 days) for
freshness, but not true “real-time”. Probabilistic elements appear in scoring and anomaly detection.
Known limits: coverage gaps (any data not in those sources will be missing), stale data between refreshes,
and dependency on external APIs. For an open-source tool, Clearbit’s model suggests using multi-source
enrichment with confidence scoring and regular refresh, but also highlights that purely aggregated data
lacks interactive explanation.

## Apollo.io (Sales Intelligence Platform)
Apollo provides a lead generation platform with a sophisticated backend. It crawls and consolidates contact
and company data, but also built its own search over that data. Internally, Apollo uses Elasticsearch to
index entities (people, companies, contacts, accounts, etc.). Its search layer historically struggled with cross-
entity joins (e.g. find emails of contacts at certain companies). The team solved this by integrating the Siren
Federate plugin into ES, enabling efficient “JOIN-like” queries. Thus, Apollo’s logic for discovery is:
full-text filter each entity index, then federate across indices for relationships. Ranking is largely based on
relevance in ES (term scores, filters). Unlike Perplexity or Diffbot, Apollo does not expose a natural-language
LLM answer; it returns raw records with attributes. Explainability is minimal (no citations or trace); it’s a
search UI. Architecture: pipeline ETL into MongoDB → Snowflake → Elasticsearch, real-time query on ES
. We see trade-offs: building this system was complex and costly – Apollo documented spending months
and significant engineering (Airflow, Databricks, custom ingestion) to scale their data platform. They
also note first ingestion took >10 hours/week. The key takeaway is that high recall cross-entity search
(Apollo’s use case) required specialized infrastructure (federated ES), which may be overkill for a lean client
discovery tool.

## Clay (GTM Data Orchestration)
Clay is a no-code GTM platform that combines data from many providers with workflow automation. It
aggregates premium data from  150+ providers  to enrich leads (firmographics, contact info). It also
monitors intent signals (job changes, web visits, social mentions) and offers AI agents (“Claygents”) to
mine public databases and even fill out web forms for deeper insights. Essentially, Clay’s pipeline pulls
in raw signals (like Clearbit) and then allows custom enrichment and outreach flows. The core architecture is
a  data pipeline + workflow engine: connectors ingest data, a database unifies it, and user-defined flows
(with conditional logic) act on it. It uses AI in two ways: (1) data coverage – e.g. it reports doubling email
coverage via OpenAI embeddings, and (2) AI agents for searching data sources (“search public
databases... with Claygent”). However, results are again records, not natural-language answers. Clay’s
design is heavily rule-based with optional LLM hooks. Explainability comes from transparency of data
sources (users can see enrichments from each provider) and workflow steps, but any AI outputs (e.g. AI-
generated tags) are opaque. The system is built for scale (millions of records sync) and has a powerful
control plane (dynamic segments, sequencer). Constraints include complexity and cost: tapping 150
providers means depending on many APIs, and workflows can become complex. The lessons are: reuse
multi-source enrichment and signals like Clearbit, but also allow human-readable workflows. Clay shows
how combining external data, trigger signals, and AI agents can automate client discovery, but it is a
heavyweight (and mostly closed-source, SaaS) stack.

## PhantomBuster (Social Scraping Automation)
PhantomBuster   is   a   browser-based   automation   platform   for   lead   scraping.   Its   pipeline   is   very
straightforward: it runs  “Phantoms” (scripts) that scrape public web platforms (LinkedIn, Twitter, Google
Maps, etc.) for leads, then optionally enrich them and trigger actions. For example, one Phantom might
export LinkedIn search results, another fetch emails or titles from profiles. Users can chain Phantoms or use
pre-built  Workflows  that   automate   find→enrich→outreach   steps.   PhantomBuster’s   logic   is
deterministic: it interacts with web UIs or APIs and parses HTML/JSON. It doesn’t infer intent or score
leads; it simply collects data as-is. There is a bit of “AI” in content generation for messaging, but mostly
it’s a low-level data extraction toolkit. Explainability is minimal – you get the raw data points, and you must
verify them yourself. Scalability is limited (subject to site rate limits and automation slots) and is brittle
(platform changes can break scrapers). However, it excels at bootstrapping a lead database from social
signals. The trade-offs: it’s cheap (browser scripts) and simple, but fragile and unlabeled (no confidence
scores, no smart relevance). Its best use is as a data source rather than a logic engine.

## Comparative Insights for an Explainable Client-Discovery Engine
Across these systems, the  strongest   logic   model  for a minimal but powerful client discovery engine
combines a hybrid retrieval pipeline with explicit evidence tracking. In practice this means indexing candidate
sources (websites, social profiles, public databases) and retrieving both keyword matches and semantic
embeddings, then using a lightweight generative model or rule engine to interpret query intent. The engine
should saturate a knowledge context (like Perplexity’s snippet approach) so that answers rely on
actual data, not hallucination. Unlike a pure LLM chatbot, it would present found insights as structured
records or bullet points, each tagged with its source link and confidence. Diffbot’s model of attaching
provenance and validity scores to every fact is a best practice: an open system should show why it
believes a given lead fits (e.g. “this person’s email was extracted from LinkedIn on date X”). Similarly,
incorporating Algolia-style relevance controls (weights, rules) allows tuning: one might boost leads by
relevance to the freelancer’s domain or by freshness, and explain results via scores or term highlights.
Best practices to reuse:
-   Signal   scoring   and   weighting:  Like Clearbit and Algolia, assign weights to different signals (source
trustworthiness, recency, domain match). For example, tag a lead’s attributes with a confidence from each
source.
-  Evidence tracking: Store the origin of each datum. Emulate Diffbot’s traceability: show the snippet
URL or document that gave you a piece of data. This grounds answers in verifiable facts.
-  Service/intake mapping: Build a simple ontology (akin to a mini-knowledge graph) of service categories.
Glean’s notion of a graph of entities suggests mapping clients to services and skills. Even a small graph (e.g.
person → company → industry relationships) can improve relevance and explainability.
-  Iterative pipelines: Use a staged pipeline (fetch → filter → rank → generate) as in Perplexity. Each
stage should expose intermediate outputs for auditing.
Pitfalls to avoid:
-  Black-box AI: Don’t rely solely on an LLM for final output without attribution. Systems like Perplexity and
Glean show that black-box answers reduce trust. Instead, wrap any model in a transparent retrieval step
and cite sources.
-  Unnecessary complexity: Avoid full-scale knowledge graphs or massive infrastructure if your data scale is
small. Apollo’s experience shows that a heavyweight ML platform can cost 5–6 figures to build and slow
down agility. Choose simpler open tools (e.g. Elasticsearch or an open vector DB) over designing a
new graph engine unless needed.
-   Overreliance   on   one   platform’s   data:  Don’t hard-code data sources that may change or go paid.
PhantomBuster’s fragility warns that scraping LinkedIn or other proprietary sites is brittle. If possible, favor
open data (e.g. company registries, job boards) or user-submitted info.
-  Ignoring explainability: Never output leads without context. For example, failing to note why a lead was
surfaced (what keywords matched, or what signal triggered it) makes the tool opaque. Algolia’s emphasis
on visibility and Diffbot’s provenance should inspire including similar traces in a lean system.

## Strongest Minimal Model
In summary, the best model is a hybrid search pipeline that retrieves relevant candidates using keyword+semantic search, then refines and explains results using lightweight AI and evidence links. The retrieval stage (Elasticsearch + vector embeddings) provides recall; a re-ranking stage (perhaps using a smaller transformer or even heuristic scoring) ensures relevance; and finally the system highlights confidence factors and source links for each suggested client. This mirrors Perplexity’s layered search and Diffbot’s evidence tracking. The engine would not be a black-box LLM but rather a transparent,   reproducible   pipeline  of signals. Implemented with open tools (FAISS or Pinecone for vectors, Elasticsearch or SQLite for keyword, LangChain-style RAG templates, etc.), it would allow a solo developer to harness modern AI search techniques in an explainable way.
