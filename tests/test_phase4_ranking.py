"""
Tests for Phase 4: Deterministic Lead Ranking.

These tests verify:
1. Deterministic scoring (same input → same score)
2. Component isolation (each component affects score independently)
3. Explanation correctness
4. Ranking stability
5. Proof that no Evidence → no score component
"""

import pytest
from datetime import datetime, timedelta

from glassbox.domain import Entity, Signal
from glassbox.evidence import create_inference
from glassbox.validation import create_signal_id, create_dedup_hash
from glassbox.ranking.components import (
    ComponentScore,
    compute_intent_strength,
    compute_signal_freshness,
    compute_evidence_confidence,
    compute_entity_completeness,
    compute_noise_penalty,
)
from glassbox.ranking.scorer import (
    LeadTier,
    compute_tier,
    score_lead,
    score_leads,
    ScoreBreakdown,
    RankedLead,
    generate_explanation,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

def make_signal(
    raw_text: str,
    source_url: str = "https://boards.greenhouse.io/acme/jobs/123",
    days_ago: int = 0,
) -> Signal:
    """Helper to create a Signal for testing."""
    timestamp = datetime.utcnow() - timedelta(days=days_ago)
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
    with_industry: bool = False,
    with_size: bool = False,
    confidence: float = 0.75,
) -> Entity:
    """Helper to create an Entity for testing."""
    company_evidence = create_inference(
        field_name="company_name",
        value=company_name,
        source_evidence_ids=["evt_test_signal"],
        inference_rule="test_extraction",
        confidence=confidence,
    )
    domain_evidence = create_inference(
        field_name="domain",
        value=domain,
        source_evidence_ids=["evt_test_signal"],
        inference_rule="test_extraction",
        confidence=confidence,
    )
    
    entity = Entity(
        company_name=company_evidence,
        domain=domain_evidence,
    )
    
    if with_industry:
        entity.industry = create_inference(
            field_name="industry",
            value="technology",
            source_evidence_ids=["evt_test_signal"],
            inference_rule="keyword_mapping",
            confidence=0.70,
        )
    
    if with_size:
        entity.size_estimate = create_inference(
            field_name="company_size_range",
            value="startup",
            source_evidence_ids=["evt_test_signal"],
            inference_rule="signal_heuristics",
            confidence=0.65,
        )
    
    return entity


# =============================================================================
# INTENT STRENGTH TESTS
# =============================================================================

class TestIntentStrength:
    """Test intent strength component."""
    
    def test_hiring_signal_high_score(self):
        """Hiring signals should get 40 points."""
        signal = make_signal("We're hiring a Senior Engineer!")
        score = compute_intent_strength(signal=signal)
        
        assert score.contribution == 40
        assert "hiring" in score.reason.lower()
    
    def test_funding_signal_medium_score(self):
        """Funding signals should get 30 points."""
        signal = make_signal("Company raised $10 million in Series A funding")
        score = compute_intent_strength(signal=signal)
        
        assert score.contribution == 30
        assert "funding" in score.reason.lower()
    
    def test_no_signal_zero_score(self):
        """No signal should get 0 points."""
        score = compute_intent_strength(signal=None)
        
        assert score.contribution == 0
        assert len(score.evidence_ids) == 0


# =============================================================================
# SIGNAL FRESHNESS TESTS
# =============================================================================

class TestSignalFreshness:
    """Test signal freshness component."""
    
    def test_fresh_signal_high_score(self):
        """Signal from today should get 25 points."""
        signal = make_signal("Hiring now!", days_ago=0)
        score = compute_signal_freshness(signal=signal)
        
        assert score.contribution == 25
        assert "fresh" in score.reason.lower()
    
    def test_week_old_signal_medium_score(self):
        """Week-old signal should get 20 points."""
        signal = make_signal("Hiring now!", days_ago=5)
        score = compute_signal_freshness(signal=signal)
        
        assert score.contribution == 20
    
    def test_old_signal_low_score(self):
        """25-day old signal should get 5 points."""
        signal = make_signal("Hiring now!", days_ago=25)
        score = compute_signal_freshness(signal=signal)
        
        assert score.contribution == 5
    
    def test_stale_signal_zero_score(self):
        """Signal older than 30 days should get 0 points."""
        signal = make_signal("Hiring now!", days_ago=35)
        score = compute_signal_freshness(signal=signal)
        
        assert score.contribution == 0
        assert "stale" in score.reason.lower()


# =============================================================================
# EVIDENCE CONFIDENCE TESTS
# =============================================================================

class TestEvidenceConfidence:
    """Test evidence confidence component."""
    
    def test_high_confidence_high_score(self):
        """High confidence (0.85) should get 20 points."""
        entity = make_entity(confidence=0.85)
        score = compute_evidence_confidence(entity)
        
        assert score.contribution == 20
        assert "high" in score.reason.lower()
    
    def test_medium_confidence_medium_score(self):
        """Medium confidence (0.65) should get 15 points."""
        entity = make_entity(confidence=0.65)
        score = compute_evidence_confidence(entity)
        
        assert score.contribution == 15
    
    def test_low_confidence_low_score(self):
        """Low confidence (0.35) should get 5 points (Low tier: 0.2-0.4)."""
        entity = make_entity(confidence=0.35)
        score = compute_evidence_confidence(entity)
        
        # 0.35 is in range [0.2, 0.4) which is "Low" = 5 points
        assert score.contribution == 5


# =============================================================================
# ENTITY COMPLETENESS TESTS
# =============================================================================

class TestEntityCompleteness:
    """Test entity completeness component."""
    
    def test_base_entity_base_score(self):
        """Entity with only required fields should get 5 points."""
        entity = make_entity()
        score = compute_entity_completeness(entity)
        
        assert score.contribution == 5
        assert "company_name" in score.reason
        assert "domain" in score.reason
    
    def test_enriched_entity_higher_score(self):
        """Entity with enriched fields should get more points."""
        entity = make_entity(with_industry=True, with_size=True)
        score = compute_entity_completeness(entity)
        
        assert score.contribution == 10  # 5 + 3 + 2
        assert "industry" in score.reason
        assert "size_estimate" in score.reason


# =============================================================================
# NOISE PENALTY TESTS
# =============================================================================

class TestNoisePenalty:
    """Test noise penalty component."""
    
    def test_clean_signal_no_penalty(self):
        """Signal without uncertainty markers should have no penalty."""
        signal = make_signal("We are hiring a Senior Engineer!")
        score = compute_noise_penalty(signal=signal)
        
        assert score.contribution == 0
        assert "clean" in score.reason.lower()
    
    def test_uncertain_signal_penalty(self):
        """Signal with uncertainty markers should be penalized."""
        signal = make_signal("We might possibly be hiring maybe")
        score = compute_noise_penalty(signal=signal)
        
        assert score.contribution < 0
        assert "uncertainty" in score.reason.lower()


# =============================================================================
# SCORE COMPOSITION TESTS
# =============================================================================

class TestScoreComposition:
    """Test full score composition."""
    
    def test_deterministic_scoring(self):
        """Same input should produce same score every time."""
        entity = make_entity()
        signal = make_signal("Hiring a developer!")
        
        score1 = score_lead(entity, signal)
        score2 = score_lead(entity, signal)
        
        assert score1.score == score2.score
    
    def test_total_score_is_sum(self):
        """Total score should be sum of components."""
        entity = make_entity()
        signal = make_signal("Hiring a developer!")
        
        ranked = score_lead(entity, signal)
        
        expected = sum(c.contribution for c in ranked.breakdown.components)
        assert ranked.score == expected
    
    def test_components_are_independent(self):
        """Each component should be independently computable."""
        entity = make_entity()
        signal = make_signal("Hiring a developer!")
        
        ranked = score_lead(entity, signal)
        
        # All 5 components should be present
        assert len(ranked.breakdown.components) == 5
        
        # Each component has a name and reason
        for component in ranked.breakdown.components:
            assert component.name is not None
            assert component.reason is not None


# =============================================================================
# TIER ASSIGNMENT TESTS
# =============================================================================

class TestTierAssignment:
    """Test tier assignment based on score."""
    
    def test_tier_a_threshold(self):
        """Score >= 60 should be Tier A."""
        assert compute_tier(60) == LeadTier.TIER_A
        assert compute_tier(80) == LeadTier.TIER_A
    
    def test_tier_b_threshold(self):
        """Score 40-59 should be Tier B."""
        assert compute_tier(40) == LeadTier.TIER_B
        assert compute_tier(59) == LeadTier.TIER_B
    
    def test_tier_c_threshold(self):
        """Score 20-39 should be Tier C."""
        assert compute_tier(20) == LeadTier.TIER_C
        assert compute_tier(39) == LeadTier.TIER_C
    
    def test_tier_d_threshold(self):
        """Score < 20 should be Tier D."""
        assert compute_tier(19) == LeadTier.TIER_D
        assert compute_tier(0) == LeadTier.TIER_D


# =============================================================================
# EXPLANATION TESTS
# =============================================================================

class TestExplanation:
    """Test explanation generation."""
    
    def test_explanation_contains_score(self):
        """Explanation should contain the score."""
        entity = make_entity("TechCo", "techco.com")
        signal = make_signal("TechCo is hiring engineers!")
        
        ranked = score_lead(entity, signal)
        explanation = ranked.get_explanation()
        
        assert str(int(ranked.score)) in explanation
    
    def test_explanation_contains_tier(self):
        """Explanation should contain the tier."""
        entity = make_entity("TechCo", "techco.com")
        signal = make_signal("TechCo is hiring engineers!")
        
        ranked = score_lead(entity, signal)
        explanation = ranked.get_explanation()
        
        assert ranked.tier.value in explanation
    
    def test_explanation_contains_reasons(self):
        """Explanation should contain component reasons."""
        entity = make_entity("TechCo", "techco.com")
        signal = make_signal("TechCo is hiring engineers!")
        
        ranked = score_lead(entity, signal)
        explanation = ranked.get_explanation()
        
        # Should have score breakdown section
        assert "Score Breakdown" in explanation or "Breakdown" in explanation


# =============================================================================
# RANKING STABILITY TESTS
# =============================================================================

class TestRankingStability:
    """Test that ranking is stable and deterministic."""
    
    def test_batch_ranking_sorted(self):
        """Batch ranking should return sorted results."""
        entities = [
            make_entity("Co1", "co1.com"),
            make_entity("Co2", "co2.com"),
            make_entity("Co3", "co3.com"),
        ]
        signals = [
            make_signal("Regular update", days_ago=20),  # Low score
            make_signal("We're hiring engineers!", days_ago=0),  # High score
            make_signal("Company news", days_ago=10),  # Medium score
        ]
        
        ranked = score_leads(entities, signals)
        
        # Should be sorted by score descending
        scores = [r.score for r in ranked]
        assert scores == sorted(scores, reverse=True)
    
    def test_same_order_every_time(self):
        """Ranking order should be consistent."""
        entities = [
            make_entity("Co1", "co1.com"),
            make_entity("Co2", "co2.com"),
        ]
        signals = [
            make_signal("Hiring now!", days_ago=0),
            make_signal("Maybe hiring", days_ago=5),
        ]
        
        ranked1 = score_leads(entities, signals)
        ranked2 = score_leads(entities, signals)
        
        names1 = [r.entity.get_name_value() for r in ranked1]
        names2 = [r.entity.get_name_value() for r in ranked2]
        
        assert names1 == names2


# =============================================================================
# NO EVIDENCE → NO SCORE TESTS
# =============================================================================

class TestNoEvidenceNoScore:
    """Prove that no Evidence means no score component."""
    
    def test_no_signal_means_no_intent_score(self):
        """Without signal, intent strength should be 0."""
        score = compute_intent_strength(signal=None)
        
        assert score.contribution == 0
        assert len(score.evidence_ids) == 0
    
    def test_no_signal_means_no_freshness_score(self):
        """Without signal, freshness should be 0."""
        score = compute_signal_freshness(signal=None)
        
        assert score.contribution == 0
        assert len(score.evidence_ids) == 0
    
    def test_component_has_evidence_refs(self):
        """Score component should reference its Evidence."""
        entity = make_entity()
        signal = make_signal("Hiring developers!")
        
        intent_score = compute_intent_strength(signal=signal)
        
        # Should have evidence reference
        assert len(intent_score.evidence_ids) > 0
        assert signal.signal_id in intent_score.evidence_ids


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
