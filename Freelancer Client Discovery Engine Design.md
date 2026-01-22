

Architectural Blueprint for the Glass Box
## Discovery Engine: A Comparative
Analysis and Design Specification
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
5.2 Open-Source Patterns & Setup Details
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
"source_type": "Scraped",
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
Works cited
- Network Traffic Analysis of Perplexity AI: The Next-Gen Search Engine | Keysight
Blogs, accessed January 22, 2026,
https://www.keysight.com/blogs/en/tech/nwvs/2025/05/19/perplexityai-har-analys
is
- OmidZamani/perplexity-journey: A deep technical exploration of what happens
when you ask Perplexity AI a question - from query tokenization to response
generation. Inspired by "What Happens When You Type google.com" repository,
this technical guide maps the complete journey of your query through
Perplexity's architecture, algorithms, and systems. - GitHub, accessed January
22, 2026, https://github.com/OmidZamani/perplexity-journey
- Architecting and Evaluating an AI-First Search API - Perplexity Research, accessed
## January 22, 2026,
https://research.perplexity.ai/articles/architecting-and-evaluating-an-ai-first-sear
ch-api
- Introducing Perplexity Deep Research, accessed January 22, 2026,
https://www.perplexity.ai/hub/blog/introducing-perplexity-deep-research
- Perplexity AI: A Deep Dive - Reflections, accessed January 22, 2026,
https://annjose.com/post/perplexity-ai/
- How AI Engines Cite Your Content: ChatGPT, Perplexity & Claude - Hashmeta,
accessed January 22, 2026,
https://hashmeta.com/ai-search-optimisation-guide/ai-citation-mechanics-chatg
pt-perplexity-claude/
- Article - Diffbot Docs, accessed January 22, 2026,
https://docs.diffbot.com/docs/ont-article

- The Diffbot Master Plan (Part One) – Diffblog, accessed January 22, 2026,
https://blog.diffbot.com/the-diffbot-master-plan-part-one/
- Towards A Public Web Data Infused Dashboard - Diffbot Blog, accessed January
## 22, 2026,
https://blog.diffbot.com/wp-content/uploads/public-web-data-dashboards-white
paper.pdf
- How Algolia tackled the relevance problem of search engines, accessed January
## 22, 2026,
https://www.algolia.com/blog/engineering/how-algolia-tackled-the-relevance-pr
oblem-of-search-engines
- Inside the Algolia Engine Part 4 — Textual Relevance, accessed January 22, 2026,
https://www.algolia.com/blog/engineering/inside-the-algolia-enginepart-4-textua
l-relevance
- The role of security in optimizing enterprise search results - Glean, accessed
## January 22, 2026,
https://www.glean.com/perspectives/how-do-security-features-affect-enterprise
## -search
- Transform enterprise search and knowledge discovery with Glean and Amazon
Bedrock, accessed January 22, 2026,
https://aws.amazon.com/blogs/awsmarketplace/transform-enterprise-search-kn
owledge-discovery-glean-amazon-bedrock/
- What are RAG models? A guide to enterprise AI in 2025 - Glean, accessed
January 22, 2026, https://www.glean.com/blog/rag-models-enterprise-ai
- Is MCP + federated search killing the index? - Glean, accessed January 22, 2026,
https://www.glean.com/blog/federated-indexed-enterprise-ai
- Essential features for enterprise search platforms in 2025 - Glean, accessed
## January 22, 2026,
https://www.glean.com/perspectives/what-are-the-top-features-to-look-for-in-a
n-enterprise-search-platform
- How to use Clay for data enrichment | Zapier, accessed January 22, 2026,
https://zapier.com/blog/clay-data-enrichment/
- What is Clay Data Enrichment and How Should You Actually Use it?, accessed
## January 22, 2026,
https://blog.revpartners.io/en/revops-articles/what-is-clay-data-enrichment-and-
how-should-you-use-it
- Best Practices for Contact Enrichment Using Webhooks vs People & Company
API in Clay, accessed January 22, 2026,
https://community.clay.com/x/support/3vm2k1jv8v5l/best-practices-for-contact-
enrichment-using-webhoo
- Troubleshooting Conditional Logic in Multi-Layer Enrichment Flow - Clay
Community, accessed January 22, 2026,
https://community.clay.com/x/support/teleycfkh9qq/troubleshooting-conditional-l
ogic-in-multi-layer-e
- Effective Lead Scoring Using Apollo.io: Enhancing Conversion Rates | Wrk Blog,
accessed January 22, 2026,

https://www.wrk.com/blog/effective-lead-scoring-apollo-io
- Apollo.io Intent Data - B2B Sales Success with Lead Scoring & Enrichment - The AI
Surf, accessed January 22, 2026,
https://theaisurf.com/apollo-io-intent-data-b2b-sales/
- The 10 Best Data Enrichment APIs for 2025 | AbstractAPI, accessed January 22,
## 2026,
https://www.abstractapi.com/guides/company-enrichment/best-data-enrichment
## -apis
- Understand how PhantomBuster Works and What you can Automate, accessed
## January 22, 2026,
https://support.phantombuster.com/hc/en-us/articles/22306827153810-Understa
nd-how-PhantomBuster-Works-and-What-you-can-Automate
- How To Use AI + PhantomBuster To Identify, Qualify, And Personalize At Scale,
accessed January 22, 2026,
https://phantombuster.com/blog/ai-automation/how-to-use-ai-phantombuster-t
o-identify-qualify-and-personalize-at-scale/
- Everyone's Scraping LinkedIn With AI - Here's Why Your Legal Team Should Be
Panicking, accessed January 22, 2026,
https://verityai.co/blog/linkedin-scraping-ai-legal-team-panicking
- The Ultimate Guide to Scraping LinkedIn Profiles in 2025 | ScrapeCreators Blog,
accessed January 22, 2026,
https://scrapecreators.com/blog/linkedin-scraping-guide-2025
## 28. Clay Lead Enrichment: Complete 2025 Guide & Top Alternatives - Databar.ai,
accessed January 22, 2026,
https://databar.ai/blog/article/clay-lead-enrichment-complete-2025-guide-top-al
ternatives
- 50 Best Financial News RSS Feeds, accessed January 22, 2026,
https://rss.feedspot.com/financial_news_rss_feeds/
- RSS FEEDS - Grants.gov, accessed January 22, 2026,
https://www.grants.gov/connect/rss-feeds
- firecrawl/fire-enrich: AI-powered data enrichment tool that transforms emails
into rich datasets with company profiles, funding data, tech stacks, and more
using Firecrawl and multi-agent AI - GitHub, accessed January 22, 2026,
https://github.com/firecrawl/fire-enrich
- How do you integrate n8n with Ollama for local LLM workflows? - Hostinger,
accessed January 22, 2026,
https://www.hostinger.com/tutorials/n8n-ollama-integration
- Building Powerful Local AI Automations with n8n, MCP, and Ollama | atal
upadhyay, accessed January 22, 2026,
https://atalupadhyay.wordpress.com/2026/01/13/building-powerful-local-ai-auto
mations-with-n8n-mcp-and-ollama/
- Build Dynamic AI Agents with JSON Schema (No Flows) - ChatbotBuilder AI,
accessed January 22, 2026,
https://www.chatbotbuilder.ai/blog/build-dynamic-ai-agents-with-json-schema-n
o-flows

- How to use n8n for FREE - Self-Host n8n Locally Using Docker (Step-by-Step
Tutorial), accessed January 22, 2026,
https://m.youtube.com/watch?v=j8k3I_zfG4w
- How to Run LLMs Locally - Full Guide - YouTube, accessed January 22, 2026,
https://www.youtube.com/watch?v=km5-0jhv0JI
- LLM API Engine: How to Build a Dynamic API Generation Engine Powered by
Firecrawl, accessed January 22, 2026,
https://www.firecrawl.dev/blog/llm-api-engine-dynamic-api-generation-explainer
- Building an Open Source AI Assistant with n8n and Ollama: A Step-by-Step Guide,
accessed January 22, 2026,
https://aicloudautomation.net/blog/building-an-open-source-ai-assistant-with-n
## 8n-and-ollama/
- Ollama Model node common issues - n8n Docs, accessed January 22, 2026,
https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langc
hain.lmollama/common-issues/
## 40.
library - Ollama, accessed January 22, 2026, https://ollama.com/library/
- Email Marketing - General Data Protection Regulation (GDPR), accessed January
22, 2026, https://gdpr-info.eu/issues/email-marketing/
- How do we apply legitimate interests in practice? | ICO, accessed January 22,
## 2026,
https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basi
s/legitimate-interests/how-do-we-apply-legitimate-interests-in-practice/
- How does GDPR affect B2B - iubenda, accessed January 22, 2026,
https://www.iubenda.com/en/blog/how-does-gdpr-affect-b2b/