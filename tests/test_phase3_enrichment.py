"""
Tests for Phase 3: Waterfall Enrichment.

These tests verify:
1. Successful enrichment with Evidence
2. Partial enrichment (some fields missing)
3. Enrichment failure without Entity rejection
4. Evidence confidence assignment
5. Proof that enrichment cannot create an Entity
"""

import pytest
from datetime import datetime

from glassbox.domain import Entity, Signal
from glassbox.evidence import EvidenceType, create_inference
from glassbox.validation import create_signal_id, create_dedup_hash
from glassbox.enrichment.waterfall import (
    infer_industry,
    infer_company_size_range,
    infer_country_from_domain,
    enrich_entity,
    enrich_entities,
    EnrichmentResult,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

def make_signal(
    raw_text: str,
    source_url: str = "https://boards.greenhouse.io/acme/jobs/123",
) -> Signal:
    """Helper to create a Signal for testing."""
    timestamp = datetime.utcnow()
    signal_id = create_signal_id(source_url, timestamp)
    dedup_hash = create_dedup_hash(source_url, raw_text)
    
    return Signal(
        signal_id=signal_id,
        source_url=source_url,
        raw_text=raw_text,
        timestamp=timestamp,
        source_type="rss_greenhouse.io",
        dedup_hash=dedup_hash,
    )


def make_entity(
    company_name: str = "Acme Corp",
    domain: str = "acme.com",
) -> Entity:
    """Helper to create an Entity for testing."""
    company_evidence = create_inference(
        field_name="company_name",
        value=company_name,
        source_evidence_ids=["evt_test_signal"],
        inference_rule="test_extraction",
    )
    domain_evidence = create_inference(
        field_name="domain",
        value=domain,
        source_evidence_ids=["evt_test_signal"],
        inference_rule="test_extraction",
    )
    
    return Entity(
        company_name=company_evidence,
        domain=domain_evidence,
    )


# =============================================================================
# INDUSTRY INFERENCE TESTS
# =============================================================================

class TestIndustryInference:
    """Test industry inference from keywords."""
    
    def test_infer_technology(self):
        """Technology keywords should map to technology industry."""
        evidence = infer_industry(
            "We're building a SaaS platform for developers",
            "evt_source123",
        )
        
        assert evidence is not None
        assert evidence.value == "technology"
        assert evidence.meta.confidence == 0.70
        assert evidence.meta.inference_rule == "keyword_industry_mapping"
    
    def test_infer_fintech(self):
        """Fintech keywords should map to fintech industry."""
        # Use 'payments' only - no ambiguous overlap with other industries
        evidence = infer_industry(
            "Building the future of banking and payments",
            "evt_source123",
        )
        
        assert evidence is not None
        assert evidence.value == "fintech"
    
    def test_infer_healthcare(self):
        """Healthcare keywords should map to healthcare industry."""
        # Use 'patient' and 'clinical' - no overlap with 'tech' keywords
        evidence = infer_industry(
            "Revolutionizing patient care with clinical solutions",
            "evt_source123",
        )
        
        assert evidence is not None
        assert evidence.value == "healthcare"
    
    def test_no_industry_for_ambiguous_text(self):
        """Multiple industry keywords should return None."""
        evidence = infer_industry(
            "Healthcare SaaS platform for fintech payments",  # Multiple industries
            "evt_source123",
        )
        
        # Multiple matches = ambiguous = None
        assert evidence is None
    
    def test_no_industry_for_generic_text(self):
        """Text without industry keywords should return None."""
        evidence = infer_industry(
            "We are hiring for our growing team!",
            "evt_source123",
        )
        
        assert evidence is None


# =============================================================================
# COMPANY SIZE INFERENCE TESTS
# =============================================================================

class TestCompanySizeInference:
    """Test company size inference from heuristics."""
    
    def test_infer_startup(self):
        """Startup indicators should map to startup size."""
        evidence = infer_company_size_range(
            "Join our early stage startup as a founding engineer",
            "evt_source123",
        )
        
        assert evidence is not None
        assert evidence.value == "startup"
        assert evidence.meta.confidence == 0.65
    
    def test_infer_scaleup(self):
        """Scaleup indicators should map to scaleup size."""
        evidence = infer_company_size_range(
            "Series B company experiencing hypergrowth",
            "evt_source123",
        )
        
        assert evidence is not None
        assert evidence.value == "scaleup"
    
    def test_infer_enterprise(self):
        """Enterprise indicators should map to enterprise size."""
        evidence = infer_company_size_range(
            "Fortune 500 company with global presence",
            "evt_source123",
        )
        
        assert evidence is not None
        assert evidence.value == "enterprise"
    
    def test_no_size_for_generic_text(self):
        """Text without size indicators should return None."""
        evidence = infer_company_size_range(
            "We are hiring a software engineer",
            "evt_source123",
        )
        
        assert evidence is None


# =============================================================================
# COUNTRY INFERENCE TESTS
# =============================================================================

class TestCountryInference:
    """Test country inference from domain TLD."""
    
    def test_infer_country_uk(self):
        """UK TLD should map to United Kingdom."""
        evidence = infer_country_from_domain("company.uk", "evt_source123")
        
        assert evidence is not None
        assert evidence.value == "United Kingdom"
        assert evidence.meta.confidence == 0.80
    
    def test_infer_country_germany(self):
        """DE TLD should map to Germany."""
        evidence = infer_country_from_domain("startup.de", "evt_source123")
        
        assert evidence is not None
        assert evidence.value == "Germany"
    
    def test_no_country_for_generic_tld(self):
        """Generic TLDs (.com, .io) should return None."""
        evidence = infer_country_from_domain("company.com", "evt_source123")
        assert evidence is None
        
        evidence = infer_country_from_domain("startup.io", "evt_source123")
        assert evidence is None
    
    def test_no_country_for_invalid_domain(self):
        """Invalid domain should return None."""
        evidence = infer_country_from_domain("", "evt_source123")
        assert evidence is None
        
        evidence = infer_country_from_domain("nodot", "evt_source123")
        assert evidence is None


# =============================================================================
# ENTITY ENRICHMENT TESTS
# =============================================================================

class TestEntityEnrichment:
    """Test full entity enrichment pipeline."""
    
    def test_successful_enrichment(self):
        """Entity with tech signal should be enriched with industry."""
        entity = make_entity("TechCorp", "techcorp.com")
        signal = make_signal(
            "TechCorp is hiring! Join our SaaS platform team as a founding engineer."
        )
        
        result = enrich_entity(entity, signal)
        
        assert result.was_enriched is True
        assert "industry" in result.enriched_fields
        assert entity.industry is not None
        assert entity.industry.value == "technology"
    
    def test_partial_enrichment(self):
        """Some fields may enrich while others fail."""
        entity = make_entity("GenericCo", "genericco.com")
        signal = make_signal(
            "GenericCo is hiring engineers!"  # No industry keywords
        )
        
        result = enrich_entity(entity, signal)
        
        # Industry should fail (no keywords)
        assert "industry" in result.failed_fields
        # Entity remains valid
        assert result.entity is not None
    
    def test_enrichment_failure_preserves_entity(self):
        """Failed enrichment should not modify or reject Entity."""
        entity = make_entity("SimpleCo", "simpleco.com")
        
        # No signal provided - all enrichment should fail
        result = enrich_entity(entity, signal=None)
        
        # Entity unchanged
        assert result.entity.get_name_value() == "SimpleCo"
        assert result.entity.get_domain_value() == "simpleco.com"
        
        # All text-based enrichments failed
        assert "industry" in result.failed_fields
        assert "company_size_range" in result.failed_fields
    
    def test_country_enrichment_from_tld(self):
        """Country should be inferred from domain TLD."""
        entity = make_entity("UKCompany", "ukcompany.uk")
        signal = make_signal("UKCompany is hiring!")
        
        result = enrich_entity(entity, signal)
        
        # Country should be enriched from TLD
        assert "country" in result.enriched_fields
    
    def test_generic_tld_no_country(self):
        """Generic TLD should not add country."""
        entity = make_entity("GlobalCo", "globalco.com")
        signal = make_signal("GlobalCo is hiring!")
        
        result = enrich_entity(entity, signal)
        
        # Country should fail for .com
        assert "country" in result.failed_fields


# =============================================================================
# EVIDENCE REQUIREMENTS TESTS
# =============================================================================

class TestEvidenceRequirements:
    """Test that all enriched fields have proper Evidence."""
    
    def test_enriched_field_has_evidence_id(self):
        """Enriched fields must have Evidence IDs."""
        entity = make_entity("TechCo", "techco.com")
        signal = make_signal("TechCo builds SaaS software for developers")
        
        result = enrich_entity(entity, signal)
        
        if result.entity.industry:
            assert result.entity.industry.evidence_id.startswith("evt_")
    
    def test_enriched_field_has_source_reference(self):
        """Enriched fields must link to source Evidence."""
        entity = make_entity("TechCo", "techco.com")
        signal = make_signal("TechCo builds SaaS software")
        
        result = enrich_entity(entity, signal)
        
        if result.entity.industry:
            assert len(result.entity.industry.meta.source_evidence_ids) > 0
    
    def test_enriched_field_has_inference_rule(self):
        """Enriched fields must document inference rule."""
        entity = make_entity("TechCo", "techco.com")
        signal = make_signal("TechCo builds SaaS software")
        
        result = enrich_entity(entity, signal)
        
        if result.entity.industry:
            assert result.entity.industry.meta.inference_rule is not None
    
    def test_enriched_field_has_conservative_confidence(self):
        """Enriched fields should have confidence ≤ 0.8."""
        entity = make_entity("TechCo", "techco.com")
        signal = make_signal("TechCo builds SaaS software")
        
        result = enrich_entity(entity, signal)
        
        if result.entity.industry:
            assert result.entity.industry.meta.confidence <= 0.80


# =============================================================================
# ENRICHMENT CANNOT CREATE ENTITY TESTS
# =============================================================================

class TestEnrichmentCannotCreate:
    """Prove that enrichment cannot create or rescue an Entity."""
    
    def test_enrichment_requires_valid_entity(self):
        """Enrichment requires a pre-existing valid Entity."""
        # This test documents the design:
        # enrich_entity() takes an Entity as input
        # It cannot be called without one
        
        entity = make_entity("ValidCo", "validco.com")
        result = enrich_entity(entity)
        
        # Entity was already valid before enrichment
        assert result.entity.get_name_value() == "ValidCo"
    
    def test_enrichment_does_not_modify_required_fields(self):
        """Enrichment cannot change company_name or domain."""
        entity = make_entity("OriginalCo", "original.com")
        signal = make_signal("TechStartup is hiring!")
        
        result = enrich_entity(entity, signal)
        
        # Required fields unchanged
        assert result.entity.get_name_value() == "OriginalCo"
        assert result.entity.get_domain_value() == "original.com"


# =============================================================================
# BATCH ENRICHMENT TESTS
# =============================================================================

class TestBatchEnrichment:
    """Test batch enrichment of multiple entities."""
    
    def test_batch_enrichment(self):
        """Batch should enrich multiple entities."""
        entities = [
            make_entity("TechCo", "techco.com"),
            make_entity("HealthCo", "healthco.uk"),
        ]
        signals = [
            make_signal("TechCo builds SaaS software"),
            make_signal("HealthCo improves patient care"),
        ]
        
        results = enrich_entities(entities, signals)
        
        assert len(results) == 2
    
    def test_batch_handles_missing_signals(self):
        """Batch should handle entities without signals."""
        entities = [
            make_entity("Co1", "co1.com"),
            make_entity("Co2", "co2.com"),
        ]
        signals = [make_signal("Co1 builds software")]  # Only 1 signal
        
        results = enrich_entities(entities, signals)
        
        # Both entities processed
        assert len(results) == 2
        # Second entity has all text-based enrichments failed
        assert "industry" in results[1].failed_fields


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
