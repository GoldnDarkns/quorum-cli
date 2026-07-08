"""Tests for SPAR model benchmark comparative analysis."""

from __future__ import annotations

from quorum.methods.spar_model_benchmarks import (
    build_analysis_report,
    format_benchmark_report,
    models_for_preset,
    recommend_role_swaps,
)


def test_demo_diverse_has_six_stack_models():
    profiles = models_for_preset("demo-diverse", include_frontier=False)
    assert len(profiles) == 6
    roles = {p.spar_role for p in profiles}
    assert "Economic" in roles
    assert "Moderator" in roles


def test_analysis_report_includes_benchmarks_and_frontier():
    report = build_analysis_report("demo-diverse")
    assert len(report["benchmarks"]) == 6
    assert len(report["stack_ranking"]) == 6
    assert len(report["frontier_reference"]) >= 2
    assert report["swap_recommendations"]


def test_format_report_mentions_swap_recommendations():
    text = format_benchmark_report("demo-diverse")
    assert "SPAR Model Benchmark Analysis" in text
    assert "Role swap recommendations" in text
    assert "qwen2.5:7b" in text


def test_recommend_role_swaps_returns_all_roles():
    recs = recommend_role_swaps("demo-diverse")
    assert len(recs) == 6
    assert all("role" in r and "current_model" in r for r in recs)
