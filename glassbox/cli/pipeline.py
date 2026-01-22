"""
Pipeline Orchestrator for GlassBox Discovery Engine.

Phase 5A: Ties all phases together into a single execution flow.

Pipeline stages:
    1. Signal Ingestion (Phase 1)
    2. Entity Resolution (Phase 2)
    3. Waterfall Enrichment (Phase 3)
    4. Lead Ranking (Phase 4)

The pipeline is read-only and deterministic.
No configuration. No tuning. No persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib

from ..domain import Entity, Signal, Rejection
from ..ingestion.rss import ingest_rss_feed, BatchIngestionResult
from ..resolution.entity_resolver import resolve_signals, BatchResolutionResult
from ..enrichment.waterfall import enrich_entities, EnrichmentResult
from ..ranking.scorer import score_leads, RankedLead


# =============================================================================
# PIPELINE RESULT
# =============================================================================

@dataclass
class PipelineResult:
    """
    Complete result of running the GlassBox pipeline.
    
    Exposes:
    - All ranked leads
    - All rejections (for audit)
    - Processing statistics
    """
    ranked_leads: list[RankedLead]
    rejections: list[Rejection]
    
    # Statistics
    total_signals_processed: int = 0
    signals_accepted: int = 0
    signals_rejected: int = 0
    entities_resolved: int = 0
    entities_rejected: int = 0
    
    # Metadata
    run_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def get_lead_by_id(self, lead_id: str) -> Optional[RankedLead]:
        """Find a lead by its ID."""
        for lead in self.ranked_leads:
            if self._generate_lead_id(lead) == lead_id:
                return lead
        return None
    
    @staticmethod
    def _generate_lead_id(lead: RankedLead) -> str:
        """Generate a stable ID for a lead."""
        # Use domain as the stable identifier
        domain = lead.entity.get_domain_value()
        return hashlib.md5(domain.encode()).hexdigest()[:8]
    
    def get_lead_ids(self) -> list[tuple[str, RankedLead]]:
        """Get all leads with their IDs."""
        return [
            (self._generate_lead_id(lead), lead)
            for lead in self.ranked_leads
        ]


# =============================================================================
# SAMPLE DATA (For Demo Purposes)
# =============================================================================

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Tech Jobs</title>
    <item>
      <title>Senior Engineer at Acme Labs</title>
      <link>https://boards.greenhouse.io/acmelabs/jobs/123</link>
      <description>Acme Labs is hiring a Senior Engineer to join our SaaS platform team!</description>
      <pubDate>Thu, 20 Jan 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Developer at TechStartup</title>
      <link>https://boards.greenhouse.io/techstartup/jobs/456</link>
      <description>Join TechStartup as a founding engineer. We're building the future of payments.</description>
      <pubDate>Wed, 21 Jan 2026 14:30:00 GMT</pubDate>
    </item>
    <item>
      <title>Engineer at CloudCo</title>
      <link>https://boards.greenhouse.io/cloudco/jobs/789</link>
      <description>CloudCo is hiring! Help us build cloud infrastructure for enterprise clients.</description>
      <pubDate>Mon, 19 Jan 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


# =============================================================================
# PIPELINE EXECUTION
# =============================================================================

def run_pipeline(
    rss_xml: Optional[str] = None,
    source_url: str = "https://demo.glassbox.local/feed.xml",
) -> PipelineResult:
    """
    Execute the full GlassBox pipeline.
    
    Stages:
        1. Ingest signals from RSS
        2. Resolve signals into entities
        3. Enrich entities with optional context
        4. Rank leads and generate explanations
    
    Args:
        rss_xml: RSS feed content (uses sample data if None)
        source_url: URL of the RSS source
    
    Returns:
        PipelineResult with ranked leads and audit information
    """
    # Use sample data if none provided
    if rss_xml is None:
        rss_xml = SAMPLE_RSS_XML
    
    all_rejections: list[Rejection] = []
    
    # ==========================================================================
    # STAGE 1: Signal Ingestion (Phase 1)
    # ==========================================================================
    ingestion_result = ingest_rss_feed(rss_xml, source_url)
    
    # Collect rejections
    all_rejections.extend(ingestion_result.rejected)
    
    accepted_signals = ingestion_result.accepted
    
    # ==========================================================================
    # STAGE 2: Entity Resolution (Phase 2)
    # ==========================================================================
    resolution_result = resolve_signals(accepted_signals)
    
    # Collect rejections
    all_rejections.extend(resolution_result.rejected)
    
    resolved_entities = resolution_result.resolved
    
    # Track which signal goes with which entity (for enrichment and ranking)
    # Since we process in order, signals[i] corresponds to entities[i]
    entity_signal_pairs: list[tuple[Entity, Signal]] = []
    signal_idx = 0
    for entity in resolved_entities:
        # Find the corresponding signal
        if signal_idx < len(accepted_signals):
            entity_signal_pairs.append((entity, accepted_signals[signal_idx]))
        signal_idx += 1
    
    # ==========================================================================
    # STAGE 3: Waterfall Enrichment (Phase 3)
    # ==========================================================================
    enriched_entities = []
    enriched_signals = []
    
    for entity, signal in entity_signal_pairs:
        from ..enrichment.waterfall import enrich_entity
        result = enrich_entity(entity, signal)
        enriched_entities.append(result.entity)
        enriched_signals.append(signal)
    
    # ==========================================================================
    # STAGE 4: Lead Ranking (Phase 4)
    # ==========================================================================
    ranked_leads = score_leads(
        entities=enriched_entities,
        signals=enriched_signals,
    )
    
    # ==========================================================================
    # RETURN RESULT
    # ==========================================================================
    return PipelineResult(
        ranked_leads=ranked_leads,
        rejections=all_rejections,
        total_signals_processed=ingestion_result.total_items,
        signals_accepted=len(accepted_signals),
        signals_rejected=len(ingestion_result.rejected),
        entities_resolved=len(resolved_entities),
        entities_rejected=len(resolution_result.rejected),
    )


# =============================================================================
# GLOBAL STATE (In-Memory, Not Persisted)
# =============================================================================

# Most recent pipeline result (for CLI/API access)
_last_result: Optional[PipelineResult] = None


def get_last_result() -> Optional[PipelineResult]:
    """Get the most recent pipeline result."""
    return _last_result


def set_last_result(result: PipelineResult) -> None:
    """Store the most recent pipeline result."""
    global _last_result
    _last_result = result
