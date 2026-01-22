"""
GlassBox CLI — Read-Only Interface for Lead Discovery.

Phase 5A: Public Alpha interface for running GlassBox locally.

Commands:
    glassbox run              — Execute full pipeline
    glassbox leads            — Show ranked leads
    glassbox explain <id>     — Show explanation for a lead
    glassbox evidence <id>    — Show evidence lineage

This CLI is READ-ONLY. It cannot:
    - Modify scoring logic
    - Change thresholds
    - Skip validation
    - Hide rejections

The interface must not be able to lie, tune, or hide reasoning.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from .pipeline import (
    run_pipeline,
    get_last_result,
    set_last_result,
    PipelineResult,
)
from ..ranking.scorer import RankedLead, LeadTier


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def format_tier_badge(tier: LeadTier) -> str:
    """Format tier as a visual badge."""
    badges = {
        LeadTier.TIER_A: "[A-TIER]",
        LeadTier.TIER_B: "[B-TIER]",
        LeadTier.TIER_C: "[C-TIER]",
        LeadTier.TIER_D: "[D-TIER]",
    }
    return badges.get(tier, "[?-TIER]")


def format_lead_row(lead_id: str, lead: RankedLead) -> str:
    """Format a single lead for display."""
    tier = format_tier_badge(lead.tier)
    company = lead.entity.get_name_value()
    domain = lead.entity.get_domain_value()
    score = lead.score
    
    return f"{tier} | Score: {score:>5.0f} | {company} ({domain}) | ID: {lead_id}"


def format_explanation(lead: RankedLead) -> str:
    """Format the full explanation for a lead."""
    return lead.get_explanation()


def format_evidence_lineage(lead: RankedLead) -> str:
    """Format the evidence lineage for a lead."""
    lines = []
    
    company = lead.entity.get_name_value()
    lines.append(f"Evidence Lineage for: {company}")
    lines.append("=" * 50)
    
    # Entity evidence
    lines.append("")
    lines.append("ENTITY EVIDENCE:")
    lines.append(f"  • company_name: {lead.entity.company_name.value}")
    lines.append(f"    ID: {lead.entity.company_name.evidence_id}")
    lines.append(f"    Type: {lead.entity.company_name.evidence_type.value}")
    lines.append(f"    Confidence: {lead.entity.company_name.meta.confidence:.0%}")
    
    lines.append("")
    lines.append(f"  • domain: {lead.entity.domain.value}")
    lines.append(f"    ID: {lead.entity.domain.evidence_id}")
    lines.append(f"    Type: {lead.entity.domain.evidence_type.value}")
    lines.append(f"    Confidence: {lead.entity.domain.meta.confidence:.0%}")
    
    if lead.entity.industry:
        lines.append("")
        lines.append(f"  • industry: {lead.entity.industry.value}")
        lines.append(f"    ID: {lead.entity.industry.evidence_id}")
        lines.append(f"    Inference rule: {lead.entity.industry.meta.inference_rule}")
    
    if lead.entity.size_estimate:
        lines.append("")
        lines.append(f"  • size_estimate: {lead.entity.size_estimate.value}")
        lines.append(f"    ID: {lead.entity.size_estimate.evidence_id}")
        lines.append(f"    Inference rule: {lead.entity.size_estimate.meta.inference_rule}")
    
    # Signal evidence
    if lead.signal:
        lines.append("")
        lines.append("SIGNAL EVIDENCE:")
        lines.append(f"  • Source: {lead.signal.source_url}")
        lines.append(f"  • Signal ID: {lead.signal.signal_id}")
        lines.append(f"  • Timestamp: {lead.signal.timestamp}")
        lines.append(f"  • Text: {lead.signal.raw_text[:200]}...")
    
    # Scoring components
    lines.append("")
    lines.append("SCORING COMPONENTS:")
    for component in lead.breakdown.components:
        sign = "+" if component.contribution >= 0 else ""
        lines.append(f"  • {component.name}: {sign}{component.contribution:.0f}")
        lines.append(f"    {component.reason}")
        if component.evidence_ids:
            lines.append(f"    Evidence: {', '.join(component.evidence_ids[:3])}")
    
    return "\n".join(lines)


# =============================================================================
# CLI COMMANDS
# =============================================================================

def cmd_run(args: argparse.Namespace) -> int:
    """Execute the full pipeline."""
    print("GlassBox Discovery Engine")
    print("=" * 50)
    print("Running pipeline...")
    print()
    
    try:
        result = run_pipeline()
        set_last_result(result)
        
        print(f"Pipeline completed at: {result.run_timestamp}")
        print()
        print("STATISTICS:")
        print(f"  Signals processed: {result.total_signals_processed}")
        print(f"  Signals accepted:  {result.signals_accepted}")
        print(f"  Signals rejected:  {result.signals_rejected}")
        print(f"  Entities resolved: {result.entities_resolved}")
        print(f"  Entities rejected: {result.entities_rejected}")
        print(f"  Final leads:       {len(result.ranked_leads)}")
        print()
        
        if result.rejections:
            print("REJECTIONS (for audit):")
            for rejection in result.rejections[:5]:  # Show first 5
                print(f"  • [{rejection.rule.value}] {rejection.reason[:60]}...")
            if len(result.rejections) > 5:
                print(f"  ... and {len(result.rejections) - 5} more")
            print()
        
        print("Run 'glassbox leads' to see ranked leads.")
        return 0
        
    except Exception as e:
        print(f"ERROR: Pipeline failed")
        print(f"Reason: {e}")
        return 1


def cmd_leads(args: argparse.Namespace) -> int:
    """Show ranked leads."""
    result = get_last_result()
    
    if result is None:
        print("No pipeline results available.")
        print("Run 'glassbox run' first.")
        return 1
    
    print("GlassBox — Ranked Leads")
    print("=" * 70)
    print()
    
    if not result.ranked_leads:
        print("No leads found.")
        return 0
    
    lead_ids = result.get_lead_ids()
    
    for lead_id, lead in lead_ids:
        print(format_lead_row(lead_id, lead))
    
    print()
    print(f"Total: {len(result.ranked_leads)} leads")
    print()
    print("Use 'glassbox explain <id>' for detailed explanation.")
    
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Show explanation for a specific lead."""
    result = get_last_result()
    
    if result is None:
        print("No pipeline results available.")
        print("Run 'glassbox run' first.")
        return 1
    
    lead_id = args.lead_id
    lead = result.get_lead_by_id(lead_id)
    
    if lead is None:
        print(f"Lead not found: {lead_id}")
        print()
        print("Available leads:")
        for lid, l in result.get_lead_ids():
            print(f"  {lid} — {l.entity.get_name_value()}")
        return 1
    
    print("GlassBox — Lead Explanation")
    print("=" * 50)
    print()
    print(format_explanation(lead))
    
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    """Show evidence lineage for a specific lead."""
    result = get_last_result()
    
    if result is None:
        print("No pipeline results available.")
        print("Run 'glassbox run' first.")
        return 1
    
    lead_id = args.lead_id
    lead = result.get_lead_by_id(lead_id)
    
    if lead is None:
        print(f"Lead not found: {lead_id}")
        print()
        print("Available leads:")
        for lid, l in result.get_lead_ids():
            print(f"  {lid} — {l.entity.get_name_value()}")
        return 1
    
    print(format_evidence_lineage(lead))
    
    return 0


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="glassbox",
        description="GlassBox Discovery Engine — Explainable Lead Discovery",
    )
    
    subparsers = parser.add_subparsers(
        title="commands",
        description="Available commands",
        dest="command",
    )
    
    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Execute the full pipeline",
    )
    run_parser.set_defaults(func=cmd_run)
    
    # Leads command
    leads_parser = subparsers.add_parser(
        "leads",
        help="Show ranked leads",
    )
    leads_parser.set_defaults(func=cmd_leads)
    
    # Explain command
    explain_parser = subparsers.add_parser(
        "explain",
        help="Show explanation for a lead",
    )
    explain_parser.add_argument(
        "lead_id",
        help="Lead ID to explain",
    )
    explain_parser.set_defaults(func=cmd_explain)
    
    # Evidence command
    evidence_parser = subparsers.add_parser(
        "evidence",
        help="Show evidence lineage for a lead",
    )
    evidence_parser.add_argument(
        "lead_id",
        help="Lead ID to show evidence for",
    )
    evidence_parser.set_defaults(func=cmd_evidence)
    
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    if args.command is None:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
