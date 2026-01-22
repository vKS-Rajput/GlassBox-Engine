"""
Entity Resolver for GlassBox Discovery Engine.

Phase 2: Convert accepted Signals into verified Entities.

Design principles:
- Every Entity field must have attached Evidence
- Evidence must trace back to the originating Signal
- Ambiguity is rejected, not resolved
- No placeholders, no guesses

Trust boundary: If the system is not sure, it rejects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from ..domain import (
    Entity,
    Rejection,
    RejectionError,
    RejectionRule,
    Signal,
)
from ..evidence import (
    Evidence,
    EvidenceType,
    create_evidence_id,
    create_inference,
    create_observation,
)


# =============================================================================
# DOMAIN VALIDATION
# =============================================================================

# Personal email domains (not company domains)
PERSONAL_EMAIL_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", 
    "aol.com", "icloud.com", "mail.com", "protonmail.com",
    "live.com", "msn.com", "ymail.com", "googlemail.com",
})

# URL shortener domains (cannot be resolved to company)
URL_SHORTENER_DOMAINS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
    "is.gd", "buff.ly", "rebrand.ly", "short.io",
})

# Known job board domains (signal source, not company domain)
JOB_BOARD_DOMAINS = frozenset({
    "greenhouse.io", "lever.co", "workday.com", "jobvite.com",
    "icims.com", "smartrecruiters.com", "bamboohr.com",
    "indeed.com", "linkedin.com", "glassdoor.com",
})

# Valid TLDs (subset of common ones for conservative validation)
VALID_TLDS = frozenset({
    "com", "org", "net", "io", "co", "ai", "app", "dev",
    "tech", "xyz", "info", "biz", "me", "us", "uk", "de",
    "fr", "ca", "au", "in", "jp", "cn", "eu", "edu", "gov",
    "ly",  # Libya TLD, used by bit.ly and others
})

# Reserved/invalid TLDs
INVALID_TLDS = frozenset({
    "test", "invalid", "localhost", "example", "local",
})


class DomainValidationError(Exception):
    """Raised when domain validation fails."""
    pass


def extract_domain_from_url(url: str) -> Optional[str]:
    """
    Extract the registrable domain from a URL.
    
    Example:
        "https://boards.greenhouse.io/acme/jobs/123" -> "greenhouse.io"
        "https://www.acme.com/careers" -> "acme.com"
    """
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        
        # Get the host, remove port if present
        host = parsed.netloc.split(':')[0].lower()
        
        # Remove www prefix
        if host.startswith('www.'):
            host = host[4:]
        
        # Get registrable domain (last two parts for most TLDs)
        parts = host.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return host
    except Exception:
        return None


def extract_company_domain_from_job_url(url: str) -> Optional[str]:
    """
    Extract the company domain from a job board URL.
    
    Job boards like Greenhouse use patterns like:
        boards.greenhouse.io/companyname/jobs/123
    
    This extracts "companyname" which can be used to infer company identity,
    but NOT as a domain (that would require enrichment).
    
    Returns None if no company identifier can be extracted.
    """
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        # Greenhouse pattern: /companyname/jobs/...
        if 'greenhouse.io' in parsed.netloc and len(path_parts) >= 1:
            return path_parts[0]
        
        # Lever pattern: lever.co/companyname/...
        if 'lever.co' in parsed.netloc and len(path_parts) >= 1:
            return path_parts[0]
        
        return None
    except Exception:
        return None


def validate_domain(domain: str, signal_id: Optional[str] = None) -> None:
    """
    Validate that a domain is suitable for Entity resolution.
    
    Fails if:
    - Not a valid domain format
    - Personal email domain
    - URL shortener
    - Job board domain (source, not target)
    - Invalid TLD
    
    Raises:
        RejectionError: With R4_INVALID_DOMAIN if validation fails
    """
    if not domain:
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            "Domain is empty",
            signal_id,
        )
    
    domain = domain.lower().strip()
    
    # Basic format: must have at least one dot
    if '.' not in domain:
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"Invalid domain format: {domain}",
            signal_id,
        )
    
    # Extract TLD
    parts = domain.split('.')
    tld = parts[-1]
    
    # Check for invalid TLDs
    if tld in INVALID_TLDS:
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"Domain uses reserved/invalid TLD: {domain}",
            signal_id,
        )
    
    # Check for valid TLDs (conservative whitelist)
    if tld not in VALID_TLDS:
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"Domain TLD not in allowed list: {domain}",
            signal_id,
        )
    
    # Check for personal email domains
    if domain in PERSONAL_EMAIL_DOMAINS:
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"Personal email domain not allowed: {domain}",
            signal_id,
        )
    
    # Check for URL shorteners
    if domain in URL_SHORTENER_DOMAINS:
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"URL shortener domain not resolvable: {domain}",
            signal_id,
        )
    
    # Check for job board domains
    if domain in JOB_BOARD_DOMAINS:
        raise RejectionError(
            RejectionRule.R4_INVALID_DOMAIN,
            f"Job board domain is signal source, not company: {domain}",
            signal_id,
        )


def normalize_domain(domain: str) -> str:
    """
    Normalize a domain deterministically.
    
    - Lowercase
    - Strip whitespace
    - Remove trailing dots
    - Remove www prefix
    """
    domain = domain.lower().strip().rstrip('.')
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


# =============================================================================
# COMPANY NAME EXTRACTION
# =============================================================================

def extract_company_name_from_signal(signal: Signal) -> Optional[str]:
    """
    Attempt to extract company name from signal text.
    
    This is conservative extraction — looks for explicit patterns only.
    Does NOT guess or infer.
    
    Patterns recognized:
    - "at [Company]"
    - "[Company] is hiring"
    - "Join [Company]"
    - URL-based company slug
    """
    text = signal.raw_text
    
    # Pattern 1: "at [Company]" or "@ [Company]"
    pattern_at = r'(?:at|@)\s+([A-Z][A-Za-z0-9\s]{1,30}?)(?:\s+(?:is|are|we)|\.|,|$)'
    match = re.search(pattern_at, text)
    if match:
        return match.group(1).strip()
    
    # Pattern 2: "[Company] is hiring"
    pattern_hiring = r'([A-Z][A-Za-z0-9\s]{1,30}?)\s+(?:is|are)\s+hiring'
    match = re.search(pattern_hiring, text)
    if match:
        return match.group(1).strip()
    
    # Pattern 3: "Join [Company]"
    pattern_join = r'[Jj]oin\s+([A-Z][A-Za-z0-9\s]{1,30}?)(?:\s+(?:as|to|and)|\.|,|!|$)'
    match = re.search(pattern_join, text)
    if match:
        return match.group(1).strip()
    
    # Pattern 4: Company slug from job board URL
    company_slug = extract_company_domain_from_job_url(signal.source_url)
    if company_slug:
        # Convert slug to title case
        return company_slug.replace('-', ' ').replace('_', ' ').title()
    
    return None


def extract_domain_from_signal(signal: Signal) -> Optional[str]:
    """
    Attempt to extract a company domain from signal.
    
    Priority:
    1. Explicit domain mention in text (company.com)
    2. Inferred from job board URL slug + ".com"
    
    Returns None if no domain can be confidently extracted.
    """
    text = signal.raw_text
    
    # Pattern 1: Explicit domain in text (e.g., "visit acme.com")
    # This pattern matches full domains including subdomains
    domain_pattern = r'\b([a-z0-9][a-z0-9.-]*\.[a-z]{2,10})\b'
    matches = re.findall(domain_pattern, text.lower())
    
    # Filter out known non-company domains and normalize to registrable domain
    registrable_domains = set()
    for d in matches:
        if d in PERSONAL_EMAIL_DOMAINS:
            continue
        if d in URL_SHORTENER_DOMAINS:
            continue
        if d in JOB_BOARD_DOMAINS:
            continue
        
        # Normalize to registrable domain (remove subdomains)
        # e.g., careers.acme.com → acme.com
        parts = d.split('.')
        if len(parts) >= 2:
            registrable = '.'.join(parts[-2:])
        else:
            registrable = d
        
        # Skip if the registrable domain is in blocked lists
        if registrable in PERSONAL_EMAIL_DOMAINS:
            continue
        if registrable in URL_SHORTENER_DOMAINS:
            continue
        if registrable in JOB_BOARD_DOMAINS:
            continue
            
        registrable_domains.add(registrable)
    
    if len(registrable_domains) == 1:
        # Exactly one unique company domain found — unambiguous
        return normalize_domain(list(registrable_domains)[0])
    elif len(registrable_domains) > 1:
        # Multiple different company domains — ambiguous, return None
        return None
    
    # Pattern 2: Infer from job board URL slug
    company_slug = extract_company_domain_from_job_url(signal.source_url)
    if company_slug:
        # Assume .com (conservative guess — marked as inference)
        return f"{company_slug.lower()}.com"
    
    return None


# =============================================================================
# AMBIGUITY DETECTION
# =============================================================================

@dataclass
class AmbiguityCheck:
    """Result of ambiguity analysis."""
    is_ambiguous: bool
    reason: Optional[str] = None


def check_for_ambiguity(
    signal: Signal,
    extracted_name: Optional[str],
    extracted_domain: Optional[str],
) -> AmbiguityCheck:
    """
    Check if entity resolution has ambiguity.
    
    Ambiguous cases:
    - Multiple company names detected
    - Multiple domains detected
    - Name and domain seem to refer to different companies
    - Generic name with no corroborating domain
    """
    text = signal.raw_text.lower()
    
    # Check for multiple company references
    company_indicators = ["at ", "@ ", " is hiring", "join "]
    indicator_count = sum(1 for ind in company_indicators if ind in text)
    
    # Multiple indicators might mean multiple companies
    if indicator_count > 2:
        return AmbiguityCheck(
            is_ambiguous=True,
            reason="Multiple company references detected in signal",
        )
    
    # Domain found in text but doesn't match extracted domain
    domain_pattern = r'\b([a-z0-9][a-z0-9-]*\.[a-z]{2,10})\b'
    text_domains = set(re.findall(domain_pattern, text))
    text_domains = {
        d for d in text_domains
        if d not in PERSONAL_EMAIL_DOMAINS
        and d not in URL_SHORTENER_DOMAINS
        and d not in JOB_BOARD_DOMAINS
    }
    
    if len(text_domains) > 1:
        return AmbiguityCheck(
            is_ambiguous=True,
            reason=f"Multiple domains in signal text: {text_domains}",
        )
    
    # Generic company name without domain
    generic_names = {"company", "startup", "team", "organization", "firm"}
    if extracted_name and extracted_name.lower() in generic_names:
        if not extracted_domain:
            return AmbiguityCheck(
                is_ambiguous=True,
                reason=f"Generic company name '{extracted_name}' without domain",
            )
    
    return AmbiguityCheck(is_ambiguous=False)


# =============================================================================
# ENTITY RESOLUTION
# =============================================================================

@dataclass
class ResolutionResult:
    """Result of entity resolution attempt."""
    success: bool
    entity: Optional[Entity] = None
    rejection: Optional[Rejection] = None


def resolve_entity(signal: Signal) -> ResolutionResult:
    """
    Resolve a Signal into a verified Entity.
    
    This is the core Phase 2 function. It:
    1. Extracts company name and domain from signal
    2. Validates the domain
    3. Checks for ambiguity
    4. Creates Evidence-backed Entity
    
    Returns:
        ResolutionResult with either:
        - success=True and verified Entity
        - success=False and Rejection with reason
    """
    signal_id = signal.signal_id
    
    try:
        # Step 1: Extract company name
        company_name = extract_company_name_from_signal(signal)
        if not company_name:
            raise RejectionError(
                RejectionRule.R3_MISSING_ENTITY,
                "Could not extract company name from signal",
                signal_id,
            )
        
        # Step 2: Extract domain
        domain = extract_domain_from_signal(signal)
        if not domain:
            raise RejectionError(
                RejectionRule.R3_MISSING_ENTITY,
                "Could not extract or infer company domain from signal",
                signal_id,
            )
        
        # Step 3: Validate domain
        validate_domain(domain, signal_id)
        
        # Step 4: Check for ambiguity
        ambiguity = check_for_ambiguity(signal, company_name, domain)
        if ambiguity.is_ambiguous:
            raise RejectionError(
                RejectionRule.R3_MISSING_ENTITY,
                f"Ambiguous entity: {ambiguity.reason}",
                signal_id,
            )
        
        # Step 5: Create Evidence-backed Entity
        # First, convert signal to evidence (for provenance chain)
        signal_evidence = signal.to_evidence()
        
        # Company name evidence (inferred from signal)
        company_name_evidence = create_inference(
            field_name="company_name",
            value=company_name,
            source_evidence_ids=[signal_evidence.evidence_id],
            inference_rule="regex_extraction_from_signal",
            confidence=0.75,  # Conservative confidence for extraction
        )
        
        # Determine domain evidence type
        # If domain was explicitly in text, it's higher confidence
        text_has_domain = domain in signal.raw_text.lower()
        
        if text_has_domain:
            # Domain was explicitly mentioned — higher confidence
            domain_evidence = create_inference(
                field_name="domain",
                value=domain,
                source_evidence_ids=[signal_evidence.evidence_id],
                inference_rule="explicit_domain_extraction",
                confidence=0.85,
            )
        else:
            # Domain was inferred — lower confidence
            domain_evidence = create_inference(
                field_name="domain",
                value=domain,
                source_evidence_ids=[signal_evidence.evidence_id],
                inference_rule="domain_inference_from_url_slug",
                confidence=0.60,
            )
        
        # Create Entity
        entity = Entity(
            company_name=company_name_evidence,
            domain=domain_evidence,
        )
        
        return ResolutionResult(
            success=True,
            entity=entity,
        )
        
    except RejectionError as e:
        rejection = Rejection.from_error(
            rejection_id=create_evidence_id(),
            error=e,
            raw_signal=signal.raw_text,
        )
        return ResolutionResult(
            success=False,
            rejection=rejection,
        )


# =============================================================================
# BATCH RESOLUTION
# =============================================================================

@dataclass
class BatchResolutionResult:
    """Result of resolving multiple signals."""
    total_signals: int
    resolved: list[Entity]
    rejected: list[Rejection]
    
    @property
    def resolution_rate(self) -> float:
        if self.total_signals == 0:
            return 0.0
        return len(self.resolved) / self.total_signals


def resolve_signals(signals: list[Signal]) -> BatchResolutionResult:
    """
    Resolve a batch of signals into entities.
    
    Each signal is processed independently.
    Failures do not affect other signals.
    """
    resolved: list[Entity] = []
    rejected: list[Rejection] = []
    
    for signal in signals:
        result = resolve_entity(signal)
        
        if result.success and result.entity:
            resolved.append(result.entity)
        elif result.rejection:
            rejected.append(result.rejection)
    
    return BatchResolutionResult(
        total_signals=len(signals),
        resolved=resolved,
        rejected=rejected,
    )
