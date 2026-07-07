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
from .spar_layer0 import (
    Layer0State,
    build_agent_system_prompt,
    resolve_master_context,
    run_layer0_pipeline,
)

MODERATOR_USER_INSTRUCTION = """Synthesise the SPAR debate below. You did NOT participate in the debate.

Shock scenario:
{shock}

=== LAYER 0 ACTIVATED TRANSMISSION CHANNELS ===
{layer0_channels}

=== ROUND 1 — Independent forecasts ===
{round1}

=== ROUND 2 — Live cross-examination ===
{round2}

INSTRUCTIONS:
Produce exactly TWO JSON objects separated by ONE blank line. No markdown fences. No prose before or after.

Object 1 — consensus_scenario:
{{
  "type": "consensus_scenario",
  "direction": "negative|positive|neutral",
  "magnitude_pct": {{"SP500": float, "XLE": float, "XLF": float, "XLK": float, "ITA": float, "XLY": float}},
  "confidence": float,
  "primary_transmission_channels": ["channel names from Layer 0"],
  "plausibility_score": 0-100,
  "consensus_summary": "2-4 sentences"
}}

Object 2 — minority_dissent:
{{
  "type": "minority_dissent",
  "dissenting_agents": ["roles"],
  "dissent_direction": "negative|positive|neutral",
  "magnitude_pct": {{"SP500": float, ...}},
  "preserved_dissent_summary": "one paragraph on tail risk the majority overruled",
  "plausibility_score": 0-100
}}

Base plausibility on channel consistency, internal logic, and fit with the Apr 2025 / event regime. Score honestly if the debate was weak."""

ROUND2_LIVE_DEBATE_INSTRUCTION = """LIVE DEBATE — Round 2 (sequential panel).

You are the {role_label} specialist. Read the full transcript below — including what other agents already said in THIS round before you.

=== DEBATE TRANSCRIPT ===
{transcript}
=== END TRANSCRIPT ===

Respond in clear prose (3–6 short paragraphs). This is a live war-room debate, NOT a JSON report.

You MUST:
1) Name at least one other agent by role (POLITICAL, ECONOMIC, ENVIRONMENTAL, SOCIAL, or DEVILS_ADVOCATE) and reference their specific claim from the transcript.
2) Explain where you agree and where you disagree, using evidence from your Layer 0 packet or Master Context.
3) If you change your Round 1 view, state what changed and cite a transmission channel — not just "I heard another agent."
4) Address the panel directly (e.g. "Economic agent, your oil channel assumes…").

Do NOT output JSON. Write as if speaking aloud in the room."""

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

    channel_assessment = parsed.get("channel_assessment")
    if isinstance(channel_assessment, dict):
        primary = channel_assessment.get("primary_channel", "N/A")
        parts.append(f"\n**Primary channel:** {primary}")
    else:
        analogue = parsed.get("analogue_assessment")
        if isinstance(analogue, dict):
            primary = analogue.get("primary_analogue", "N/A")
            parts.append(f"\n**Analogue:** {primary}")

    response_to = parsed.get("response_to")
    if response_to:
        parts.append(f"\n**Response to peers:**\n{json.dumps(response_to, indent=2)}")

    conclusion = parsed.get("conclusion")
    if isinstance(conclusion, dict):
        overall = conclusion.get("overall_impact")
        if overall and not direction:
            parts.append(f"**Direction:** {overall}")
        reasoning = conclusion.get("reasoning")
        if reasoning:
            parts.append(f"**Reasoning:** {reasoning}")

    assessment = parsed.get("round_1_assessment")
    if isinstance(assessment, dict) and len(parts) < 3:
        parts.append("**Domain assessment:**")
        parts.append(json.dumps(assessment, indent=2)[:2500])

    assessment = parsed.get("assessment")
    if isinstance(assessment, dict) and len(parts) < 3:
        parts.append("**Domain assessment:**")
        parts.append(json.dumps(assessment, indent=2)[:2500])

    analysis = parsed.get("analysis")
    if isinstance(analysis, dict) and len(parts) < 3:
        parts.append("**Domain analysis:**")
        parts.append(json.dumps(analysis, indent=2)[:2500])

    if not parts:
        compact = json.dumps(parsed, indent=2)
        return compact[:4000] if len(compact) > 4000 else compact

    return "\n".join(parts)


def _build_round1_transcript(round1_displays: dict[str, str]) -> str:
    """Human-readable Round 1 transcript for live debate."""
    sections: list[str] = ["=== ROUND 1 — Independent analyses ===\n"]
    for _role_key, agent_id, _prompt_file, ipc_role in SPAR_AGENT_SPECS:
        body = round1_displays.get(agent_id, "(no output)")
        sections.append(f"--- {ipc_role} ---\n{body}\n")
    return "\n".join(sections)


def _role_label(ipc_role: str) -> str:
    return ipc_role.replace("_", " ").title()


def build_moderator_user_message(
    task: str,
    layer0: Layer0State,
    round1_displays: dict[str, str],
    round2_results: dict[str, Any],
) -> str:
    """Readable moderator input — avoids dumping huge nested JSON blobs."""
    channel_lines = [
        f"- {ch['name']} [{ch['priority']}, score {ch['score']}]"
        for ch in layer0.to_dict().get("activated_channels", [])
    ]
    round2_sections: list[str] = []
    for _role_key, agent_id, _prompt_file, ipc_role in SPAR_AGENT_SPECS:
        entry = round2_results.get(agent_id, {})
        body = entry.get("live_response", "(no round 2 output)") if isinstance(entry, dict) else str(entry)
        round2_sections.append(f"--- {ipc_role} ---\n{body}\n")

    return MODERATOR_USER_INSTRUCTION.format(
        shock=task.strip()[:800],
        layer0_channels="\n".join(channel_lines) or layer0.summary_text[:2000],
        round1=_build_round1_transcript(round1_displays)[:12000],
        round2="\n".join(round2_sections)[:12000],
    )


class SparMethod(BaseMethodOrchestrator):
    """SPAR: Layer 0 channel-first RAG, then five specialists debate, then moderator.

    Phase 1: Layer 0 — transmission channel prioritization and evidence routing
    Phase 2: Round 1 — independent domain analysis (JSON)
    Phase 3: Round 2 — live sequential debate (agents read and respond to each other)
    Phase 4: Moderator synthesis
    """

    @property
    def method_name(self) -> str:
        return "spar"

    @property
    def total_phases(self) -> int:
        return 4

    def _model_for_role(self, role_key: str) -> str:
        if self.role_assignments and role_key in self.role_assignments:
            return self.role_assignments[role_key][0]
        role_names = [spec[0] for spec in SPAR_AGENT_SPECS] + ["Moderator"]
        if role_key in role_names:
            idx = role_names.index(role_key)
            return self.model_ids[idx % len(self.model_ids)]
        return self.model_ids[0]

    def _system_for_agent(self, layer0: Layer0State, role_key: str, prompt_file: str, task: str) -> str:
        master = resolve_master_context(task or layer0.shock_text, _prompts_dir())
        agent_prompt = _load_prompt(prompt_file)
        return build_agent_system_prompt(master, layer0, role_key, agent_prompt)

    async def run_stream(self, task: str) -> AsyncIterator[MessageType]:
        """Run SPAR with Layer 0 pipeline, then debate with live UI streaming."""
        self._original_task = task
        round1_results: dict[str, Any] = {}
        round1_displays: dict[str, str] = {}
        round2_results: dict[str, Any] = {}
        debate_transcript: list[str] = []

        # === PHASE 1: Layer 0 — channel-first evidence pipeline ===
        yield self._create_phase_marker(1)
        layer0 = run_layer0_pipeline(task)
        self._message_count += 1
        yield self._create_team_message(
            self.model_ids[0],
            layer0.summary_text,
            "LAYER0",
            round_type="layer0",
        )

        # === PHASE 2: Round 1 ===
        yield self._create_phase_marker(2)

        for role_key, agent_id, prompt_file, ipc_role in SPAR_AGENT_SPECS:
            model_id = self._model_for_role(role_key)
            yield ThinkingIndicator(model=model_id)

            system = self._system_for_agent(layer0, role_key, prompt_file, task)
            user_msg = task.strip() or layer0.shock_text
            user_msg = f"{user_msg}\n\nProduce your Round 1 JSON output now. JSON only."
            if "json" not in user_msg.lower():
                user_msg = f"{user_msg}\n\nJSON only."

            raw = await self._get_model_response(model_id, system, user_msg)

            parsed: dict[str, Any] | None = None
            try:
                parsed = _parse_json_response(raw)
                round1_results[agent_id] = parsed
            except (json.JSONDecodeError, ValueError) as exc:
                round1_results[agent_id] = {"parse_error": str(exc), "raw_preview": raw[:500]}

            display = _format_agent_response(raw, parsed)
            round1_displays[agent_id] = display
            self._message_count += 1
            yield self._create_team_message(model_id, display, ipc_role, round_type="round1")

        # === PHASE 3: Round 2 — live sequential debate ===
        yield self._create_phase_marker(3)
        debate_transcript.append(_build_round1_transcript(round1_displays))
        debate_transcript.append("\n=== ROUND 2 — Live cross-examination ===\n")

        for role_key, agent_id, prompt_file, ipc_role in SPAR_AGENT_SPECS:
            model_id = self._model_for_role(role_key)
            yield ThinkingIndicator(model=model_id)

            system = self._system_for_agent(layer0, role_key, prompt_file, task)
            transcript_so_far = "\n".join(debate_transcript)
            round2_user = ROUND2_LIVE_DEBATE_INSTRUCTION.format(
                role_label=_role_label(ipc_role),
                transcript=transcript_so_far,
            )
            raw = await self._get_model_response(model_id, system, round2_user)

            round2_results[agent_id] = {"round": 2, "live_response": raw}
            debate_transcript.append(f"--- {ipc_role} (speaking now) ---\n{raw}\n")

            self._message_count += 1
            yield self._create_team_message(model_id, raw, ipc_role, round_type="round2")

        # === PHASE 4: Moderator ===
        yield self._create_phase_marker(4)

        moderator_model = self._model_for_role("Moderator")
        yield ThinkingIndicator(model=moderator_model)

        master = resolve_master_context(task or layer0.shock_text, _prompts_dir())
        mod = _load_prompt("moderator.txt")
        shared = build_agent_system_prompt(master, layer0, "Moderator", mod)
        user_msg = build_moderator_user_message(task, layer0, round1_displays, round2_results)
        synthesis = await self._get_model_response(moderator_model, shared, user_msg)
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
