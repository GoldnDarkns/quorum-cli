"""Unit tests for SPAR Plausibility Gate."""

from __future__ import annotations

from quorum.methods.spar_plausibility_gate import (
    evaluate_plausibility_gate,
    format_plausibility_gate_summary,
    parse_moderator_output,
)

CONSENSUS_OK = """```json
{
  "type": "consensus_scenario",
  "direction": "negative",
  "plausibility_score": 78,
  "consensus_summary": "Tariff shock drives risk-off via trade policy uncertainty and supply chain disruption."
}
```

```json
{
  "type": "minority_dissent",
  "plausibility_score": 65,
  "preserved_dissent_summary": "Tail risk from retaliation."
}
```"""

CONSENSUS_LOW = """```json
{
  "type": "consensus_scenario",
  "direction": "negative",
  "plausibility_score": 42,
  "consensus_summary": "Weak internal consistency."
}
```"""


def test_parse_moderator_output_extracts_both_objects():
    consensus, dissent = parse_moderator_output(CONSENSUS_OK)
    assert consensus is not None
    assert dissent is not None
    assert consensus["type"] == "consensus_scenario"
    assert dissent["type"] == "minority_dissent"


def test_gate_passes_above_threshold():
    decision, _fsr = evaluate_plausibility_gate(
        CONSENSUS_OK, threshold=60, fsr_enabled=False
    )
    assert decision.passed is True
    assert decision.action == "proceed"
    assert decision.consensus_score == 78.0


def test_gate_fails_below_threshold():
    decision, _fsr = evaluate_plausibility_gate(
        CONSENSUS_LOW, threshold=60, fsr_enabled=False
    )
    assert decision.passed is False
    assert decision.action == "human_review"
    assert "human review" in decision.reason.lower()


def test_gate_disabled_auto_proceeds():
    decision, _fsr = evaluate_plausibility_gate(
        CONSENSUS_LOW, threshold=60, enabled=False
    )
    assert decision.passed is True
    assert decision.action == "proceed"


def test_format_summary_mentions_gate():
    decision, fsr = evaluate_plausibility_gate(
        CONSENSUS_LOW,
        threshold=60,
        scenario_id="liberation_day_2025",
    )
    summary = format_plausibility_gate_summary(decision, fsr)
    assert "Plausibility Gate" in summary
    assert "human review" in summary.lower()
