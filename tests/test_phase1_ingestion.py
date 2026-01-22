"""
Tests for Phase 1: RSS Signal Ingestion.

These tests verify:
1. Valid RSS items become Evidence-backed Signals
2. Invalid/stale items are rejected with audit trail
3. Phase 0 invariants remain enforced
4. Deduplication works correctly
"""

import pytest
from datetime import datetime, timedelta

from glassbox.ingestion.rss import (
    RSSItem,
    RSSParseError,
    parse_rss_feed,
    parse_rss_date,
    normalize_text,
    extract_domain_from_url,
    rss_item_to_signal,
    ingest_rss_item,
    ingest_rss_feed,
    IngestionResult,
    BatchIngestionResult,
)
from glassbox.domain import RejectionRule


# =============================================================================
# TEST FIXTURES
# =============================================================================

VALID_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Acme Corp Jobs</title>
    <link>https://jobs.acme.com</link>
    <item>
      <title>Senior Software Engineer</title>
      <link>https://boards.greenhouse.io/acme/jobs/123</link>
      <description>We're hiring a Senior Engineer to join our team!</description>
      <pubDate>Wed, 22 Jan 2026 10:00:00 GMT</pubDate>
      <guid>job-123</guid>
    </item>
    <item>
      <title>Product Manager</title>
      <link>https://boards.greenhouse.io/acme/jobs/456</link>
      <description>Looking for a PM to lead our product initiatives.</description>
      <pubDate>Wed, 22 Jan 2026 09:00:00 GMT</pubDate>
      <guid>job-456</guid>
    </item>
  </channel>
</rss>
"""

STALE_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Old Jobs</title>
    <item>
      <title>Ancient Position</title>
      <link>https://jobs.oldcompany.com/job/1</link>
      <description>We're hiring someone!</description>
      <pubDate>Wed, 01 Jan 2020 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

NO_INTENT_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Company Blog</title>
    <item>
      <title>Our Annual Picnic</title>
      <link>https://blog.company.com/picnic</link>
      <description>Photos from our annual company picnic event!</description>
      <pubDate>Wed, 22 Jan 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

MALFORMED_RSS = """<not valid xml at all"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
  </channel>
</rss>
"""


# =============================================================================
# RSS PARSING TESTS
# =============================================================================

class TestRSSParsing:
    """Test RSS XML parsing."""
    
    def test_parse_valid_feed(self):
        """Valid RSS feed should yield items."""
        items = list(parse_rss_feed(VALID_RSS_FEED, "https://jobs.acme.com/feed"))
        
        assert len(items) == 2
        assert items[0].title == "Senior Software Engineer"
        assert items[0].link == "https://boards.greenhouse.io/acme/jobs/123"
        assert "hiring" in items[0].description.lower()
    
    def test_parse_malformed_xml_raises(self):
        """Malformed XML should raise RSSParseError."""
        with pytest.raises(RSSParseError, match="Invalid XML"):
            list(parse_rss_feed(MALFORMED_RSS, "https://example.com/feed"))
    
    def test_parse_empty_feed_raises(self):
        """Empty feed (no items) should raise RSSParseError."""
        with pytest.raises(RSSParseError, match="No items found"):
            list(parse_rss_feed(EMPTY_RSS, "https://example.com/feed"))
    
    def test_parse_date_rfc2822(self):
        """RSS pubDate in RFC 2822 format should parse correctly."""
        dt = parse_rss_date("Wed, 22 Jan 2026 10:00:00 GMT")
        
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 22
    
    def test_parse_date_invalid(self):
        """Invalid date string should return None."""
        dt = parse_rss_date("not a date")
        assert dt is None

    def test_parse_date_none(self):
        """None input should return None."""
        dt = parse_rss_date(None)
        assert dt is None


# =============================================================================
# NORMALIZATION TESTS
# =============================================================================

class TestNormalization:
    """Test text and data normalization."""
    
    def test_normalize_html_tags(self):
        """HTML tags should be stripped."""
        text = "<p>Hello <b>World</b></p>"
        result = normalize_text(text)
        assert result == "Hello World"
    
    def test_normalize_whitespace(self):
        """Multiple spaces should collapse to single space."""
        text = "Hello    World  \n\n  Test"
        result = normalize_text(text)
        assert result == "Hello World Test"
    
    def test_extract_domain_from_url(self):
        """Domain should be extracted from URL."""
        url = "https://boards.greenhouse.io/acme/jobs/123"
        domain = extract_domain_from_url(url)
        assert domain == "greenhouse.io"
    
    def test_extract_domain_simple(self):
        """Simple domain should work."""
        url = "https://acme.com/jobs"
        domain = extract_domain_from_url(url)
        assert domain == "acme.com"
    
    def test_extract_domain_invalid(self):
        """Invalid URL should return None."""
        domain = extract_domain_from_url("not a url")
        assert domain is None


# =============================================================================
# SIGNAL CONVERSION TESTS
# =============================================================================

class TestSignalConversion:
    """Test RSS item to Signal conversion."""
    
    def test_rss_item_to_signal(self):
        """Valid RSS item should convert to Signal."""
        item = RSSItem(
            title="Senior Engineer",
            link="https://jobs.acme.com/123",
            description="We're hiring!",
            pub_date=datetime.utcnow(),
            guid="job-123",
            feed_url="https://jobs.acme.com/feed",
        )
        
        signal = rss_item_to_signal(item)
        
        assert signal.signal_id.startswith("sig_")
        assert signal.source_url == "https://jobs.acme.com/123"
        assert "Senior Engineer" in signal.raw_text
        assert "hiring" in signal.raw_text.lower()
        assert signal.source_type == "rss_acme.com"
    
    def test_signal_has_dedup_hash(self):
        """Signal should have deduplication hash."""
        item = RSSItem(
            title="Test Job",
            link="https://jobs.acme.com/123",
            description="Description",
            pub_date=datetime.utcnow(),
            guid="job-123",
            feed_url="https://jobs.acme.com/feed",
        )
        
        signal = rss_item_to_signal(item)
        
        assert signal.dedup_hash is not None
        assert len(signal.dedup_hash) == 64  # SHA-256 hex


# =============================================================================
# INGESTION PIPELINE TESTS
# =============================================================================

class TestIngestionPipeline:
    """Test full ingestion pipeline with gating."""
    
    def test_ingest_valid_hiring_signal(self):
        """Valid hiring signal should be accepted."""
        item = RSSItem(
            title="Senior Software Engineer",
            link="https://boards.greenhouse.io/acme/jobs/123",
            description="We're hiring a talented engineer to join our team!",
            pub_date=datetime.utcnow(),
            guid="job-123",
            feed_url="https://jobs.acme.com/feed",
        )
        
        result = ingest_rss_item(item)
        
        assert result.success is True
        assert result.signal is not None
        assert result.rejection is None
    
    def test_ingest_stale_signal_rejected(self):
        """Stale signal (> 30 days) should be rejected."""
        old_date = datetime.utcnow() - timedelta(days=45)
        
        item = RSSItem(
            title="Senior Software Engineer",
            link="https://boards.greenhouse.io/acme/jobs/123",
            description="We're hiring a talented engineer!",
            pub_date=old_date,
            guid="job-123",
            feed_url="https://jobs.acme.com/feed",
        )
        
        result = ingest_rss_item(item)
        
        assert result.success is False
        assert result.rejection is not None
        assert result.rejection.rule == RejectionRule.R2_STALE_SIGNAL
    
    def test_ingest_no_intent_rejected(self):
        """Signal without intent keywords should be rejected."""
        item = RSSItem(
            title="Company Picnic Photos",
            link="https://blog.acme.com/picnic",
            description="Here are photos from our annual company picnic!",
            pub_date=datetime.utcnow(),
            guid="blog-123",
            feed_url="https://blog.acme.com/feed",
        )
        
        result = ingest_rss_item(item)
        
        assert result.success is False
        assert result.rejection is not None
        assert result.rejection.rule == RejectionRule.R1_NO_INTENT_SIGNAL
    
    def test_ingest_empty_text_rejected(self):
        """Empty raw text should be rejected."""
        item = RSSItem(
            title="",
            link="https://jobs.acme.com/123",
            description="",
            pub_date=datetime.utcnow(),
            guid="job-123",
            feed_url="https://jobs.acme.com/feed",
        )
        
        result = ingest_rss_item(item)
        
        assert result.success is False
        assert result.rejection is not None


# =============================================================================
# BATCH INGESTION TESTS
# =============================================================================

class TestBatchIngestion:
    """Test batch ingestion of entire feeds."""
    
    def test_ingest_valid_feed(self):
        """Valid feed should produce accepted signals."""
        result = ingest_rss_feed(VALID_RSS_FEED, "https://jobs.acme.com/feed")
        
        # Both items have "hiring" or "looking for" keywords
        assert result.total_items == 2
        assert len(result.accepted) >= 1  # At least one should pass
    
    def test_ingest_stale_feed_all_rejected(self):
        """Feed with only stale items should reject all."""
        result = ingest_rss_feed(STALE_RSS_FEED, "https://jobs.oldcompany.com/feed")
        
        assert result.total_items == 1
        assert len(result.accepted) == 0
        assert len(result.rejected) == 1
        assert result.rejected[0].rule == RejectionRule.R2_STALE_SIGNAL
    
    def test_ingest_no_intent_feed_rejected(self):
        """Feed without intent signals should reject all."""
        result = ingest_rss_feed(NO_INTENT_RSS_FEED, "https://blog.company.com/feed")
        
        assert result.total_items == 1
        assert len(result.accepted) == 0
        assert len(result.rejected) == 1
        assert result.rejected[0].rule == RejectionRule.R1_NO_INTENT_SIGNAL
    
    def test_deduplication(self):
        """Duplicate items should be skipped."""
        seen_hashes: set[str] = set()
        
        # First ingestion
        result1 = ingest_rss_feed(VALID_RSS_FEED, "https://jobs.acme.com/feed", seen_hashes)
        accepted_count_1 = len(result1.accepted)
        
        # Second ingestion of same feed - should skip duplicates
        result2 = ingest_rss_feed(VALID_RSS_FEED, "https://jobs.acme.com/feed", seen_hashes)
        
        # Second run should have 0 new accepted (all skipped as dupes)
        assert len(result2.accepted) == 0
    
    def test_malformed_feed_returns_empty(self):
        """Malformed feed should return empty result, not crash."""
        result = ingest_rss_feed(MALFORMED_RSS, "https://broken.com/feed")
        
        assert result.total_items == 0
        assert len(result.accepted) == 0
        assert len(result.rejected) == 0


# =============================================================================
# EVIDENCE INVARIANT TESTS
# =============================================================================

class TestEvidenceInvariants:
    """Verify Phase 0 Evidence invariants are maintained."""
    
    def test_accepted_signal_can_produce_evidence(self):
        """Accepted signal should be convertible to Evidence Object."""
        item = RSSItem(
            title="Senior Software Engineer",
            link="https://boards.greenhouse.io/acme/jobs/123",
            description="We're hiring a talented engineer to join our team!",
            pub_date=datetime.utcnow(),
            guid="job-123",
            feed_url="https://jobs.acme.com/feed",
        )
        
        result = ingest_rss_item(item)
        assert result.success is True
        
        # Signal should be able to produce Evidence
        evidence = result.signal.to_evidence()
        
        assert evidence.evidence_id.startswith("evt_")
        assert evidence.meta.source_url == "https://boards.greenhouse.io/acme/jobs/123"
        assert evidence.meta.confidence == 0.95  # OBS default
    
    def test_rejection_has_audit_trail(self):
        """Rejection should have complete audit information."""
        item = RSSItem(
            title="Company Picnic",
            link="https://blog.acme.com/picnic",
            description="Annual picnic photos",
            pub_date=datetime.utcnow(),
            guid="blog-123",
            feed_url="https://blog.acme.com/feed",
        )
        
        result = ingest_rss_item(item)
        assert result.success is False
        
        rejection = result.rejection
        assert rejection.rejection_id is not None
        assert rejection.rule is not None
        assert rejection.reason is not None
        assert rejection.raw_signal_snippet is not None
        assert rejection.timestamp is not None


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
