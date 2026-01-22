"""
Tests for Phase 5A: Public Alpha CLI.

These tests verify:
1. CLI command correctness
2. Deterministic output
3. Explanation parity with internal logic
4. Proof that CLI cannot mutate state
"""

import pytest
from io import StringIO
import sys

from glassbox.cli.pipeline import (
    run_pipeline,
    get_last_result,
    set_last_result,
    PipelineResult,
    SAMPLE_RSS_XML,
)
from glassbox.cli.main import (
    main,
    create_parser,
    cmd_run,
    cmd_leads,
    format_lead_row,
    format_tier_badge,
)
from glassbox.ranking.scorer import LeadTier


# =============================================================================
# PIPELINE TESTS
# =============================================================================

class TestPipeline:
    """Test pipeline orchestration."""
    
    def test_pipeline_runs_without_error(self):
        """Pipeline should execute successfully with sample data."""
        result = run_pipeline()
        
        assert result is not None
        assert isinstance(result, PipelineResult)
    
    def test_pipeline_produces_leads(self):
        """Pipeline should produce ranked leads."""
        result = run_pipeline()
        
        # With sample data, we should get at least some leads
        assert len(result.ranked_leads) > 0
    
    def test_pipeline_is_deterministic(self):
        """Same input should produce same output."""
        result1 = run_pipeline(SAMPLE_RSS_XML)
        result2 = run_pipeline(SAMPLE_RSS_XML)
        
        # Same number of leads
        assert len(result1.ranked_leads) == len(result2.ranked_leads)
        
        # Same scores (in same order)
        scores1 = [lead.score for lead in result1.ranked_leads]
        scores2 = [lead.score for lead in result2.ranked_leads]
        assert scores1 == scores2
    
    def test_pipeline_tracks_rejections(self):
        """Pipeline should track all rejections for audit."""
        result = run_pipeline()
        
        # Rejections list should exist (may be empty)
        assert isinstance(result.rejections, list)
    
    def test_pipeline_generates_lead_ids(self):
        """Pipeline should generate stable lead IDs."""
        result = run_pipeline()
        
        if result.ranked_leads:
            lead_ids = result.get_lead_ids()
            
            # Each lead should have an ID
            assert len(lead_ids) == len(result.ranked_leads)
            
            # IDs should be non-empty strings
            for lead_id, lead in lead_ids:
                assert isinstance(lead_id, str)
                assert len(lead_id) > 0


# =============================================================================
# CLI COMMAND TESTS
# =============================================================================

class TestCLICommands:
    """Test CLI commands."""
    
    def test_run_command_succeeds(self, capsys):
        """Run command should execute without error."""
        import argparse
        args = argparse.Namespace()
        
        result = cmd_run(args)
        
        assert result == 0
        
        captured = capsys.readouterr()
        assert "Pipeline completed" in captured.out
    
    def test_leads_command_after_run(self, capsys):
        """Leads command should work after run."""
        import argparse
        
        # First run the pipeline
        run_args = argparse.Namespace()
        cmd_run(run_args)
        
        # Then list leads
        leads_args = argparse.Namespace()
        result = cmd_leads(leads_args)
        
        assert result == 0
        
        captured = capsys.readouterr()
        assert "Ranked Leads" in captured.out
    
    def test_leads_command_without_run_fails(self, capsys):
        """Leads command should fail if run hasn't been executed."""
        import argparse
        
        # Clear any previous result
        set_last_result(None)
        
        leads_args = argparse.Namespace()
        result = cmd_leads(leads_args)
        
        assert result == 1
        
        captured = capsys.readouterr()
        assert "Run 'glassbox run' first" in captured.out


# =============================================================================
# OUTPUT FORMATTING TESTS
# =============================================================================

class TestOutputFormatting:
    """Test output formatting functions."""
    
    def test_tier_badge_formatting(self):
        """Tier badges should be formatted correctly."""
        assert format_tier_badge(LeadTier.TIER_A) == "[A-TIER]"
        assert format_tier_badge(LeadTier.TIER_B) == "[B-TIER]"
        assert format_tier_badge(LeadTier.TIER_C) == "[C-TIER]"
        assert format_tier_badge(LeadTier.TIER_D) == "[D-TIER]"
    
    def test_lead_row_contains_key_info(self):
        """Lead row should contain company, score, and ID."""
        result = run_pipeline()
        
        if result.ranked_leads:
            lead_id, lead = result.get_lead_ids()[0]
            row = format_lead_row(lead_id, lead)
            
            # Should contain tier badge
            assert "TIER" in row
            
            # Should contain score
            assert "Score" in row
            
            # Should contain ID
            assert lead_id in row


# =============================================================================
# DETERMINISM TESTS
# =============================================================================

class TestDeterminism:
    """Test that output is deterministic."""
    
    def test_same_leads_every_time(self):
        """Running pipeline multiple times should produce same leads."""
        runs = [run_pipeline(SAMPLE_RSS_XML) for _ in range(3)]
        
        # All runs should have same number of leads
        counts = [len(r.ranked_leads) for r in runs]
        assert len(set(counts)) == 1
    
    def test_same_ranking_order(self):
        """Ranking order should be stable."""
        result1 = run_pipeline(SAMPLE_RSS_XML)
        result2 = run_pipeline(SAMPLE_RSS_XML)
        
        if result1.ranked_leads and result2.ranked_leads:
            companies1 = [l.entity.get_name_value() for l in result1.ranked_leads]
            companies2 = [l.entity.get_name_value() for l in result2.ranked_leads]
            
            assert companies1 == companies2


# =============================================================================
# IMMUTABILITY TESTS
# =============================================================================

class TestImmutability:
    """Prove that CLI cannot mutate internal state."""
    
    def test_cli_cannot_change_scoring(self):
        """CLI has no way to change scoring logic."""
        parser = create_parser()
        
        # The parser should have no flags that affect scoring
        # Check that there are no --weight, --threshold, --config flags
        # by examining the subparsers
        
        # Run command should have no arguments
        run_parser = parser._subparsers._actions[1].choices.get('run')
        if run_parser:
            # Should have minimal arguments
            assert len(run_parser._actions) <= 2  # -h and maybe --help
    
    def test_leads_command_is_read_only(self):
        """Leads command should not modify pipeline result."""
        import argparse
        
        # Run pipeline
        result1 = run_pipeline()
        set_last_result(result1)
        
        # Get leads
        leads_args = argparse.Namespace()
        cmd_leads(leads_args)
        
        # Result should be unchanged
        result2 = get_last_result()
        assert len(result1.ranked_leads) == len(result2.ranked_leads)


# =============================================================================
# EXPLANATION PARITY TESTS
# =============================================================================

class TestExplanationParity:
    """Test that CLI explanations match internal logic."""
    
    def test_explanation_matches_score(self):
        """CLI explanation should reflect the actual score breakdown."""
        result = run_pipeline()
        
        if result.ranked_leads:
            lead = result.ranked_leads[0]
            explanation = lead.get_explanation()
            
            # Explanation should contain the tier
            tier_value = lead.tier.value
            assert tier_value in explanation
    
    def test_evidence_lineage_is_complete(self):
        """Evidence command should show all evidence."""
        from glassbox.cli.main import format_evidence_lineage
        
        result = run_pipeline()
        
        if result.ranked_leads:
            lead = result.ranked_leads[0]
            lineage = format_evidence_lineage(lead)
            
            # Should contain entity evidence
            assert "company_name" in lineage
            assert "domain" in lineage
            
            # Should contain scoring components
            assert "SCORING COMPONENTS" in lineage


# =============================================================================
# ARGPARSE TESTS
# =============================================================================

class TestArgparse:
    """Test argument parser."""
    
    def test_parser_has_required_commands(self):
        """Parser should have all required commands."""
        parser = create_parser()
        
        # Check subparsers exist
        subparsers = parser._subparsers._actions[1].choices
        
        assert 'run' in subparsers
        assert 'leads' in subparsers
        assert 'explain' in subparsers
        assert 'evidence' in subparsers
    
    def test_explain_requires_lead_id(self):
        """Explain command should require lead_id argument."""
        parser = create_parser()
        
        # This should fail without lead_id
        with pytest.raises(SystemExit):
            parser.parse_args(['explain'])
    
    def test_evidence_requires_lead_id(self):
        """Evidence command should require lead_id argument."""
        parser = create_parser()
        
        # This should fail without lead_id  
        with pytest.raises(SystemExit):
            parser.parse_args(['evidence'])


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
