"""
Tests for GlassBox Discovery Engine — Phase 0 Foundation.

These tests verify that:
1. Evidence Ledger invariants are enforced
2. Invalid data cannot enter the system
3. Rejections are explicit and auditable
"""

import pytest
from datetime import datetime, timedelta

from glassbox.evidence import (
    Evidence,
    EvidenceMeta,
    EvidenceType,
    EvidenceValidationError,
    create_observation,
    create_inference,
    create_api_evidence,
    BASE_CONFIDENCE,
)
from glassbox.domain import (
    Entity,
    Lead,
    Rejection,
    RejectionError,
    RejectionRule,
    Signal,
    Tier,
)
from glassbox.validation import (
    gate_signal,
    validate_signal_freshness,
    validate_intent_signal_present,
    validate_domain_resolvable,
    validate_llm_json_output,
    LLMExtractionResult,
    MIN_CONFIDENCE_THRESHOLD,
)


# =============================================================================
# EVIDENCE INVARIANT TESTS
# =============================================================================

class TestEvidenceInvariants:
    """Test that Evidence Ledger invariants are enforced."""
    
    def test_evidence_requires_id(self):
        """Evidence without evidence_id must be rejected."""
        with pytest.raises(EvidenceValidationError, match="evidence_id is required"):
            Evidence(
                evidence_id="",  # Empty ID
                field_name="test",
                value="test_value",
                evidence_type=EvidenceType.OBS,
                meta=EvidenceMeta(
                    timestamp=datetime.utcnow(),
                    confidence=0.95,
                    source_url="https://example.com",
                    extraction_method="test",
                ),
            )
    
    def test_evidence_requires_valid_confidence(self):
        """Confidence must be in [0.0, 1.0]."""
        with pytest.raises(EvidenceValidationError, match="confidence must be in"):
            Evidence(
                evidence_id="evt_test",
                field_name="test",
                value="test_value",
                evidence_type=EvidenceType.OBS,
                meta=EvidenceMeta(
                    timestamp=datetime.utcnow(),
                    confidence=1.5,  # Invalid: > 1.0
                    source_url="https://example.com",
                    extraction_method="test",
                ),
            )
    
    def test_obs_requires_source_url(self):
        """OBS evidence must have source_url."""
        with pytest.raises(EvidenceValidationError, match="source_url"):
            Evidence(
                evidence_id="evt_test",
                field_name="test",
                value="test_value",
                evidence_type=EvidenceType.OBS,
                meta=EvidenceMeta(
                    timestamp=datetime.utcnow(),
                    confidence=0.95,
                    source_url=None,  # Missing
                    extraction_method="test",
                ),
            )
    
    def test_inf_requires_source_evidence_ids(self):
        """INF evidence must have source_evidence_ids."""
        with pytest.raises(EvidenceValidationError, match="source_evidence_ids"):
            Evidence(
                evidence_id="evt_test",
                field_name="test",
                value="test_value",
                evidence_type=EvidenceType.INF,
                meta=EvidenceMeta(
                    timestamp=datetime.utcnow(),
                    confidence=0.70,
                    source_evidence_ids=(),  # Empty
                    inference_rule="test_rule",
                ),
            )
    
    def test_api_requires_provider_name(self):
        """API evidence must have provider_name."""
        with pytest.raises(EvidenceValidationError, match="provider_name"):
            Evidence(
                evidence_id="evt_test",
                field_name="test",
                value="test_value",
                evidence_type=EvidenceType.API,
                meta=EvidenceMeta(
                    timestamp=datetime.utcnow(),
                    confidence=0.85,
                    provider_name=None,  # Missing
                    api_response_id="resp_123",
                ),
            )
    
    def test_valid_observation_passes(self):
        """Valid OBS evidence should pass validation."""
        evidence = create_observation(
            field_name="intent_signal",
            value="Hiring Head of Engineering",
            source_url="https://greenhouse.io/acme/jobs/123",
            extraction_method="rss_parse",
        )
        assert evidence.evidence_id.startswith("evt_")
        assert evidence.evidence_type == EvidenceType.OBS
        assert evidence.meta.confidence == BASE_CONFIDENCE[EvidenceType.OBS]
    
    def test_valid_inference_passes(self):
        """Valid INF evidence should pass validation."""
        evidence = create_inference(
            field_name="contact_email",
            value="jane@acme.com",
            source_evidence_ids=["evt_abc123"],
            inference_rule="email_permutation_first_at_domain",
        )
        assert evidence.evidence_type == EvidenceType.INF
        assert evidence.meta.confidence == BASE_CONFIDENCE[EvidenceType.INF]


# =============================================================================
# CONFIDENCE DECAY TESTS
# =============================================================================

class TestConfidenceDecay:
    """Test that confidence decays correctly over time."""
    
    def test_intent_signal_decays(self):
        """Intent signal should decay -0.25 per 7 days."""
        old_timestamp = datetime.utcnow() - timedelta(days=14)
        evidence = create_observation(
            field_name="intent_signal",
            value="Hiring",
            source_url="https://example.com",
            extraction_method="test",
            timestamp=old_timestamp,
        )
        
        current_confidence = evidence.calculate_current_confidence()
        expected = 0.95 - (2 * 0.25)  # 14 days = 2 decay periods
        assert current_confidence == expected
    
    def test_company_name_no_decay(self):
        """Company name should not decay."""
        old_timestamp = datetime.utcnow() - timedelta(days=365)
        evidence = create_observation(
            field_name="company_name",
            value="Acme Corp",
            source_url="https://example.com",
            extraction_method="test",
            timestamp=old_timestamp,
        )
        
        current_confidence = evidence.calculate_current_confidence()
        assert current_confidence == 0.95  # No decay
    
    def test_stale_signal_detected(self):
        """Signal older than 28 days should be stale."""
        old_timestamp = datetime.utcnow() - timedelta(days=30)
        evidence = create_observation(
            field_name="intent_signal",
            value="Hiring",
            source_url="https://example.com",
            extraction_method="test",
            timestamp=old_timestamp,
        )
        
        assert evidence.is_stale()


# =============================================================================
# REJECTION LOGIC TESTS
# =============================================================================

class TestRejectionLogic:
    """Test that hard rejection rules are enforced."""
    
    def test_reject_stale_signal(self):
        """Signals older than 30 days must be rejected (R2)."""
        old_timestamp = datetime.utcnow() - timedelta(days=35)
        
        with pytest.raises(RejectionError) as exc_info:
            validate_signal_freshness(old_timestamp, signal_id="sig_test")
        
        assert exc_info.value.rule == RejectionRule.R2_STALE_SIGNAL
    
    def test_reject_no_intent_signal(self):
        """Text without intent keywords must be rejected (R1)."""
        boring_text = "This is just a regular blog post about nothing."
        
        with pytest.raises(RejectionError) as exc_info:
            validate_intent_signal_present(boring_text, signal_id="sig_test")
        
        assert exc_info.value.rule == RejectionRule.R1_NO_INTENT_SIGNAL
    
    def test_accept_hiring_signal(self):
        """Text with hiring keywords should be accepted."""
        hiring_text = "We're hiring a Senior Engineer to join our team!"
        
        from glassbox.domain import IntentType
        intent = validate_intent_signal_present(hiring_text)
        assert intent == IntentType.HIRING
    
    def test_reject_invalid_domain(self):
        """Invalid domains must be rejected (R4)."""
        with pytest.raises(RejectionError) as exc_info:
            validate_domain_resolvable("not a domain")
        
        assert exc_info.value.rule == RejectionRule.R4_INVALID_DOMAIN
    
    def test_accept_valid_domain(self):
        """Valid domains should pass."""
        validate_domain_resolvable("acme.com")  # Should not raise


# =============================================================================
# LLM OUTPUT VALIDATION TESTS
# =============================================================================

class TestLLMValidation:
    """Test LLM output validation."""
    
    def test_reject_low_confidence(self):
        """LLM confidence below threshold must be rejected (R7)."""
        json_output = {
            "company_name": "Acme",
            "domain": "acme.com",
            "intent_type": "hiring",
            "confidence": 0.5,  # Below 0.8 threshold
        }
        
        with pytest.raises(RejectionError) as exc_info:
            validate_llm_json_output(json_output)
        
        assert exc_info.value.rule == RejectionRule.R7_LLM_FAILURE
    
    def test_reject_missing_field(self):
        """Missing required fields must be rejected (R7)."""
        json_output = {
            "company_name": "Acme",
            # Missing domain, intent_type, confidence
        }
        
        with pytest.raises(RejectionError) as exc_info:
            validate_llm_json_output(json_output)
        
        assert exc_info.value.rule == RejectionRule.R7_LLM_FAILURE
    
    def test_accept_valid_output(self):
        """Valid LLM output should pass."""
        json_output = {
            "company_name": "Acme Corp",
            "domain": "acme.com",
            "intent_type": "hiring",
            "confidence": 0.92,
        }
        
        result = validate_llm_json_output(json_output)
        assert result.company_name == "Acme Corp"
        assert result.confidence == 0.92


# =============================================================================
# DOMAIN OBJECT TESTS
# =============================================================================

class TestDomainObjects:
    """Test domain objects enforce Evidence requirements."""
    
    def test_lead_requires_evidence(self):
        """Lead without required Evidence must be rejected."""
        with pytest.raises(RejectionError) as exc_info:
            Lead(
                company_name=None,  # Missing required evidence
                domain=None,
                intent_signal=None,
            )
        
        assert exc_info.value.rule == RejectionRule.R8_MISSING_EVIDENCE
    
    def test_lead_rejects_stale_intent(self):
        """Lead with stale intent signal must be rejected."""
        old_timestamp = datetime.utcnow() - timedelta(days=35)
        
        company = create_observation(
            field_name="company_name",
            value="Acme",
            source_url="https://example.com",
            extraction_method="test",
        )
        domain = create_observation(
            field_name="domain",
            value="acme.com",
            source_url="https://example.com",
            extraction_method="test",
        )
        intent = create_observation(
            field_name="intent_signal",
            value="Hiring",
            source_url="https://example.com",
            extraction_method="test",
            timestamp=old_timestamp,
        )
        
        with pytest.raises(RejectionError) as exc_info:
            Lead(company_name=company, domain=domain, intent_signal=intent)
        
        assert exc_info.value.rule == RejectionRule.R2_STALE_SIGNAL
    
    def test_valid_lead_computes_tier(self):
        """Valid lead should compute correct tier."""
        company = create_observation(
            field_name="company_name",
            value="Acme",
            source_url="https://example.com",
            extraction_method="test",
        )
        domain = create_observation(
            field_name="domain",
            value="acme.com",
            source_url="https://example.com",
            extraction_method="test",
        )
        intent = create_observation(
            field_name="intent_signal",
            value="Hiring Engineer",
            source_url="https://greenhouse.io/jobs/123",
            extraction_method="rss",
        )
        
        lead = Lead(company_name=company, domain=domain, intent_signal=intent)
        assert lead.tier == Tier.TIER_3  # Hiring only


# =============================================================================
# GATING INTEGRATION TESTS
# =============================================================================

class TestGating:
    """Test full gating pipeline."""
    
    def test_gate_accepts_valid_signal(self):
        """Valid signal should pass gating."""
        result = gate_signal(
            source_url="https://greenhouse.io/acme/jobs/123",
            raw_text="We're hiring a Senior Software Engineer!",
            timestamp=datetime.utcnow(),
            source_type="rss_greenhouse",
        )
        
        assert result.accepted is True
        assert result.signal is not None
        assert result.rejection is None
    
    def test_gate_rejects_stale_signal(self):
        """Stale signal should be rejected with audit trail."""
        result = gate_signal(
            source_url="https://greenhouse.io/acme/jobs/123",
            raw_text="We're hiring a Senior Software Engineer!",
            timestamp=datetime.utcnow() - timedelta(days=45),
            source_type="rss_greenhouse",
        )
        
        assert result.accepted is False
        assert result.signal is None
        assert result.rejection is not None
        assert result.rejection.rule == RejectionRule.R2_STALE_SIGNAL
    
    def test_gate_rejects_no_intent(self):
        """Signal without intent should be rejected."""
        result = gate_signal(
            source_url="https://blog.acme.com/post/123",
            raw_text="Here's our annual company picnic photos!",
            timestamp=datetime.utcnow(),
            source_type="rss_blog",
        )
        
        assert result.accepted is False
        assert result.rejection.rule == RejectionRule.R1_NO_INTENT_SIGNAL


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
