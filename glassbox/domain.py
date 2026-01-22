"""
Core Domain Objects for GlassBox Discovery Engine.

All domain objects are built on the Evidence Ledger foundation.
The invariant is maintained: no field exists without Evidence.

Domain Objects:
    Signal      — A raw business event from a curated source
    Entity      — A resolved company with verified domain
    Lead        — A qualified prospect with evidence-backed fields
    Rejection   — An explicit discard with auditable reason
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .evidence import (
    Evidence,
    EvidenceType,
    EvidenceValidationError,
    create_observation,
)


# =============================================================================
# REJECTION SYSTEM
# =============================================================================

class RejectionRule(Enum):
    """
    Hard reject rules per implementation plan.
    
    Any of these triggers immediate discard:
    R1: No intent signal
    R2: Stale signal (> 30 days)
    R3: Missing entity
    R4: Invalid domain
    R5: Out-of-scope industry
    R6: Size mismatch
    R7: LLM failure
    R8: Missing evidence (system invariant violation)
    """
    R1_NO_INTENT_SIGNAL = "no_intent_signal"
    R2_STALE_SIGNAL = "stale_signal"
    R3_MISSING_ENTITY = "missing_entity"
    R4_INVALID_DOMAIN = "invalid_domain"
    R5_OUT_OF_SCOPE_INDUSTRY = "out_of_scope_industry"
    R6_SIZE_MISMATCH = "size_mismatch"
    R7_LLM_FAILURE = "llm_failure"
    R8_MISSING_EVIDENCE = "missing_evidence"


class RejectionError(Exception):
    """Raised when a domain object fails validation and must be rejected."""
    
    def __init__(self, rule: RejectionRule, reason: str, signal_id: Optional[str] = None):
        self.rule = rule
        self.reason = reason
        self.signal_id = signal_id
        super().__init__(f"[{rule.value}] {reason}")


@dataclass(frozen=True)
class Rejection:
    """
    An explicit rejection with auditable reason.
    
    Rejected signals are logged but NOT stored in the leads table.
    They exist only for pipeline debugging and are never retried.
    """
    rejection_id: str
    signal_id: str
    rule: RejectionRule
    reason: str
    raw_signal_snippet: str  # First 500 chars for debugging
    timestamp: datetime
    
    @classmethod
    def from_error(
        cls, 
        rejection_id: str,
        error: RejectionError, 
        raw_signal: str,
        timestamp: Optional[datetime] = None,
    ) -> Rejection:
        """Create a Rejection from a RejectionError."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        return cls(
            rejection_id=rejection_id,
            signal_id=error.signal_id or "unknown",
            rule=error.rule,
            reason=error.reason,
            raw_signal_snippet=raw_signal[:500],
            timestamp=timestamp,
        )


# =============================================================================
# SIGNAL
# =============================================================================

class IntentType(Enum):
    """Types of time-sensitive intent signals."""
    HIRING = "hiring"
    FUNDING = "funding"
    EXECUTIVE_CHANGE = "executive_change"


@dataclass(frozen=True)
class Signal:
    """
    A raw business event from a curated source.
    
    Signals are the input to the pipeline. They must contain:
    - A verifiable source URL
    - A timestamp (for freshness calculation)
    - Raw text content
    
    At this stage, no enrichment has occurred. The Signal is 
    essentially an Evidence Object of type OBS wrapping raw text.
    """
    signal_id: str
    source_url: str
    raw_text: str
    timestamp: datetime
    source_type: str  # e.g., "rss_greenhouse", "rss_lever", "firecrawl"
    
    # Deduplication key
    dedup_hash: str
    
    def __post_init__(self):
        """Validate signal requirements."""
        if not self.signal_id:
            raise RejectionError(
                RejectionRule.R8_MISSING_EVIDENCE,
                "signal_id is required",
            )
        if not self.source_url:
            raise RejectionError(
                RejectionRule.R8_MISSING_EVIDENCE,
                "source_url is required for signal provenance",
                self.signal_id,
            )
        if not self.raw_text:
            raise RejectionError(
                RejectionRule.R1_NO_INTENT_SIGNAL,
                "raw_text is empty, no intent signal present",
                self.signal_id,
            )
    
    def is_stale(self, max_age_days: int = 30) -> bool:
        """Check if signal is older than max_age_days."""
        from datetime import timedelta
        age = datetime.utcnow() - self.timestamp
        return age > timedelta(days=max_age_days)
    
    def to_evidence(self, field_name: str = "raw_signal") -> Evidence:
        """Convert signal to Evidence Object for storage."""
        return create_observation(
            field_name=field_name,
            value=self.raw_text,
            source_url=self.source_url,
            extraction_method=f"signal_ingestion_{self.source_type}",
            timestamp=self.timestamp,
        )


# =============================================================================
# ENTITY (Company)
# =============================================================================

@dataclass
class Entity:
    """
    A resolved company entity.
    
    Every field is an Evidence Object. Raw strings do not exist.
    
    Required fields (must have Evidence):
        - company_name
        - domain
    
    Optional fields:
        - industry
        - size_estimate
    """
    company_name: Evidence
    domain: Evidence
    industry: Optional[Evidence] = None
    size_estimate: Optional[Evidence] = None
    
    def __post_init__(self):
        """Validate entity requirements."""
        self._validate_required_evidence()
    
    def _validate_required_evidence(self) -> None:
        """
        Enforce: Required fields must have Evidence Objects.
        Violation triggers HARD REJECT.
        """
        if self.company_name is None:
            raise RejectionError(
                RejectionRule.R3_MISSING_ENTITY,
                "company_name Evidence is required",
            )
        if self.domain is None:
            raise RejectionError(
                RejectionRule.R3_MISSING_ENTITY,
                "domain Evidence is required",
            )
        
        # Validate field names match expected
        if self.company_name.field_name != "company_name":
            raise EvidenceValidationError(
                f"Expected field_name 'company_name', got '{self.company_name.field_name}'"
            )
        if self.domain.field_name != "domain":
            raise EvidenceValidationError(
                f"Expected field_name 'domain', got '{self.domain.field_name}'"
            )
    
    def get_domain_value(self) -> str:
        """Extract the domain string value."""
        return str(self.domain.value)
    
    def get_name_value(self) -> str:
        """Extract the company name string value."""
        return str(self.company_name.value)


# =============================================================================
# LEAD
# =============================================================================

class Tier(Enum):
    """
    Lead qualification tiers.
    
    Per implementation plan:
    - Tier 1: Hiring Signal + Tech Stack Match + Verified Email
    - Tier 2: Hiring Signal + Tech Stack Match (no email yet)
    - Tier 3: Hiring Signal only
    """
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    UNQUALIFIED = 0  # Fails minimum requirements


@dataclass
class Lead:
    """
    A qualified prospect with evidence-backed fields.
    
    INVARIANT: All fields are Evidence Objects (or None for optional).
    No raw strings. Every field can be traced to its source.
    
    Required Evidence fields:
        - company_name
        - domain
        - intent_signal
    
    Optional Evidence fields:
        - contact_name
        - contact_email
        - tech_stack
    """
    # Required fields (must be present with Evidence)
    company_name: Evidence
    domain: Evidence
    intent_signal: Evidence
    
    # Optional fields (can be None, but if present must be Evidence)
    contact_name: Optional[Evidence] = None
    contact_email: Optional[Evidence] = None
    tech_stack: Optional[Evidence] = None
    
    # Computed tier (deterministic, not Evidence-wrapped)
    tier: Tier = field(default=Tier.UNQUALIFIED)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Validate lead requirements and compute tier."""
        self._validate_required_evidence()
        self._validate_intent_signal_freshness()
        self.tier = self._compute_tier()
    
    def _validate_required_evidence(self) -> None:
        """
        Enforce: Required fields must have Evidence Objects.
        Violation triggers HARD REJECT.
        """
        if self.company_name is None:
            raise RejectionError(
                RejectionRule.R8_MISSING_EVIDENCE,
                "company_name Evidence is required for Lead",
            )
        if self.domain is None:
            raise RejectionError(
                RejectionRule.R8_MISSING_EVIDENCE,
                "domain Evidence is required for Lead",
            )
        if self.intent_signal is None:
            raise RejectionError(
                RejectionRule.R1_NO_INTENT_SIGNAL,
                "intent_signal Evidence is required for Lead",
            )
        
        # Validate field names
        expected = [
            (self.company_name, "company_name"),
            (self.domain, "domain"),
            (self.intent_signal, "intent_signal"),
        ]
        for evidence, expected_name in expected:
            if evidence.field_name != expected_name:
                raise EvidenceValidationError(
                    f"Expected field_name '{expected_name}', got '{evidence.field_name}'"
                )
    
    def _validate_intent_signal_freshness(self) -> None:
        """
        Enforce: Intent signal must be ≤ 30 days old.
        Stale signals trigger HARD REJECT.
        """
        if self.intent_signal.is_stale():
            raise RejectionError(
                RejectionRule.R2_STALE_SIGNAL,
                f"intent_signal is stale (timestamp: {self.intent_signal.meta.timestamp})",
            )
    
    def _compute_tier(self) -> Tier:
        """
        Compute tier using deterministic rules.
        
        Tier 1: Hiring Signal + Tech Stack Match + Verified Email
        Tier 2: Hiring Signal + Tech Stack Match
        Tier 3: Hiring Signal only
        """
        has_hiring = self.intent_signal is not None
        has_tech_stack = self.tech_stack is not None
        has_verified_email = (
            self.contact_email is not None 
            and self.contact_email.meta.validated
        )
        
        if has_hiring and has_tech_stack and has_verified_email:
            return Tier.TIER_1
        elif has_hiring and has_tech_stack:
            return Tier.TIER_2
        elif has_hiring:
            return Tier.TIER_3
        else:
            return Tier.UNQUALIFIED
    
    def get_sort_key(self) -> tuple:
        """
        Generate sort key for deterministic ordering.
        
        Sort order per implementation plan:
        1. Signal timestamp (newest first) — negated for descending
        2. Email confidence (highest first) — negated for descending
        3. Company name (alphabetical, for stability)
        """
        signal_timestamp = self.intent_signal.meta.timestamp.timestamp()
        email_confidence = (
            self.contact_email.meta.confidence 
            if self.contact_email else 0.0
        )
        company_name = self.company_name.value
        
        # Negate for descending order
        return (-signal_timestamp, -email_confidence, company_name)
    
    def has_contact(self) -> bool:
        """Check if lead has contact information."""
        return self.contact_email is not None
    
    def get_evidence_ids(self) -> list[str]:
        """Get all evidence IDs associated with this lead."""
        ids = [
            self.company_name.evidence_id,
            self.domain.evidence_id,
            self.intent_signal.evidence_id,
        ]
        if self.contact_name:
            ids.append(self.contact_name.evidence_id)
        if self.contact_email:
            ids.append(self.contact_email.evidence_id)
        if self.tech_stack:
            ids.append(self.tech_stack.evidence_id)
        return ids
