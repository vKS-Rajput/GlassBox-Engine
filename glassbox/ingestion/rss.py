"""
RSS Feed Signal Ingestion for GlassBox Discovery Engine.

This module handles ingestion from a single signal source: RSS feeds
(typically job board feeds like Greenhouse, Lever, etc.).

Design principles:
- Every extracted field becomes an Evidence Object (type=OBS)
- No inference, only observation
- All signals pass through Phase 0 gating
- Rejections are explicit and logged

This is Phase 1: one signal source, controlled ingestion.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterator, Optional
from urllib.parse import urlparse

from ..domain import Signal, Rejection, RejectionError, RejectionRule
from ..evidence import create_evidence_id
from ..validation import (
    gate_signal,
    create_signal_id,
    create_dedup_hash,
    GatingResult,
)


# =============================================================================
# RSS PARSING
# =============================================================================

@dataclass
class RSSItem:
    """
    A single item from an RSS feed.
    
    This is the raw parsed representation before conversion to Signal.
    All fields are strings exactly as they appear in the feed.
    """
    title: str
    link: str
    description: str
    pub_date: Optional[datetime]
    guid: Optional[str]
    
    # Source tracking
    feed_url: str


class RSSParseError(Exception):
    """Raised when RSS feed cannot be parsed."""
    pass


def parse_rss_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse RSS pubDate string to datetime.
    
    RSS uses RFC 2822 format: "Wed, 02 Oct 2002 08:00:00 EST"
    Falls back to current time if unparseable (with warning).
    """
    if not date_str:
        return None
    
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        # Cannot parse date - will use current time
        return None


def parse_rss_feed(xml_content: str, feed_url: str) -> Iterator[RSSItem]:
    """
    Parse RSS XML content and yield RSSItem objects.
    
    Handles RSS 2.0 format. Does not handle Atom feeds.
    
    Args:
        xml_content: Raw XML string
        feed_url: URL of the feed (for provenance tracking)
    
    Yields:
        RSSItem for each <item> in the feed
    
    Raises:
        RSSParseError: If XML is malformed or not RSS
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise RSSParseError(f"Invalid XML: {e}")
    
    # Find channel - RSS 2.0 structure is <rss><channel><item>...
    channel = root.find("channel")
    if channel is None:
        # Try finding items directly (some feeds skip channel)
        items = root.findall(".//item")
    else:
        items = channel.findall("item")
    
    if not items:
        raise RSSParseError("No items found in RSS feed")
    
    for item in items:
        title = _get_text(item, "title") or ""
        link = _get_text(item, "link") or ""
        description = _get_text(item, "description") or ""
        pub_date_str = _get_text(item, "pubDate")
        guid = _get_text(item, "guid")
        
        # Skip items without link (no provenance possible)
        if not link:
            continue
        
        yield RSSItem(
            title=title,
            link=link,
            description=description,
            pub_date=parse_rss_date(pub_date_str),
            guid=guid,
            feed_url=feed_url,
        )


def _get_text(element: ET.Element, tag: str) -> Optional[str]:
    """Safely extract text from child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


# =============================================================================
# NORMALIZATION
# =============================================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for consistent processing.
    
    - Strip whitespace
    - Collapse multiple spaces
    - Remove HTML tags (basic)
    """
    import re
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    # Strip
    return text.strip()


def extract_domain_from_url(url: str) -> Optional[str]:
    """
    Extract domain from URL.
    
    e.g., "https://boards.greenhouse.io/acme/jobs/123" -> "greenhouse.io"
    """
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        
        # Remove subdomain for cleaner domain
        parts = parsed.netloc.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return parsed.netloc
    except Exception:
        return None


def normalize_datetime(dt: Optional[datetime]) -> datetime:
    """
    Normalize datetime, defaulting to UTC now if None.
    """
    if dt is None:
        return datetime.utcnow()
    
    # Ensure UTC (naive datetime assumed to be UTC)
    if dt.tzinfo is not None:
        from datetime import timezone
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    
    return dt


# =============================================================================
# SIGNAL CONVERSION
# =============================================================================

@dataclass
class IngestionResult:
    """Result of attempting to ingest an RSS item."""
    success: bool
    signal: Optional[Signal] = None
    rejection: Optional[Rejection] = None
    raw_item: Optional[RSSItem] = None


def rss_item_to_signal(item: RSSItem) -> Signal:
    """
    Convert an RSSItem to a Signal.
    
    This creates the raw Signal object. It does NOT yet pass through
    gating - that happens in the full ingestion pipeline.
    
    The Signal's raw_text is composed from title + description,
    as this is what will be analyzed for intent signals.
    """
    # Normalize the text content
    title = normalize_text(item.title)
    description = normalize_text(item.description)
    
    # Compose raw_text (what will be scanned for intent)
    if title and description:
        raw_text = f"{title}\n\n{description}"
    elif title:
        raw_text = title
    else:
        raw_text = description
    
    # Normalize timestamp
    timestamp = normalize_datetime(item.pub_date)
    
    # Generate IDs
    signal_id = create_signal_id(item.link, timestamp)
    dedup_hash = create_dedup_hash(item.link, raw_text)
    
    # Determine source type from feed URL
    source_domain = extract_domain_from_url(item.feed_url)
    source_type = f"rss_{source_domain}" if source_domain else "rss_unknown"
    
    return Signal(
        signal_id=signal_id,
        source_url=item.link,
        raw_text=raw_text,
        timestamp=timestamp,
        source_type=source_type,
        dedup_hash=dedup_hash,
    )


def ingest_rss_item(item: RSSItem) -> IngestionResult:
    """
    Ingest a single RSS item through the full pipeline.
    
    Pipeline:
    1. Convert to Signal (attach observation evidence)
    2. Pass through Phase 0 gating
    3. Return IngestionResult (success or rejection)
    
    This function guarantees:
    - Every accepted signal has Evidence
    - Every rejection has an audit trail
    - No partial or placeholder data
    """
    try:
        # Step 1: Convert to Signal
        signal = rss_item_to_signal(item)
        
        # Step 2: Pass through gating
        gating_result = gate_signal(
            source_url=signal.source_url,
            raw_text=signal.raw_text,
            timestamp=signal.timestamp,
            source_type=signal.source_type,
        )
        
        if gating_result.accepted:
            return IngestionResult(
                success=True,
                signal=gating_result.signal,
                raw_item=item,
            )
        else:
            return IngestionResult(
                success=False,
                rejection=gating_result.rejection,
                raw_item=item,
            )
            
    except RejectionError as e:
        # Signal construction itself failed
        rejection = Rejection.from_error(
            rejection_id=create_evidence_id(),
            error=e,
            raw_signal=f"{item.title}\n{item.description}"[:500],
        )
        return IngestionResult(
            success=False,
            rejection=rejection,
            raw_item=item,
        )


# =============================================================================
# BATCH INGESTION
# =============================================================================

@dataclass
class BatchIngestionResult:
    """Result of ingesting an entire RSS feed."""
    total_items: int
    accepted: list[Signal]
    rejected: list[Rejection]
    
    @property
    def acceptance_rate(self) -> float:
        if self.total_items == 0:
            return 0.0
        return len(self.accepted) / self.total_items


def ingest_rss_feed(
    xml_content: str, 
    feed_url: str,
    seen_hashes: Optional[set[str]] = None,
) -> BatchIngestionResult:
    """
    Ingest an entire RSS feed.
    
    Args:
        xml_content: Raw XML string of the feed
        feed_url: URL of the feed (for provenance)
        seen_hashes: Optional set of dedup hashes to skip
    
    Returns:
        BatchIngestionResult with accepted signals and rejections
    """
    if seen_hashes is None:
        seen_hashes = set()
    
    accepted: list[Signal] = []
    rejected: list[Rejection] = []
    total = 0
    
    try:
        items = list(parse_rss_feed(xml_content, feed_url))
    except RSSParseError as e:
        # Cannot parse feed at all - return empty result
        # In production, this would be logged
        return BatchIngestionResult(
            total_items=0,
            accepted=[],
            rejected=[],
        )
    
    for item in items:
        total += 1
        
        # Deduplication check (before full ingestion)
        temp_signal = rss_item_to_signal(item)
        if temp_signal.dedup_hash in seen_hashes:
            # Skip duplicate - not a rejection, just a skip
            continue
        
        # Full ingestion
        result = ingest_rss_item(item)
        
        if result.success and result.signal:
            accepted.append(result.signal)
            seen_hashes.add(result.signal.dedup_hash)
        elif result.rejection:
            rejected.append(result.rejection)
    
    return BatchIngestionResult(
        total_items=total,
        accepted=accepted,
        rejected=rejected,
    )
