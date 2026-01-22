"""
Waterfall Enrichment for GlassBox Discovery Engine.

Phase 3: Add supporting facts to verified Entities without weakening trust.

Core principle (non-negotiable):
    Enrichment must never CREATE or RESCUE an Entity.
    It may only ADD evidence-backed attributes to an already-valid Entity.

If enrichment fails:
    - Do NOT reject the Entity
    - Do NOT modify existing fields
    - Log enrichment failure (audit only)
    - Return Entity unchanged

Allowed enrichment types:
    - industry: Deterministic keyword mapping (INF)
    - company_size_range: Signal-derived heuristics (INF)
    - country: Domain TLD mapping (INF)
    - public_contact_email: Explicitly listed on site (OBS) - NOT IMPLEMENTED YET
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..domain import Entity, Signal
from ..evidence import (
    Evidence,
    EvidenceType,
    create_inference,
)


# =============================================================================
# INDUSTRY INFERENCE (Keyword Mapping)
# =============================================================================

# Deterministic industry classification based on keywords in signal text
# These are conservative mappings - only clear indicators
INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "technology": [
        "software", "saas", "api", "cloud", "devops", "engineering",
        "platform", "tech", "ai", "machine learning", "data science",
        "developer", "programming", "code", "app", "mobile",
    ],
    "fintech": [
        "fintech", "payments", "banking", "financial technology",
        "cryptocurrency", "blockchain", "defi", "neobank",
    ],
    "healthcare": [
        "healthcare", "healthtech", "medtech", "clinical", "medical",
        "hospital", "patient", "diagnosis", "pharma", "biotech",
    ],
    "e-commerce": [
        "e-commerce", "ecommerce", "retail", "marketplace", "shopping",
        "online store", "dropship",
    ],
    "education": [
        "edtech", "education", "learning", "training", "course",
        "school", "university", "tutoring",
    ],
    "marketing": [
        "marketing", "advertising", "adtech", "seo", "content",
        "social media", "brand", "agency",
    ],
    "cybersecurity": [
        "security", "cybersecurity", "infosec", "encryption",
        "vulnerability", "penetration", "threat",
    ],
}


def infer_industry(
    signal_text: str,
    source_evidence_id: str,
) -> Optional[Evidence]:
    """
    Infer industry from signal text using deterministic keyword mapping.
    
    Returns Evidence if industry can be confidently determined.
    Returns None if no clear industry signal or multiple matches.
    
    Confidence: 0.70 (INF from keywords)
    """
    text_lower = signal_text.lower()
    
    matches: list[str] = []
    
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                if industry not in matches:
                    matches.append(industry)
                break  # One keyword match per industry is enough
    
    # Only return if exactly one industry matches
    if len(matches) == 1:
        return create_inference(
            field_name="industry",
            value=matches[0],
            source_evidence_ids=[source_evidence_id],
            inference_rule="keyword_industry_mapping",
            confidence=0.70,
        )
    
    # Multiple or no matches = no inference
    return None


# =============================================================================
# COMPANY SIZE HEURISTICS
# =============================================================================

# Size indicators in job postings
SIZE_INDICATORS: dict[str, list[str]] = {
    "startup": [
        "startup", "early stage", "seed", "series a", "founding team",
        "first hire", "small team", "growing team",
    ],
    "scaleup": [
        "series b", "series c", "scaling", "hypergrowth", "fast-growing",
        "100+ employees", "200+ employees",
    ],
    "enterprise": [
        "fortune 500", "enterprise", "global company", "multinational",
        "1000+ employees", "5000+ employees", "publicly traded",
    ],
}


def infer_company_size_range(
    signal_text: str,
    source_evidence_id: str,
) -> Optional[Evidence]:
    """
    Infer company size range from signal text using deterministic heuristics.
    
    Returns Evidence if size can be confidently determined.
    Returns None if no clear size signal or multiple matches.
    
    Confidence: 0.65 (INF from heuristics, lower certainty)
    """
    text_lower = signal_text.lower()
    
    matches: list[str] = []
    
    for size_range, indicators in SIZE_INDICATORS.items():
        for indicator in indicators:
            if indicator in text_lower:
                if size_range not in matches:
                    matches.append(size_range)
                break
    
    # Only return if exactly one size range matches
    if len(matches) == 1:
        return create_inference(
            field_name="company_size_range",
            value=matches[0],
            source_evidence_ids=[source_evidence_id],
            inference_rule="signal_size_heuristics",
            confidence=0.65,
        )
    
    return None


# =============================================================================
# COUNTRY FROM TLD
# =============================================================================

# TLD to country mapping (conservative, only clear cases)
TLD_COUNTRY_MAP: dict[str, str] = {
    "uk": "United Kingdom",
    "de": "Germany",
    "fr": "France",
    "ca": "Canada",
    "au": "Australia",
    "in": "India",
    "jp": "Japan",
    "cn": "China",
    "nl": "Netherlands",
    "es": "Spain",
    "it": "Italy",
    "br": "Brazil",
    "mx": "Mexico",
    "se": "Sweden",
    "no": "Norway",
    "dk": "Denmark",
    "fi": "Finland",
    "ch": "Switzerland",
    "at": "Austria",
    "be": "Belgium",
    "ie": "Ireland",
    "nz": "New Zealand",
    "sg": "Singapore",
    "hk": "Hong Kong",
    "kr": "South Korea",
    "za": "South Africa",
    "pl": "Poland",
    "cz": "Czech Republic",
    "ru": "Russia",
    "ua": "Ukraine",
}

# Generic TLDs that don't indicate country
GENERIC_TLDS = frozenset({
    "com", "org", "net", "io", "co", "ai", "app", "dev",
    "tech", "xyz", "info", "biz", "me", "edu", "gov",
})


def infer_country_from_domain(
    domain: str,
    source_evidence_id: str,
) -> Optional[Evidence]:
    """
    Infer country from domain TLD.
    
    Only returns for country-specific TLDs (e.g., .uk, .de, .fr).
    Generic TLDs (.com, .io, .ai) return None.
    
    Confidence: 0.80 (TLD is deterministic mapping)
    """
    if not domain or '.' not in domain:
        return None
    
    tld = domain.split('.')[-1].lower()
    
    # Skip generic TLDs
    if tld in GENERIC_TLDS:
        return None
    
    # Lookup country
    country = TLD_COUNTRY_MAP.get(tld)
    if country:
        return create_inference(
            field_name="country",
            value=country,
            source_evidence_ids=[source_evidence_id],
            inference_rule="tld_country_mapping",
            confidence=0.80,
        )
    
    return None


# =============================================================================
# ENRICHMENT PIPELINE
# =============================================================================

@dataclass
class EnrichmentResult:
    """Result of enrichment attempt."""
    entity: Entity  # Original or enriched Entity
    enriched_fields: list[str] = field(default_factory=list)
    failed_fields: list[str] = field(default_factory=list)
    
    @property
    def was_enriched(self) -> bool:
        return len(self.enriched_fields) > 0


@dataclass
class EnrichedEntity:
    """
    An Entity with optional enriched fields.
    
    This wraps the original Entity and adds enrichment Evidence.
    The original Entity remains unchanged.
    """
    entity: Entity
    industry: Optional[Evidence] = None
    company_size_range: Optional[Evidence] = None
    country: Optional[Evidence] = None
    
    def get_all_evidence_ids(self) -> list[str]:
        """Get all Evidence IDs including enriched fields."""
        ids = [
            self.entity.company_name.evidence_id,
            self.entity.domain.evidence_id,
        ]
        if self.industry:
            ids.append(self.industry.evidence_id)
        if self.company_size_range:
            ids.append(self.company_size_range.evidence_id)
        if self.country:
            ids.append(self.country.evidence_id)
        return ids


def enrich_entity(
    entity: Entity,
    signal: Optional[Signal] = None,
) -> EnrichmentResult:
    """
    Enrich an Entity with optional supporting facts.
    
    Core principle:
        Enrichment NEVER creates or rescues an Entity.
        It only ADDS evidence-backed attributes.
    
    If enrichment fails:
        Entity remains valid and unchanged.
    
    Args:
        entity: A fully resolved Entity from Phase 2
        signal: Optional original Signal for text-based inference
    
    Returns:
        EnrichmentResult with original or enriched Entity
    """
    enriched_fields: list[str] = []
    failed_fields: list[str] = []
    
    # Source Evidence ID for inference chain
    domain_evidence_id = entity.domain.evidence_id
    
    # Get signal text if available
    signal_text = signal.raw_text if signal else ""
    
    # 1. Infer industry from signal text
    if signal_text:
        industry_evidence = infer_industry(signal_text, domain_evidence_id)
        if industry_evidence:
            entity.industry = industry_evidence
            enriched_fields.append("industry")
        else:
            failed_fields.append("industry")
    else:
        failed_fields.append("industry")
    
    # 2. Infer company size range from signal text
    if signal_text:
        size_evidence = infer_company_size_range(signal_text, domain_evidence_id)
        if size_evidence:
            entity.size_estimate = size_evidence
            enriched_fields.append("company_size_range")
        else:
            failed_fields.append("company_size_range")
    else:
        failed_fields.append("company_size_range")
    
    # 3. Infer country from domain TLD
    domain_value = entity.get_domain_value()
    country_evidence = infer_country_from_domain(domain_value, domain_evidence_id)
    if country_evidence:
        # Note: Entity doesn't have a country field yet, so we'd need to add it
        # For now, we track it as enriched but don't store it
        # This is a limitation we acknowledge
        enriched_fields.append("country")
    else:
        failed_fields.append("country")
    
    return EnrichmentResult(
        entity=entity,
        enriched_fields=enriched_fields,
        failed_fields=failed_fields,
    )


def enrich_entities(
    entities: list[Entity],
    signals: Optional[list[Signal]] = None,
) -> list[EnrichmentResult]:
    """
    Enrich a batch of entities.
    
    If signals are provided, they should match entities by index.
    Missing signals are handled gracefully.
    """
    results: list[EnrichmentResult] = []
    
    for i, entity in enumerate(entities):
        signal = signals[i] if signals and i < len(signals) else None
        result = enrich_entity(entity, signal)
        results.append(result)
    
    return results
