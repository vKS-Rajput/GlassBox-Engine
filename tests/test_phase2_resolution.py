"""
Tests for Phase 2: Entity Resolution.

These tests verify:
1. Successful entity resolution creates Evidence-backed Entities
2. Invalid domains are rejected
3. Ambiguous signals are rejected
4. Missing evidence causes hard rejection
5. Evidence lineage is preserved from Signal → Entity
"""

import pytest
from datetime import datetime

from glassbox.domain import Signal, RejectionRule
from glassbox.evidence import EvidenceType
from glassbox.validation import create_signal_id, create_dedup_hash
from glassbox.resolution.entity_resolver import (
    validate_domain,
    normalize_domain,
    extract_domain_from_url,
    extract_company_name_from_signal,
    extract_domain_from_signal,
    check_for_ambiguity,
    resolve_entity,
    resolve_signals,
    ResolutionResult,
    DomainValidationError,
    RejectionError,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

def make_signal(
    raw_text: str,
    source_url: str = "https://boards.greenhouse.io/acme/jobs/123",
    timestamp: datetime = None,
) -> Signal:
    """Helper to create a Signal for testing."""
    if timestamp is None:
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


# =============================================================================
# DOMAIN VALIDATION TESTS
# =============================================================================

class TestDomainValidation:
    """Test domain validation logic."""
    
    def test_valid_domain_passes(self):
        """Valid company domain should pass validation."""
        validate_domain("acme.com")  # Should not raise
    
    def test_valid_io_domain_passes(self):
        """Valid .io domain should pass."""
        validate_domain("startup.io")  # Should not raise
    
    def test_empty_domain_rejected(self):
        """Empty domain should be rejected."""
        with pytest.raises(RejectionError) as exc_info:
            validate_domain("")
        assert exc_info.value.rule == RejectionRule.R4_INVALID_DOMAIN
    
    def test_invalid_tld_rejected(self):
        """Domain with invalid/reserved TLD should be rejected."""
        with pytest.raises(RejectionError) as exc_info:
            validate_domain("company.test")
        assert exc_info.value.rule == RejectionRule.R4_INVALID_DOMAIN
    
    def test_personal_email_domain_rejected(self):
        """Personal email domains should be rejected."""
        with pytest.raises(RejectionError) as exc_info:
            validate_domain("gmail.com")
        assert exc_info.value.rule == RejectionRule.R4_INVALID_DOMAIN
        assert "Personal email" in exc_info.value.reason
    
    def test_url_shortener_rejected(self):
        """URL shortener domains should be rejected."""
        with pytest.raises(RejectionError) as exc_info:
            validate_domain("bit.ly")
        assert exc_info.value.rule == RejectionRule.R4_INVALID_DOMAIN
        assert "shortener" in exc_info.value.reason
    
    def test_job_board_domain_rejected(self):
        """Job board domains should be rejected (source, not target)."""
        with pytest.raises(RejectionError) as exc_info:
            validate_domain("greenhouse.io")
        assert exc_info.value.rule == RejectionRule.R4_INVALID_DOMAIN
        assert "signal source" in exc_info.value.reason
    
    def test_normalize_domain(self):
        """Domain normalization should be consistent."""
        assert normalize_domain("ACME.COM") == "acme.com"
        assert normalize_domain("www.acme.com") == "acme.com"
        assert normalize_domain("  acme.com.  ") == "acme.com"
    
    def test_extract_domain_from_url(self):
        """Should extract registrable domain from URL."""
        url = "https://boards.greenhouse.io/acme/jobs/123"
        assert extract_domain_from_url(url) == "greenhouse.io"
        
        url = "https://www.acme.com/careers"
        assert extract_domain_from_url(url) == "acme.com"


# =============================================================================
# COMPANY NAME EXTRACTION TESTS
# =============================================================================

class TestCompanyNameExtraction:
    """Test company name extraction from signals."""
    
    def test_extract_from_at_pattern(self):
        """'at Company' pattern should extract name."""
        signal = make_signal("Senior Engineer at Acme Corp is needed")
        name = extract_company_name_from_signal(signal)
        assert name == "Acme Corp"
    
    def test_extract_from_hiring_pattern(self):
        """'Company is hiring' pattern should extract name."""
        signal = make_signal("TechStartup is hiring engineers!")
        name = extract_company_name_from_signal(signal)
        assert name == "TechStartup"
    
    def test_extract_from_join_pattern(self):
        """'Join Company' pattern should extract name."""
        signal = make_signal("Join Acme Labs as a developer")
        name = extract_company_name_from_signal(signal)
        assert name == "Acme Labs"
    
    def test_extract_from_url_slug(self):
        """Company slug from job board URL should work as fallback."""
        signal = make_signal(
            "We need an engineer!",  # No company name in text
            source_url="https://boards.greenhouse.io/super-startup/jobs/123"
        )
        name = extract_company_name_from_signal(signal)
        assert name == "Super Startup"
    
    def test_no_extraction_returns_none(self):
        """Unrecognizable text should return None."""
        signal = make_signal(
            "Looking for talent!",
            source_url="https://example.com/jobs"
        )
        name = extract_company_name_from_signal(signal)
        assert name is None


# =============================================================================
# DOMAIN EXTRACTION TESTS
# =============================================================================

class TestDomainExtraction:
    """Test domain extraction from signals."""
    
    def test_extract_explicit_domain(self):
        """Explicit domain in text should be extracted."""
        signal = make_signal("Apply at careers.acme.com or visit acme.com")
        domain = extract_domain_from_signal(signal)
        assert domain == "acme.com"
    
    def test_multiple_domains_returns_none(self):
        """Multiple domains = ambiguous = None."""
        signal = make_signal("Visit acme.com or partner.io for jobs")
        domain = extract_domain_from_signal(signal)
        assert domain is None  # Ambiguous
    
    def test_infer_from_url_slug(self):
        """Should infer domain from job board URL slug."""
        signal = make_signal(
            "We're hiring!",
            source_url="https://boards.greenhouse.io/acme/jobs/123"
        )
        domain = extract_domain_from_signal(signal)
        assert domain == "acme.com"


# =============================================================================
# AMBIGUITY DETECTION TESTS
# =============================================================================

class TestAmbiguityDetection:
    """Test ambiguity detection logic."""
    
    def test_unambiguous_signal_passes(self):
        """Clear signal should not be ambiguous."""
        signal = make_signal("Acme Corp is hiring engineers!")
        result = check_for_ambiguity(signal, "Acme Corp", "acme.com")
        assert result.is_ambiguous is False
    
    def test_multiple_domains_is_ambiguous(self):
        """Multiple company domains in text = ambiguous."""
        signal = make_signal("Jobs at acme.com and partner.io available")
        result = check_for_ambiguity(signal, "Acme", "acme.com")
        assert result.is_ambiguous is True
        assert "Multiple domains" in result.reason
    
    def test_generic_name_without_domain_is_ambiguous(self):
        """Generic company name without domain = ambiguous."""
        signal = make_signal("The Company is hiring!")
        result = check_for_ambiguity(signal, "Company", None)
        assert result.is_ambiguous is True
        assert "Generic company name" in result.reason


# =============================================================================
# ENTITY RESOLUTION TESTS
# =============================================================================

class TestEntityResolution:
    """Test full entity resolution pipeline."""
    
    def test_resolve_valid_signal(self):
        """Valid signal should resolve to Entity."""
        signal = make_signal(
            "Acme Corp is hiring a Senior Engineer!",
            source_url="https://boards.greenhouse.io/acme/jobs/123"
        )
        
        result = resolve_entity(signal)
        
        assert result.success is True
        assert result.entity is not None
        assert result.rejection is None
        
        # Entity should have correct values
        assert result.entity.get_name_value() == "Acme Corp"
        assert result.entity.get_domain_value() == "acme.com"
    
    def test_resolve_creates_evidence(self):
        """Resolved Entity must have Evidence for all fields."""
        signal = make_signal(
            "Join TechCo as an engineer! Visit techco.com",
            source_url="https://jobs.example.com/123"
        )
        
        result = resolve_entity(signal)
        assert result.success is True
        
        entity = result.entity
        
        # Check company_name Evidence
        assert entity.company_name.evidence_id.startswith("evt_")
        assert entity.company_name.evidence_type == EvidenceType.INF
        assert entity.company_name.field_name == "company_name"
        assert len(entity.company_name.meta.source_evidence_ids) > 0
        
        # Check domain Evidence
        assert entity.domain.evidence_id.startswith("evt_")
        assert entity.domain.evidence_type == EvidenceType.INF
        assert entity.domain.field_name == "domain"
    
    def test_reject_no_company_name(self):
        """Signal without extractable company name should be rejected."""
        signal = make_signal(
            "We need engineers!",
            source_url="https://example.com/jobs"
        )
        
        result = resolve_entity(signal)
        
        assert result.success is False
        assert result.rejection is not None
        assert result.rejection.rule == RejectionRule.R3_MISSING_ENTITY
        assert "company name" in result.rejection.reason.lower()
    
    def test_reject_invalid_domain(self):
        """Signal with personal email domain should be rejected.
        
        Note: gmail.com is filtered out during domain extraction as a 
        personal email domain, causing R3_MISSING_ENTITY rejection 
        (no valid domain could be extracted). This is correct behavior -
        the system rejects early rather than accepting a personal domain.
        """
        signal = make_signal(
            "Join Gmail.com team!",  # gmail.com is personal email domain
            source_url="https://example.com/jobs"
        )
        
        result = resolve_entity(signal)
        
        assert result.success is False
        assert result.rejection is not None
        # gmail.com is filtered during extraction → R3 (no domain found)
        assert result.rejection.rule == RejectionRule.R3_MISSING_ENTITY
    
    def test_reject_ambiguous_signal(self):
        """Ambiguous signal (multiple domains) should be rejected.
        
        Note: When multiple domains are found, extract_domain_from_signal
        returns None, causing a R3_MISSING_ENTITY rejection. This is correct
        fail-early behavior - we reject before the ambiguity check because
        we cannot determine which domain is the company.
        """
        signal = make_signal(
            "Jobs at acme.com and partner.io! Acme Corp is hiring!",
            source_url="https://example.com/jobs"
        )
        
        result = resolve_entity(signal)
        
        assert result.success is False
        assert result.rejection is not None
        # Multiple domains → domain extraction returns None → R3 rejection
        assert result.rejection.rule == RejectionRule.R3_MISSING_ENTITY


# =============================================================================
# EVIDENCE LINEAGE TESTS
# =============================================================================

class TestEvidenceLineage:
    """Test that Evidence lineage is properly preserved."""
    
    def test_entity_evidence_links_to_signal(self):
        """Entity Evidence should link back to Signal Evidence."""
        signal = make_signal(
            "Acme Corp is hiring engineers!",
            source_url="https://boards.greenhouse.io/acme/jobs/123"
        )
        
        result = resolve_entity(signal)
        assert result.success is True
        
        entity = result.entity
        
        # Get the source evidence ID from Entity
        company_source_ids = entity.company_name.meta.source_evidence_ids
        domain_source_ids = entity.domain.meta.source_evidence_ids
        
        # Source IDs should not be empty
        assert len(company_source_ids) > 0
        assert len(domain_source_ids) > 0
        
        # Source IDs should be valid Evidence IDs
        assert all(eid.startswith("evt_") for eid in company_source_ids)
        assert all(eid.startswith("evt_") for eid in domain_source_ids)
    
    def test_inference_rule_is_recorded(self):
        """Inference rule should be documented in Evidence."""
        signal = make_signal(
            "Acme Corp is hiring!",
            source_url="https://boards.greenhouse.io/acme/jobs/123"
        )
        
        result = resolve_entity(signal)
        assert result.success is True
        
        # Check that inference rules are recorded
        assert result.entity.company_name.meta.inference_rule is not None
        assert result.entity.domain.meta.inference_rule is not None


# =============================================================================
# BATCH RESOLUTION TESTS
# =============================================================================

class TestBatchResolution:
    """Test batch signal resolution."""
    
    def test_batch_resolves_valid_signals(self):
        """Batch should resolve valid signals."""
        signals = [
            make_signal(
                "Acme Corp is hiring!",
                source_url="https://boards.greenhouse.io/acme/jobs/1"
            ),
            make_signal(
                "TechCo is hiring engineers!",
                source_url="https://boards.greenhouse.io/techco/jobs/2"
            ),
        ]
        
        result = resolve_signals(signals)
        
        assert result.total_signals == 2
        assert len(result.resolved) == 2
        assert len(result.rejected) == 0
    
    def test_batch_handles_mixed_signals(self):
        """Batch should handle mix of valid and invalid signals."""
        signals = [
            make_signal(
                "Acme Corp is hiring!",
                source_url="https://boards.greenhouse.io/acme/jobs/1"
            ),
            make_signal(
                "We need help!",  # No company name
                source_url="https://example.com/jobs"
            ),
        ]
        
        result = resolve_signals(signals)
        
        assert result.total_signals == 2
        assert len(result.resolved) == 1
        assert len(result.rejected) == 1
    
    def test_batch_rejection_has_audit_trail(self):
        """Batch rejections should have full audit information."""
        signals = [
            make_signal(
                "Generic job post!",
                source_url="https://example.com/jobs"
            ),
        ]
        
        result = resolve_signals(signals)
        
        assert len(result.rejected) == 1
        rejection = result.rejected[0]
        
        assert rejection.rejection_id is not None
        assert rejection.rule is not None
        assert rejection.reason is not None
        assert rejection.timestamp is not None


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
