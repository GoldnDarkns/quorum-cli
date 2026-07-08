"""Tests for SPAR artifact persistence."""

from __future__ import annotations

import json
from pathlib import Path

from quorum.methods.spar_artifacts import (
    SparRunSnapshot,
    build_model_map,
    persist_spar_run,
)
from quorum.methods.spar_layer0 import run_layer0_pipeline


def test_build_model_map_from_role_assignments():
    roles = {
        "Political": ["model-a"],
        "Economic": ["model-b"],
        "Environmental": ["model-c"],
        "Social": ["model-d"],
        "DevilsAdvocate": ["model-e"],
        "Moderator": ["model-f"],
    }
    mapping = build_model_map(["fallback"], roles)
    assert mapping["Political"] == "model-a"
    assert mapping["Moderator"] == "model-f"


def test_persist_spar_run_writes_expected_files(tmp_path: Path):
    task = "On April 2, 2025, the United States announced broad reciprocal tariffs."
    layer0 = run_layer0_pipeline(task, compact=True)
    snapshot = SparRunSnapshot(
        task=task,
        layer0=layer0,
        round1_results={
            "political_geopolitical": {"direction": "negative", "confidence": 0.8},
        },
        round1_raw={"political_geopolitical": '{"direction": "negative"}'},
        round1_displays={"political_geopolitical": "**Direction:** negative"},
        round2_results={
            "political_geopolitical": {"round": 2, "live_response": "I disagree with Economic."},
        },
        round2_raw={"political_geopolitical": "I disagree with Economic."},
        debate_transcript="=== ROUND 1 ===\n--- POLITICAL ---\nneg",
        moderator_raw='{"type": "consensus_scenario"}',
        model_map=build_model_map(["ollama:qwen2.5:7b"], None),
        plausibility_gate={"passed": True, "action": "proceed", "threshold": 60},
        dcs_history=[
            {
                "round_number": 2,
                "dcs_score": 0.42,
                "action": "exploit",
                "threshold": 0.35,
            }
        ],
        source="test",
        run_id="test_run_001",
    )

    run_dir = persist_spar_run(snapshot, output_root=tmp_path)
    assert run_dir.name == "run_test_run_001"
    assert (run_dir / "layer0.json").exists()
    assert (run_dir / "layer0_summary.txt").exists()
    assert (run_dir / "task.txt").exists()
    assert (run_dir / "round1_all.json").exists()
    assert (run_dir / "round1_displays.json").exists()
    assert (run_dir / "round2_all.json").exists()
    assert (run_dir / "live_debate_transcript.txt").exists()
    assert (run_dir / "moderator_raw.txt").exists()
    assert (run_dir / "dcs_scores.json").exists()
    assert (run_dir / "plausibility_gate.json").exists()
    assert (run_dir / "political_geopolitical_round1_raw.txt").exists()
    assert (run_dir / "political_geopolitical_round2_raw.txt").exists()

    manifest = json.loads((run_dir / "model_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == "test"
    assert manifest["scenario_id"] == "liberation_day_2025"
