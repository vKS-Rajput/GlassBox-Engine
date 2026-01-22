"""
Validation and Gating Logic for GlassBox Discovery Engine.

This module implements the relevance gating system that operates
on a binary accept/reject model. There is no "maybe" state.

Minimum acceptance requirements (ALL must be true):
1. At least one time-sensitive intent signal with age ≤ 30 days
2. At least one resolvable entity: company name AND valid domain
3. LLM classification confidence ≥ 0.8
4. Valid JSON output from LLM (schema-conformant)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .domain import (
    Entity,
    IntentType,
    Lead,
    Rejection,
    RejectionError,
    RejectionRule,
    Signal,
)
from .evidence import (
    Evidence,
    EvidenceType,
    EvidenceValidationError,
    create_evidence_id,
    create_observation,
)


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Relevance gating thresholds
MIN_CONFIDENCE_THRESHOLD = 0.8
MAX_SIGNAL_AGE_DAYS = 30
MIN_COMPANY_SIZE = 2
MAX_COMPANY_SIZE = 1000

# Domain validation patterns
PARKED_DOMAIN_INDICATORS = [
    "parked", "for sale", "buy this domain", "domain expired",
    "coming soon", "under construction",
]


# =============================================================================
# SIGNAL VALIDATION
# =============================================================================

def create_signal_id(source_url: str, timestamp: datetime) -> str:
    """Generate a unique signal ID from source URL and timestamp."""
    content = f"{source_url}:{timestamp.isoformat()}"
    return f"sig_{hashlib.sha256(content.encode()).hexdigest()[:12]}"


def create_dedup_hash(source_url: str, raw_text: str) -> str:
    """Generate deduplication hash for a signal."""
    content = f"{source_url}:{raw_text[:500]}"
    return hashlib.sha256(content.encode()).hexdigest()


def validate_signal_freshness(
    timestamp: datetime,
    max_age_days: int = MAX_SIGNAL_AGE_DAYS,
    signal_id: Optional[str] = None,
) -> None:
    """
    Validate that a signal is not stale.
    
    Raises:
        RejectionError: If signal is older than max_age_days (R2)
    """
    age = datetime.utcnow() - timestamp
    if age > timedelta(days=max_age_days):
        raise RejectionError(
            RejectionRule.R2_STALE_SIGNAL,
            f"Signal is {age.days} days old, maximum is {max_age_days} days",
            signal_id,
        )


def validate_intent_signal_present(
    raw_text: str,
    signal_id: Optional[str] = None,
) -> Optional[IntentType]:
    """
    Check if raw text contains a time-sensitive intent signal.
    
    Returns:
        IntentType if found, None otherwise
    
    Raises:
        RejectionError: If no intent signal is detected (R1)
    """
    text_lower = raw_text.lower()
    
    # Hiring signals
    hiring_keywords = [
        "hiring", "job opening", "we're looking for", "join our team",
        "open position", "career opportunity", "now hiring",
        "seeking", "looking to hire", "job post",
    ]
    if any(kw in text_lower for kw in hiring_keywords):
        return IntentType.HIRING
    
    # Funding signals
    funding_keywords = [
        "raised", "funding", "series a", "series b", "series c",
        "seed round", "investment", "fundraise", "capital",
    ]
    if any(kw in text_lower for kw in funding_keywords):
        return IntentType.FUNDING
    
    # Executive change signals
    exec_keywords = [
        "new ceo", "new cto", "appointed", "joins as",
        "promoted to", "named as", "executive",
    ]
    if any(kw in text_lower for kw in exec_keywords):
        return IntentType.EXECUTIVE_CHANGE
    
    # No intent signal found
    raise RejectionError(
        RejectionRule.R1_NO_INTENT_SIGNAL,
        "No time-sensitive intent signal (hiring/funding/executive change) detected",
        signal_id,
    )


# =============================================================================
# ENTITY VALIDATION
# =============================================================================

def validate_domain_resolvable(
    domain: str,
    signal_id: Optional[str] = None,
) -> None:
    """
    Validate that a domain appears to be resolvable.
    
    Note: This is a heuristic check. Full DNS resolution would 
    require network calls which are not part of Phase 0.
    
    Raises:
        RejectionError: If domain appears invalid or parked (R4)
    """
    # Basic format validation
    domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}$'
    if not re.match(domain_pattern, domain):
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"Domain '{domain}' does not match valid domain pattern",
            signal_id,
        )
    
    # Check for known parked/invalid TLDs (heuristic)
    invalid_tlds = [".test", ".invalid", ".localhost", ".example"]
    if any(domain.endswith(tld) for tld in invalid_tlds):
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"Domain '{domain}' uses reserved/invalid TLD",
            signal_id,
        )


def validate_company_size(
    size: int,
    min_size: int = MIN_COMPANY_SIZE,
    max_size: int = MAX_COMPANY_SIZE,
    signal_id: Optional[str] = None,
) -> None:
    """
    Validate company size is within acceptable range.
    
    Raises:
        RejectionError: If size is outside range (R6)
    """
    if size < min_size or size > max_size:
        raise RejectionError(
            RejectionRule.R6_SIZE_MISMATCH,
            f"Company size {size} is outside acceptable range [{min_size}, {max_size}]",
            signal_id,
        )


def validate_industry_in_scope(
    industry: str,
    target_industries: list[str],
    signal_id: Optional[str] = None,
) -> None:
    """
    Validate that industry is in the target list.
    
    Raises:
        RejectionError: If industry is not in target list (R5)
    """
    industry_lower = industry.lower()
    targets_lower = [t.lower() for t in target_industries]
    
    if industry_lower not in targets_lower:
        raise RejectionError(
            RejectionRule.R5_OUT_OF_SCOPE_INDUSTRY,
            f"Industry '{industry}' is not in target list: {target_industries}",
            signal_id,
        )


# =============================================================================
# LLM OUTPUT VALIDATION
# =============================================================================

@dataclass
class LLMExtractionResult:
    """
    Structured output from LLM entity extraction.
    
    This is what we expect the LLM to produce after processing a signal.
    """
    company_name: str
    domain: str
    intent_type: IntentType
    confidence: float
    role: Optional[str] = None
    industry: Optional[str] = None
    
    def validate(self, signal_id: Optional[str] = None) -> None:
        """
        Validate LLM output meets minimum requirements.
        
        Raises:
            RejectionError: If validation fails (R3, R7)
        """
        # Check required fields
        if not self.company_name:
            raise RejectionError(
                RejectionRule.R3_MISSING_ENTITY,
                "LLM did not extract company_name",
                signal_id,
            )
        if not self.domain:
            raise RejectionError(
                RejectionRule.R3_MISSING_ENTITY,
                "LLM did not extract domain",
                signal_id,
            )
        
        # Check confidence threshold
        if self.confidence < MIN_CONFIDENCE_THRESHOLD:
            raise RejectionError(
                RejectionRule.R7_LLM_FAILURE,
                f"LLM confidence {self.confidence} is below threshold {MIN_CONFIDENCE_THRESHOLD}",
                signal_id,
            )


def validate_llm_json_output(
    json_output: dict,
    signal_id: Optional[str] = None,
) -> LLMExtractionResult:
    """
    Validate and parse LLM JSON output.
    
    Raises:
        RejectionError: If JSON is malformed or missing required fields (R7)
    
    Returns:
        LLMExtractionResult if valid
    """
    required_fields = ["company_name", "domain", "intent_type", "confidence"]
    
    for field in required_fields:
        if field not in json_output:
            raise RejectionError(
                RejectionRule.R7_LLM_FAILURE,
                f"LLM JSON output missing required field: {field}",
                signal_id,
            )
    
    try:
        intent_type = IntentType(json_output["intent_type"])
    except ValueError:
        raise RejectionError(
            RejectionRule.R7_LLM_FAILURE,
            f"Invalid intent_type: {json_output['intent_type']}",
            signal_id,
        )
    
    try:
        confidence = float(json_output["confidence"])
    except (ValueError, TypeError):
        raise RejectionError(
            RejectionRule.R7_LLM_FAILURE,
            f"Invalid confidence value: {json_output['confidence']}",
            signal_id,
        )
    
    result = LLMExtractionResult(
        company_name=json_output["company_name"],
        domain=json_output["domain"],
        intent_type=intent_type,
        confidence=confidence,
        role=json_output.get("role"),
        industry=json_output.get("industry"),
    )
    
    result.validate(signal_id)
    return result


# =============================================================================
# FULL SIGNAL GATING
# =============================================================================

@dataclass
class GatingResult:
    """Result of the gating check."""
    accepted: bool
    signal: Optional[Signal] = None
    intent_type: Optional[IntentType] = None
    rejection: Optional[Rejection] = None


def gate_signal(
    source_url: str,
    raw_text: str,
    timestamp: datetime,
    source_type: str,
) -> GatingResult:
    """
    Apply full gating logic to a raw signal.
    
    This is the binary accept/reject gate. There is no "maybe" state.
    
    Returns:
        GatingResult with either accepted=True and Signal, or 
        accepted=False and Rejection
    """
    signal_id = create_signal_id(source_url, timestamp)
    
    try:
        # R2: Check freshness
        validate_signal_freshness(timestamp, signal_id=signal_id)
        
        # R1: Check intent signal present
        intent_type = validate_intent_signal_present(raw_text, signal_id=signal_id)
        
        # Create validated signal
        signal = Signal(
            signal_id=signal_id,
            source_url=source_url,
            raw_text=raw_text,
            timestamp=timestamp,
            source_type=source_type,
            dedup_hash=create_dedup_hash(source_url, raw_text),
        )
        
        return GatingResult(
            accepted=True,
            signal=signal,
            intent_type=intent_type,
        )
        
    except RejectionError as e:
        rejection = Rejection.from_error(
            rejection_id=create_evidence_id(),
            error=e,
            raw_signal=raw_text,
        )
        return GatingResult(
            accepted=False,
            rejection=rejection,
        )
