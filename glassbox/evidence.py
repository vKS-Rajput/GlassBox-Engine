"""
Evidence Ledger — The canonical data contract for GlassBox.

SYSTEM INVARIANT:
    No field, attribute, inference, or conclusion may exist in the system
    without an attached Evidence Object. This is enforced at write time.
    Violations cause hard failures.

Evidence Types:
    OBS (Observation) — Text scraped from a specific, verifiable URL
    INF (Inference)   — Value derived from observed data via documented rule
    API (Third-Party) — Value returned from external service with known lineage
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


class EvidenceType(Enum):
    """The three valid evidence types per the implementation plan."""
    OBS = "observation"   # Direct observation from verifiable URL
    INF = "inference"     # Derived from other evidence via documented rule
    API = "third_party"   # From external API with known data lineage


# Base confidence values per evidence type
BASE_CONFIDENCE = {
    EvidenceType.OBS: 0.95,
    EvidenceType.INF: 0.70,
    EvidenceType.API: 0.85,  # Default; can be overridden by provider confidence
}


@dataclass(frozen=True)
class EvidenceMeta:
    """
    Metadata attached to every Evidence Object.
    
    Required fields vary by evidence type:
    - OBS: source_url, timestamp, extraction_method
    - INF: source_evidence_ids, inference_rule, timestamp
    - API: provider_name, api_response_id, timestamp, provider_confidence
    """
    timestamp: datetime
    confidence: float
    
    # For OBS type
    source_url: Optional[str] = None
    extraction_method: Optional[str] = None
    
    # For INF type
    source_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    inference_rule: Optional[str] = None
    
    # For API type
    provider_name: Optional[str] = None
    api_response_id: Optional[str] = None
    provider_confidence: Optional[float] = None
    
    # Validation state
    validated: bool = False
    validation_method: Optional[str] = None
    
    # Decay tracking
    invalidated: bool = False


class EvidenceValidationError(Exception):
    """Raised when evidence fails validation checks."""
    pass


@dataclass(frozen=True)
class Evidence:
    """
    The canonical Evidence Object.
    
    This is the primary data structure of the system. Every piece of 
    information must be wrapped in this structure. Raw strings do not 
    exist in the database.
    
    Invariants enforced:
    1. evidence_id must be present
    2. evidence_type must be valid
    3. meta.timestamp must be present
    4. meta.confidence must be in [0.0, 1.0]
    5. Type-specific metadata must be present
    """
    evidence_id: str
    field_name: str
    value: Any
    evidence_type: EvidenceType
    meta: EvidenceMeta
    
    def __post_init__(self):
        """Enforce invariants at construction time."""
        self._validate()
    
    def _validate(self) -> None:
        """
        Validate evidence object. Raises EvidenceValidationError if invalid.
        
        This is the enforcement of the system invariant:
        "Any write that omits evidence_id, type, meta.timestamp, or 
         meta.confidence is rejected."
        """
        # Required for all types
        if not self.evidence_id:
            raise EvidenceValidationError("evidence_id is required")
        
        if not isinstance(self.evidence_type, EvidenceType):
            raise EvidenceValidationError(
                f"evidence_type must be EvidenceType, got {type(self.evidence_type)}"
            )
        
        if self.meta.timestamp is None:
            raise EvidenceValidationError("meta.timestamp is required")
        
        if not (0.0 <= self.meta.confidence <= 1.0):
            raise EvidenceValidationError(
                f"meta.confidence must be in [0.0, 1.0], got {self.meta.confidence}"
            )
        
        # Type-specific validation
        if self.evidence_type == EvidenceType.OBS:
            self._validate_observation()
        elif self.evidence_type == EvidenceType.INF:
            self._validate_inference()
        elif self.evidence_type == EvidenceType.API:
            self._validate_api()
    
    def _validate_observation(self) -> None:
        """Validate OBS-specific requirements."""
        if not self.meta.source_url:
            raise EvidenceValidationError(
                "OBS evidence requires meta.source_url"
            )
        if not self.meta.extraction_method:
            raise EvidenceValidationError(
                "OBS evidence requires meta.extraction_method"
            )
    
    def _validate_inference(self) -> None:
        """Validate INF-specific requirements."""
        if not self.meta.source_evidence_ids:
            raise EvidenceValidationError(
                "INF evidence requires meta.source_evidence_ids"
            )
        if not self.meta.inference_rule:
            raise EvidenceValidationError(
                "INF evidence requires meta.inference_rule"
            )
    
    def _validate_api(self) -> None:
        """Validate API-specific requirements."""
        if not self.meta.provider_name:
            raise EvidenceValidationError(
                "API evidence requires meta.provider_name"
            )
        if not self.meta.api_response_id:
            raise EvidenceValidationError(
                "API evidence requires meta.api_response_id"
            )
    
    def is_stale(self, reference_time: Optional[datetime] = None) -> bool:
        """Check if this evidence has decayed to invalidation."""
        if self.meta.invalidated:
            return True
        
        current_confidence = self.calculate_current_confidence(reference_time)
        return current_confidence <= 0.0
    
    def calculate_current_confidence(
        self, 
        reference_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate confidence after decay.
        
        Decay schedules per implementation plan:
        - intent_signal: -0.25 per 7 days (reaches 0 at 28 days)
        - contact_email: -0.10 per 30 days
        - company_name, domain: No decay
        """
        if reference_time is None:
            reference_time = datetime.utcnow()
        
        age = reference_time - self.meta.timestamp
        days = age.days
        
        # Apply decay based on field name
        if self.field_name == "intent_signal":
            # -0.25 per 7 days
            decay = (days // 7) * 0.25
        elif self.field_name == "contact_email":
            # -0.10 per 30 days
            decay = (days // 30) * 0.10
        else:
            # No decay for company_name, domain, etc.
            decay = 0.0
        
        return max(0.0, self.meta.confidence - decay)


def create_evidence_id() -> str:
    """Generate a unique evidence ID."""
    return f"evt_{uuid.uuid4().hex[:12]}"


def create_observation(
    field_name: str,
    value: Any,
    source_url: str,
    extraction_method: str,
    timestamp: Optional[datetime] = None,
    confidence: Optional[float] = None,
) -> Evidence:
    """
    Factory function to create an Observation (OBS) evidence.
    
    This is the most common evidence type — direct scraping from a URL.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    if confidence is None:
        confidence = BASE_CONFIDENCE[EvidenceType.OBS]
    
    return Evidence(
        evidence_id=create_evidence_id(),
        field_name=field_name,
        value=value,
        evidence_type=EvidenceType.OBS,
        meta=EvidenceMeta(
            timestamp=timestamp,
            confidence=confidence,
            source_url=source_url,
            extraction_method=extraction_method,
        ),
    )


def create_inference(
    field_name: str,
    value: Any,
    source_evidence_ids: list[str],
    inference_rule: str,
    timestamp: Optional[datetime] = None,
    confidence: Optional[float] = None,
    validated: bool = False,
    validation_method: Optional[str] = None,
) -> Evidence:
    """
    Factory function to create an Inference (INF) evidence.
    
    Used when deriving values from other evidence (e.g., email from name + domain).
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    if confidence is None:
        confidence = BASE_CONFIDENCE[EvidenceType.INF]
    
    return Evidence(
        evidence_id=create_evidence_id(),
        field_name=field_name,
        value=value,
        evidence_type=EvidenceType.INF,
        meta=EvidenceMeta(
            timestamp=timestamp,
            confidence=confidence,
            source_evidence_ids=tuple(source_evidence_ids),
            inference_rule=inference_rule,
            validated=validated,
            validation_method=validation_method,
        ),
    )


def create_api_evidence(
    field_name: str,
    value: Any,
    provider_name: str,
    api_response_id: str,
    timestamp: Optional[datetime] = None,
    provider_confidence: Optional[float] = None,
) -> Evidence:
    """
    Factory function to create a Third-Party API (API) evidence.
    
    Used when data comes from external enrichment APIs.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    # Use provider confidence if available, otherwise default
    confidence = provider_confidence if provider_confidence else BASE_CONFIDENCE[EvidenceType.API]
    
    return Evidence(
        evidence_id=create_evidence_id(),
        field_name=field_name,
        value=value,
        evidence_type=EvidenceType.API,
        meta=EvidenceMeta(
            timestamp=timestamp,
            confidence=confidence,
            provider_name=provider_name,
            api_response_id=api_response_id,
            provider_confidence=provider_confidence,
        ),
    )
