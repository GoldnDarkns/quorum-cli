"""SPAR method: Scenario Planning via Agentic Reasoning."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, AsyncIterator

from .base import (
    BaseMethodOrchestrator,
    MessageType,
    SynthesisResult,
    ThinkingIndicator,
)

ROUND2_INSTRUCTION = """Round 2 — Cross-Examination.

Here are the Round 1 outputs from all agents:
{round1_json}

You must:
1) Identify one point of genuine agreement with at least one other agent, citing their specific claim.
2) Identify one factual or logical disagreement with at least one other agent, citing evidence from the Master Context.
3) If your direction or magnitude estimate changes from Round 1, your supporting_evidence must include a new data point that justifies the change — not just exposure to another agent's opinion.

Return updated JSON with round: 2 and a response_to field added. JSON only, no markdown fences."""

SPAR_AGENT_SPECS: list[tuple[str, str, str, str]] = [
    ("Political", "political_geopolitical", "agent1_political_geopolitical.txt", "POLITICAL"),
    ("Economic", "economic_fiscal_market", "agent2_economic_fiscal_market.txt", "ECONOMIC"),
    ("Environmental", "environmental_technology", "agent3_environmental_technology.txt", "ENVIRONMENTAL"),
    ("Social", "social_behavioural", "agent4_social_behavioural.txt", "SOCIAL"),
    ("DevilsAdvocate", "devils_advocate", "agent5_devils_advocate.txt", "DEVILS_ADVOCATE"),
]


def _prompts_dir() -> Path:
    candidates = [
        Path.cwd() / "Proejct Info" / "prompts",
        Path(__file__).resolve().parents[3] / "Proejct Info" / "prompts",
    ]
    for path in candidates:
        if (path / "master_context.txt").exists():
            return path
    raise FileNotFoundError(
        "SPAR prompts not found. Run from the quorum-cli repo root or run: "
        "python scripts/extract_spar_prompts.py"
    )


def _load_prompt(name: str) -> str:
    path = _prompts_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Missing SPAR prompt: {path}")
    return path.read_text(encoding="utf-8")


def _parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


def _format_agent_response(raw: str, parsed: dict[str, Any] | None) -> str:
    """Format structured SPAR JSON for readable terminal display."""
    if not parsed:
        return raw

    parts: list[str] = []
    direction = parsed.get("direction")
    if direction:
        parts.append(f"**Direction:** {direction}")
    confidence = parsed.get("confidence")
    if confidence is not None:
        parts.append(f"**Confidence:** {confidence}")

    magnitude = parsed.get("magnitude_pct")
    if isinstance(magnitude, dict):
        parts.append("**Magnitude estimates:**")
        for ticker, pct in magnitude.items():
            try:
                parts.append(f"- {ticker}: {float(pct):+.1f}%")
            except (TypeError, ValueError):
                parts.append(f"- {ticker}: {pct}")

    assumption = parsed.get("key_assumption")
    if assumption:
        parts.append(f"\n**Key assumption:** {assumption}")

    evidence = parsed.get("supporting_evidence")
    if isinstance(evidence, list) and evidence:
        parts.append("\n**Supporting evidence:**")
        for item in evidence[:4]:
            parts.append(f"- {item}")

    channels = parsed.get("transmission_channels")
    if isinstance(channels, list) and channels:
        parts.append("\n**Transmission channels:**")
        for item in channels[:3]:
            parts.append(f"- {item}")

    analogue = parsed.get("analogue_assessment")
    if isinstance(analogue, dict):
        primary = analogue.get("primary_analogue", "N/A")
        parts.append(f"\n**Analogue:** {primary}")

    response_to = parsed.get("response_to")
    if response_to:
        parts.append(f"\n**Response to peers:**\n{json.dumps(response_to, indent=2)}")

    return "\n".join(parts) if parts else raw


class SparMethod(BaseMethodOrchestrator):
    """SPAR: five domain specialists debate a geopolitical shock, then a moderator synthesizes.

    Phase 1: Round 1 — independent domain analysis (JSON)
    Phase 2: Round 2 — cross-examination and revision
    Phase 3: Moderator synthesis
    """

    @property
    def method_name(self) -> str:
        return "spar"

    @property
    def total_phases(self) -> int:
        return 3

    def _model_for_role(self, role_key: str) -> str:
        if self.role_assignments and role_key in self.role_assignments:
            return self.role_assignments[role_key][0]
        role_names = [spec[0] for spec in SPAR_AGENT_SPECS] + ["Moderator"]
        if role_key in role_names:
            idx = role_names.index(role_key)
            return self.model_ids[idx % len(self.model_ids)]
        return self.model_ids[0]

    async def run_stream(self, task: str) -> AsyncIterator[MessageType]:
        """Run SPAR debate with live UI streaming."""
        self._original_task = task
        round1_results: dict[str, Any] = {}
        round2_results: dict[str, Any] = {}

        # === PHASE 1: Round 1 ===
        yield self._create_phase_marker(1)

        for role_key, agent_id, prompt_file, ipc_role in SPAR_AGENT_SPECS:
            model_id = self._model_for_role(role_key)
            yield ThinkingIndicator(model=model_id)

            master = _load_prompt("master_context.txt")
            agent_prompt = _load_prompt(prompt_file)
            system = f"{master}\n\n{agent_prompt}"
            user_msg = task.strip() or "Produce your Round 1 JSON output now. JSON only."
            if "json" not in user_msg.lower():
                user_msg = f"{user_msg}\n\nProduce your Round 1 JSON output now. JSON only."

            raw = await self._get_model_response(model_id, system, user_msg)

            parsed: dict[str, Any] | None = None
            try:
                parsed = _parse_json_response(raw)
                round1_results[agent_id] = parsed
            except (json.JSONDecodeError, ValueError) as exc:
                round1_results[agent_id] = {"parse_error": str(exc), "raw_preview": raw[:500]}

            display = _format_agent_response(raw, parsed)
            self._message_count += 1
            yield self._create_team_message(model_id, display, ipc_role, round_type="round1")

        # === PHASE 2: Round 2 ===
        yield self._create_phase_marker(2)
        round1_blob = json.dumps(round1_results, indent=2)
        round2_user = ROUND2_INSTRUCTION.format(round1_json=round1_blob)

        for role_key, agent_id, prompt_file, ipc_role in SPAR_AGENT_SPECS:
            model_id = self._model_for_role(role_key)
            yield ThinkingIndicator(model=model_id)

            master = _load_prompt("master_context.txt")
            agent_prompt = _load_prompt(prompt_file)
            system = f"{master}\n\n{agent_prompt}"
            raw = await self._get_model_response(model_id, system, round2_user)

            parsed = None
            try:
                parsed = _parse_json_response(raw)
                round2_results[agent_id] = parsed
            except (json.JSONDecodeError, ValueError) as exc:
                round2_results[agent_id] = {"parse_error": str(exc), "raw_preview": raw[:500]}

            display = _format_agent_response(raw, parsed)
            self._message_count += 1
            yield self._create_team_message(model_id, display, ipc_role, round_type="round2")

        # === PHASE 3: Moderator ===
        yield self._create_phase_marker(3)

        moderator_model = self._model_for_role("Moderator")
        yield ThinkingIndicator(model=moderator_model)

        master = _load_prompt("master_context.txt")
        mod = _load_prompt("moderator.txt")
        system = f"{master}\n\n{mod}"
        transcript = {"round1": round1_results, "round2": round2_results}
        user_msg = f"Full debate transcript:\n{json.dumps(transcript, indent=2)}"
        synthesis = await self._get_model_response(moderator_model, system, user_msg)
        self._message_count += 1

        self._synthesis_result = SynthesisResult(
            consensus="PARTIAL",
            synthesis=synthesis,
            differences="See moderator synthesis for dissenting views.",
            raw_content=synthesis,
            synthesizer_model=moderator_model,
            message_count=self._message_count,
            method="spar",
        )
        yield self._synthesis_result
