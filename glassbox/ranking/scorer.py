"""
Lead Scorer for GlassBox Discovery Engine.

Phase 4: Deterministic lead ranking with full explainability.

Core principle:
    Every score must be decomposable into human-readable reasons.
    If a score cannot be explained line-by-line, it must not exist.

Score composition:
    Final score = sum of component contributions
    No normalization tricks. No statistical smoothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..domain import Entity, Lead, Signal
from .components import (
    ComponentScore,
    compute_intent_strength,
    compute_signal_freshness,
    compute_evidence_confidence,
    compute_entity_completeness,
    compute_noise_penalty,
)


# =============================================================================
# LEAD TIER (Deterministic, Threshold-Based)
# =============================================================================

class LeadTier(Enum):
    """
    Coarse lead tiers for quick prioritization.
    
    Thresholds are fixed and transparent:
    - TIER_A: score >= 60 (high priority)
    - TIER_B: score >= 40 (medium priority)
    - TIER_C: score >= 20 (low priority)
    - TIER_D: score < 20 (very low priority)
    """
    TIER_A = "A"
    TIER_B = "B"
    TIER_C = "C"
    TIER_D = "D"


def compute_tier(score: float) -> LeadTier:
    """
    Assign tier based on fixed score thresholds.
    
    No hidden logic. No tuning knobs.
    """
    if score >= 60:
        return LeadTier.TIER_A
    elif score >= 40:
        return LeadTier.TIER_B
    elif score >= 20:
        return LeadTier.TIER_C
    else:
        return LeadTier.TIER_D


# =============================================================================
# SCORE BREAKDOWN
# =============================================================================

@dataclass
class ScoreBreakdown:
    """
    Complete score decomposition for a lead.
    
    Exposes:
    - All component scores
    - Final total
    - Assigned tier
    - All evidence references
    """
    intent_strength: ComponentScore
    signal_freshness: ComponentScore
    evidence_confidence: ComponentScore
    entity_completeness: ComponentScore
    noise_penalty: ComponentScore
    
    @property
    def total_score(self) -> float:
        """Sum of all component contributions."""
        return (
            self.intent_strength.contribution +
            self.signal_freshness.contribution +
            self.evidence_confidence.contribution +
            self.entity_completeness.contribution +
            self.noise_penalty.contribution
        )
    
    @property
    def tier(self) -> LeadTier:
        """Tier based on total score."""
        return compute_tier(self.total_score)
    
    @property
    def all_evidence_ids(self) -> list[str]:
        """All Evidence IDs across all components."""
        ids = set()
        for component in self.components:
            ids.update(component.evidence_ids)
        return list(ids)
    
    @property
    def components(self) -> list[ComponentScore]:
        """List of all component scores."""
        return [
            self.intent_strength,
            self.signal_freshness,
            self.evidence_confidence,
            self.entity_completeness,
            self.noise_penalty,
        ]
    
    def get_positive_contributors(self) -> list[ComponentScore]:
        """Components that added to the score."""
        return [c for c in self.components if c.contribution > 0]
    
    def get_negative_contributors(self) -> list[ComponentScore]:
        """Components that reduced the score."""
        return [c for c in self.components if c.contribution < 0]


# =============================================================================
# RANKED LEAD
# =============================================================================

@dataclass
class RankedLead:
    """
    A lead with its ranking information.
    
    Contains:
    - Original Entity
    - Score breakdown (fully transparent)
    - Plain-English explanation
    """
    entity: Entity
    breakdown: ScoreBreakdown
    signal: Optional[Signal] = None
    
    @property
    def score(self) -> float:
        return self.breakdown.total_score
    
    @property
    def tier(self) -> LeadTier:
        return self.breakdown.tier
    
    def get_explanation(self) -> str:
        """
        Generate plain-English explanation of the ranking.
        
        This is a VIEW, not indexed truth.
        """
        return generate_explanation(self.entity, self.breakdown)


# =============================================================================
# SCORER
# =============================================================================

def score_lead(
    entity: Entity,
    signal: Optional[Signal] = None,
    reference_time: Optional[datetime] = None,
) -> RankedLead:
    """
    Score a lead and produce a full ranking.
    
    This is the main entry point for Phase 4.
    
    Args:
        entity: A validated Entity from Phase 2/3
        signal: Optional original Signal for intent/freshness analysis
        reference_time: Optional time reference (defaults to now)
    
    Returns:
        RankedLead with complete score breakdown and explanation
    """
    # Compute all components
    intent = compute_intent_strength(signal=signal)
    freshness = compute_signal_freshness(signal=signal, reference_time=reference_time)
    confidence = compute_evidence_confidence(entity)
    completeness = compute_entity_completeness(entity)
    noise = compute_noise_penalty(signal=signal)
    
    # Compose breakdown
    breakdown = ScoreBreakdown(
        intent_strength=intent,
        signal_freshness=freshness,
        evidence_confidence=confidence,
        entity_completeness=completeness,
        noise_penalty=noise,
    )
    
    return RankedLead(
        entity=entity,
        breakdown=breakdown,
        signal=signal,
    )


def score_leads(
    entities: list[Entity],
    signals: Optional[list[Signal]] = None,
    reference_time: Optional[datetime] = None,
) -> list[RankedLead]:
    """
    Score and rank multiple leads.
    
    Returns leads sorted by score (highest first).
    """
    ranked: list[RankedLead] = []
    
    for i, entity in enumerate(entities):
        signal = signals[i] if signals and i < len(signals) else None
        ranked_lead = score_lead(entity, signal, reference_time)
        ranked.append(ranked_lead)
    
    # Sort by score descending
    ranked.sort(key=lambda x: x.score, reverse=True)
    
    return ranked


# =============================================================================
# EXPLANATION GENERATION
# =============================================================================

def generate_explanation(entity: Entity, breakdown: ScoreBreakdown) -> str:
    """
    Generate a plain-English explanation of the ranking.
    
    This answers: "Why is this lead ranked this way?"
    """
    company_name = entity.get_name_value()
    score = breakdown.total_score
    tier = breakdown.tier.value
    
    # Build explanation
    lines = [
        f"**{company_name}** is ranked as Tier {tier} with a score of {score:.0f}/95.",
        "",
        "**Score Breakdown:**",
    ]
    
    # Add each component
    for component in breakdown.components:
        sign = "+" if component.contribution >= 0 else ""
        lines.append(f"- {component.reason}")
    
    # Summary statement
    positive = breakdown.get_positive_contributors()
    negative = breakdown.get_negative_contributors()
    
    lines.append("")
    
    if breakdown.tier == LeadTier.TIER_A:
        lines.append("**Summary:** This is a high-priority lead with strong signals.")
    elif breakdown.tier == LeadTier.TIER_B:
        lines.append("**Summary:** This is a medium-priority lead worth following up on.")
    elif breakdown.tier == LeadTier.TIER_C:
        lines.append("**Summary:** This is a lower-priority lead with some potential.")
    else:
        lines.append("**Summary:** This lead has weak signals and should be deprioritized.")
    
    if negative:
        lines.append("")
        lines.append("**Concerns:** " + "; ".join(c.reason for c in negative))
    
    return "\n".join(lines)


def generate_short_explanation(breakdown: ScoreBreakdown) -> str:
    """
    Generate a one-line explanation for quick scanning.
    """
    score = breakdown.total_score
    tier = breakdown.tier.value
    
    # Find the strongest contributor
    components = breakdown.get_positive_contributors()
    if components:
        strongest = max(components, key=lambda c: c.contribution)
        return f"Tier {tier} ({score:.0f} pts) — {strongest.reason}"
    else:
        return f"Tier {tier} ({score:.0f} pts) — No strong signals detected"
