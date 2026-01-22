"""
Scoring Components for GlassBox Discovery Engine.

Phase 4: Each component is independently computable with no hidden weights.

Components:
    - Intent Strength: Type of signal (hiring > funding > announcement)
    - Signal Freshness: Time decay from Evidence metadata
    - Evidence Confidence: Aggregated, conservative
    - Entity Completeness: How many core fields are known
    - Noise Penalty: Weak, vague, or borderline signals
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from ..domain import Entity, Lead, Signal, IntentType
from ..evidence import Evidence


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_entity_evidence(entity: Entity) -> list[Evidence]:
    """
    Extract all Evidence objects from an Entity.
    
    This is a standalone function to avoid modifying Phase 0 domain.py.
    """
    evidence_list = [entity.company_name, entity.domain]
    if entity.industry:
        evidence_list.append(entity.industry)
    if entity.size_estimate:
        evidence_list.append(entity.size_estimate)
    return evidence_list


# =============================================================================
# COMPONENT SCORES (Deterministic, No Hidden Weights)
# =============================================================================

@dataclass
class ComponentScore:
    """
    A single scoring component with full transparency.
    
    Every component exposes:
    - name: What this component measures
    - raw_value: The underlying measurement
    - contribution: Points added to final score
    - evidence_ids: Which Evidence objects support this
    - reason: Human-readable explanation
    """
    name: str
    raw_value: float
    contribution: float
    evidence_ids: list[str]
    reason: str


# =============================================================================
# INTENT STRENGTH COMPONENT
# =============================================================================

# Intent type to score mapping (hiring is strongest signal)
INTENT_STRENGTH_SCORES = {
    IntentType.HIRING: 40,
    IntentType.FUNDING: 30,
    IntentType.EXECUTIVE_CHANGE: 20,
}


def compute_intent_strength(
    signal: Optional[Signal] = None,
    lead: Optional[Lead] = None,
) -> ComponentScore:
    """
    Compute intent strength based on signal type.
    
    Hiring signals are the strongest indicator of need.
    Funding signals suggest growth and budget.
    Executive changes may indicate new initiatives.
    
    Returns: ComponentScore with 0-40 points
    """
    if signal is None and lead is None:
        return ComponentScore(
            name="intent_strength",
            raw_value=0.0,
            contribution=0.0,
            evidence_ids=[],
            reason="No signal data available for intent analysis",
        )
    
    # Detect intent type from signal text
    text = signal.raw_text.lower() if signal else ""
    
    intent_type = None
    evidence_ids = []
    
    if signal:
        evidence_ids = [signal.signal_id]
    
    # Check for hiring intent (highest priority)
    hiring_keywords = ["hiring", "job", "career", "position", "engineer", "developer", "role", "join"]
    if any(kw in text for kw in hiring_keywords):
        intent_type = IntentType.HIRING
    
    # Check for funding intent
    elif any(kw in text for kw in ["funding", "raised", "series", "investment", "million"]):
        intent_type = IntentType.FUNDING
    
    # Check for executive change
    elif any(kw in text for kw in ["ceo", "cto", "executive", "appointed", "leadership"]):
        intent_type = IntentType.EXECUTIVE_CHANGE
    
    if intent_type:
        score = INTENT_STRENGTH_SCORES.get(intent_type, 10)
        return ComponentScore(
            name="intent_strength",
            raw_value=float(score),
            contribution=float(score),
            evidence_ids=evidence_ids,
            reason=f"Detected {intent_type.value} intent signal (+{score} points)",
        )
    
    return ComponentScore(
        name="intent_strength",
        raw_value=0.0,
        contribution=0.0,
        evidence_ids=evidence_ids,
        reason="No clear intent signal detected",
    )


# =============================================================================
# SIGNAL FRESHNESS COMPONENT
# =============================================================================

def compute_signal_freshness(
    signal: Optional[Signal] = None,
    reference_time: Optional[datetime] = None,
) -> ComponentScore:
    """
    Compute freshness score based on signal age.
    
    Fresher signals are more valuable:
    - 0-3 days: +25 points
    - 4-7 days: +20 points
    - 8-14 days: +15 points
    - 15-21 days: +10 points
    - 22-30 days: +5 points
    - >30 days: 0 points
    
    Returns: ComponentScore with 0-25 points
    """
    if signal is None:
        return ComponentScore(
            name="signal_freshness",
            raw_value=0.0,
            contribution=0.0,
            evidence_ids=[],
            reason="No signal timestamp available",
        )
    
    if reference_time is None:
        reference_time = datetime.utcnow()
    
    age = reference_time - signal.timestamp
    days_old = age.days
    
    evidence_ids = [signal.signal_id]
    
    if days_old <= 3:
        score = 25
        reason = f"Very fresh signal ({days_old} days old)"
    elif days_old <= 7:
        score = 20
        reason = f"Fresh signal ({days_old} days old)"
    elif days_old <= 14:
        score = 15
        reason = f"Recent signal ({days_old} days old)"
    elif days_old <= 21:
        score = 10
        reason = f"Aging signal ({days_old} days old)"
    elif days_old <= 30:
        score = 5
        reason = f"Old signal ({days_old} days old)"
    else:
        score = 0
        reason = f"Stale signal ({days_old} days old, no freshness bonus)"
    
    return ComponentScore(
        name="signal_freshness",
        raw_value=float(days_old),
        contribution=float(score),
        evidence_ids=evidence_ids,
        reason=f"{reason} (+{score} points)",
    )


# =============================================================================
# EVIDENCE CONFIDENCE COMPONENT
# =============================================================================

def compute_evidence_confidence(entity: Entity) -> ComponentScore:
    """
    Compute aggregate confidence from Entity Evidence.
    
    Takes the minimum confidence across all Evidence objects
    (conservative approach) and scales to points:
    
    - confidence >= 0.8: +20 points
    - confidence >= 0.6: +15 points
    - confidence >= 0.4: +10 points
    - confidence >= 0.2: +5 points
    - confidence < 0.2: 0 points
    
    Returns: ComponentScore with 0-20 points
    """
    evidence_objects = get_entity_evidence(entity)
    
    if not evidence_objects:
        return ComponentScore(
            name="evidence_confidence",
            raw_value=0.0,
            contribution=0.0,
            evidence_ids=[],
            reason="No evidence objects found",
        )
    
    # Conservative: take minimum confidence
    min_confidence = min(e.meta.confidence for e in evidence_objects)
    evidence_ids = [e.evidence_id for e in evidence_objects]
    
    if min_confidence >= 0.8:
        score = 20
        level = "High"
    elif min_confidence >= 0.6:
        score = 15
        level = "Good"
    elif min_confidence >= 0.4:
        score = 10
        level = "Moderate"
    elif min_confidence >= 0.2:
        score = 5
        level = "Low"
    else:
        score = 0
        level = "Very low"
    
    return ComponentScore(
        name="evidence_confidence",
        raw_value=min_confidence,
        contribution=float(score),
        evidence_ids=evidence_ids,
        reason=f"{level} evidence confidence ({min_confidence:.0%}) (+{score} points)",
    )


# =============================================================================
# ENTITY COMPLETENESS COMPONENT
# =============================================================================

def compute_entity_completeness(entity: Entity) -> ComponentScore:
    """
    Compute completeness based on known fields.
    
    Required fields (always present):
    - company_name
    - domain
    
    Optional enriched fields:
    - industry (+3 points)
    - size_estimate (+2 points)
    - country (would be +2 points if stored)
    
    Returns: ComponentScore with 0-10 points
    """
    evidence_ids = [
        entity.company_name.evidence_id,
        entity.domain.evidence_id,
    ]
    
    # Base score for required fields
    score = 5
    fields_present = ["company_name", "domain"]
    
    # Check optional enriched fields
    if entity.industry:
        score += 3
        fields_present.append("industry")
        evidence_ids.append(entity.industry.evidence_id)
    
    if entity.size_estimate:
        score += 2
        fields_present.append("size_estimate")
        evidence_ids.append(entity.size_estimate.evidence_id)
    
    completeness_pct = len(fields_present) / 4  # 4 possible fields
    
    return ComponentScore(
        name="entity_completeness",
        raw_value=completeness_pct,
        contribution=float(score),
        evidence_ids=evidence_ids,
        reason=f"Entity has {len(fields_present)} fields ({', '.join(fields_present)}) (+{score} points)",
    )


# =============================================================================
# NOISE PENALTY COMPONENT
# =============================================================================

NOISE_KEYWORDS = [
    "maybe", "possibly", "might", "unclear", "unconfirmed",
    "rumor", "speculation", "could be", "tbd", "tentative",
]


def compute_noise_penalty(signal: Optional[Signal] = None) -> ComponentScore:
    """
    Compute penalty for weak, vague, or borderline signals.
    
    Looks for uncertainty markers in signal text.
    Each noise keyword reduces score:
    - 1-2 noise keywords: -5 points
    - 3+ noise keywords: -10 points
    
    Returns: ComponentScore with -10 to 0 points
    """
    if signal is None:
        return ComponentScore(
            name="noise_penalty",
            raw_value=0.0,
            contribution=0.0,
            evidence_ids=[],
            reason="No signal text to analyze for noise",
        )
    
    text = signal.raw_text.lower()
    evidence_ids = [signal.signal_id]
    
    noise_count = sum(1 for kw in NOISE_KEYWORDS if kw in text)
    
    if noise_count == 0:
        return ComponentScore(
            name="noise_penalty",
            raw_value=0.0,
            contribution=0.0,
            evidence_ids=evidence_ids,
            reason="Clean signal, no uncertainty markers",
        )
    elif noise_count <= 2:
        return ComponentScore(
            name="noise_penalty",
            raw_value=float(noise_count),
            contribution=-5.0,
            evidence_ids=evidence_ids,
            reason=f"Signal contains {noise_count} uncertainty markers (-5 points)",
        )
    else:
        return ComponentScore(
            name="noise_penalty",
            raw_value=float(noise_count),
            contribution=-10.0,
            evidence_ids=evidence_ids,
            reason=f"Signal contains {noise_count} uncertainty markers (-10 points)",
        )
