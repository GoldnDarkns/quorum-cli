"""SPAR method: Scenario Planning via Agentic Reasoning."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, AsyncIterator

from .base import (
    BaseMethodOrchestrator,
    HumanReviewRequired,
    MessageType,
    SynthesisResult,
    ThinkingIndicator,
)
from ..config import get_settings
from .spar_artifacts import (
    SparRunSnapshot,
    build_model_map,
    maybe_persist_spar_run,
)
from .spar_dcs import compute_dcs, format_dcs_summary
from .spar_plausibility_gate import (
    evaluate_plausibility_gate,
    format_plausibility_gate_summary,
    parse_moderator_output,
)
from .spar_layer3 import (
    format_layer3_summary,
    format_portfolio_recommendation,
    run_layer3_quantification,
    save_layer3_artifacts,
)
from .spar_model_benchmarks import build_analysis_report, format_benchmark_report
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

LIVE_DEBATE_ROUND_INSTRUCTION = """LIVE DEBATE — Round {round_num} (sequential panel).

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

# Backward-compatible alias
ROUND2_LIVE_DEBATE_INSTRUCTION = LIVE_DEBATE_ROUND_INSTRUCTION

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


def _format_magnitude_block(magnitude: Any) -> list[str]:
    if not isinstance(magnitude, dict):
        return []
    lines: list[str] = []
    for ticker, pct in magnitude.items():
        try:
            lines.append(f"  - {ticker}: {float(pct):+.2f}%")
        except (TypeError, ValueError):
            lines.append(f"  - {ticker}: {pct}")
    return lines


def format_moderator_synthesis(raw: str) -> str:
    """Readable Moderator output for terminal display (consensus + dissent)."""
    consensus, dissent = parse_moderator_output(raw)
    if not consensus and not dissent:
        return raw

    lines: list[str] = ["**Moderator synthesis (Layer 2)**", ""]
    if consensus:
        lines.append("**Consensus scenario (majority view after debate)**")
        direction = consensus.get("direction")
        if direction:
            lines.append(f"- Direction: **{direction}**")
        confidence = consensus.get("confidence")
        if confidence is not None:
            lines.append(f"- Confidence: {confidence}")
        plausibility = consensus.get("plausibility_score")
        if plausibility is not None:
            lines.append(f"- Moderator plausibility self-score: **{plausibility}** / 100")
        channels = consensus.get("primary_transmission_channels")
        if isinstance(channels, list) and channels:
            lines.append("- Primary transmission channels:")
            for ch in channels[:5]:
                lines.append(f"  - {ch}")
        mag_lines = _format_magnitude_block(consensus.get("magnitude_pct"))
        if mag_lines:
            lines.append("- Magnitude estimates (5-day):")
            lines.extend(mag_lines)
        summary = consensus.get("consensus_summary")
        if summary:
            lines.append(f"- Summary: {summary}")
        lines.append("")

    if dissent:
        lines.append("**Minority dissent (tail risk preserved — not overruled)**")
        agents = dissent.get("dissenting_agents")
        if isinstance(agents, list) and agents:
            lines.append(f"- Dissenting agents: {', '.join(str(a) for a in agents)}")
        direction = dissent.get("dissent_direction")
        if direction:
            lines.append(f"- Dissent direction: **{direction}**")
        plausibility = dissent.get("plausibility_score")
        if plausibility is not None:
            lines.append(f"- Dissent plausibility score: **{plausibility}** / 100")
        mag_lines = _format_magnitude_block(dissent.get("magnitude_pct"))
        if mag_lines:
            lines.append("- Dissent magnitude estimates:")
            lines.extend(mag_lines)
        summary = dissent.get("preserved_dissent_summary")
        if summary:
            lines.append(f"- Summary: {summary}")

    return "\n".join(lines)


def format_spar_pipeline_summary(
    *,
    dcs_enabled: bool,
    dcs_history: list[dict[str, Any]],
    gate_decision: Any,
    layer3_ran: bool,
    artifact_dir: Path | None,
    debate_rounds: dict[int, dict[str, Any]],
) -> str:
    """Explain what happened after the live debate — DCS, gate, Layer 3, artifacts."""
    lines = [
        "**SPAR pipeline summary (what happens next)**",
        "",
        "Round 1 domain analysis is done by **five independent specialists** "
        "(Political, Economic, Environmental, Social, Devil's Advocate) — "
        "not a moderator. The **Moderator** only runs once, after live debate, "
        "to merge their views into consensus + dissent.",
        "",
    ]

    live_rounds = sorted(debate_rounds.keys())
    if not dcs_enabled:
        lines.append(
            "- **DCS (Debate Continuation Score):** disabled — one live debate round, "
            "then Moderator synthesis."
        )
    elif dcs_history:
        last = dcs_history[-1]
        action = str(last.get("action", "exploit")).upper()
        rnd = last.get("round_number", live_rounds[-1] if live_rounds else 2)
        max_r = last.get("max_rounds", 5)
        score = last.get("dcs_score", last.get("score"))
        lines.append(f"- **Live debate rounds completed:** {len(live_rounds)} (rounds {live_rounds})")
        lines.append(
            f"- **DCS after Round {rnd}:** score {score} — decision **{action}**"
        )
        lines.append(f"  - {last.get('reason', 'Debate continuation evaluated.')}")
        if action == "EXPLORE" and len(live_rounds) < max_r:
            lines.append(
                f"  - Another live round would run (up to round {max_r}). "
                "Scroll up for the DCS block before Moderator synthesis."
            )
        else:
            lines.append(
                "  - No further live rounds — passed to **Moderator** for consensus + dissent."
            )
    else:
        lines.append("- **DCS:** no decision recorded.")

    lines.append("")
    if gate_decision.passed:
        score_note = (
            gate_decision.composite_score
            if gate_decision.composite_score is not None
            else gate_decision.consensus_score
        )
        lines.append(
            f"- **Plausibility gate:** **CLEARED** "
            f"(score {score_note if score_note is not None else 'n/a'}/100, "
            f"threshold {gate_decision.threshold:.0f})."
        )
        if layer3_ran:
            lines.append("- **Layer 3 quantification:** ran (sector P&L, VaR, Fama-French factors).")
            lines.append("- **Portfolio recommendation:** hedge overlay + rebalance trades (see Layer 3 block).")
        else:
            lines.append(
                "- **Layer 3 quantification:** skipped "
                "(enable SPAR_LAYER3_ENABLED and pass plausibility gate)."
            )
    else:
        lines.append(
            f"- **Plausibility gate:** **HUMAN REVIEW** — {gate_decision.reason}"
        )
        lines.append("- **Layer 3 quantification:** blocked until review.")

    if artifact_dir:
        lines.append(f"- **Research artifacts saved:** `{artifact_dir}`")

    lines.append("")
    lines.append(
        "_**Why 'consensus + dissent'?** SPAR always preserves minority tail-risk views "
        "alongside the majority scenario. That is intentional — not a failed debate. "
        "Check the Plausibility Gate and Layer 3 blocks above for the validated output._"
    )
    return "\n".join(lines)


def _spar_consensus_status(gate_decision: Any, gate_enabled: bool) -> str:
    if gate_enabled and not gate_decision.passed:
        return "HUMAN_REVIEW"
    return "CLEARED"


def _role_label(ipc_role: str) -> str:
    return ipc_role.replace("_", " ").title()


def _cap_transcript(text: str, limit: int = 10000) -> str:
    if len(text) <= limit:
        return text
    return f"...[transcript truncated — showing last {limit} chars]...\n{text[-limit:]}"


def build_moderator_user_message(
    task: str,
    layer0: Layer0State,
    round1_displays: dict[str, str],
    round2_results: dict[str, Any] | None = None,
    debate_rounds: dict[int, dict[str, Any]] | None = None,
) -> str:
    """Readable moderator input — avoids dumping huge nested JSON blobs."""
    channel_lines = [
        f"- {ch['name']} [{ch['priority']}, score {ch['score']}]"
        for ch in layer0.to_dict().get("activated_channels", [])
    ]
    round2_sections: list[str] = []
    if debate_rounds:
        for rnd in sorted(debate_rounds):
            round2_sections.append(f"=== ROUND {rnd} — Live cross-examination ===")
            for _role_key, agent_id, _prompt_file, ipc_role in SPAR_AGENT_SPECS:
                entry = debate_rounds[rnd].get(agent_id, {})
                body = (
                    entry.get("live_response", "(no output)")
                    if isinstance(entry, dict)
                    else str(entry)
                )
                round2_sections.append(f"--- {ipc_role} ---\n{body}\n")
    elif round2_results:
        for _role_key, agent_id, _prompt_file, ipc_role in SPAR_AGENT_SPECS:
            entry = round2_results.get(agent_id, {})
            body = (
                entry.get("live_response", "(no round 2 output)")
                if isinstance(entry, dict)
                else str(entry)
            )
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
        round1_raw: dict[str, str] = {}
        round1_displays: dict[str, str] = {}
        self._artifact_run_dir: Path | None = None

        # === PHASE 1: Layer 0 — channel-first evidence pipeline ===
        yield self._create_phase_marker(1)
        layer0 = run_layer0_pipeline(task)
        self._message_count += 1

        preset_report = build_analysis_report("demo-diverse")
        yield self._create_team_message(
            self.model_ids[0],
            format_benchmark_report("demo-diverse"),
            "BENCHMARKS",
            round_type="model_benchmarks",
        )

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

            round1_raw[agent_id] = raw
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

        # === PHASE 3: Live debate rounds (2..N) with DCS explore/exploit ===
        yield self._create_phase_marker(3)
        settings = get_settings()
        dcs_enabled = settings.spar_dcs_enabled
        dcs_threshold = settings.spar_dcs_threshold
        max_debate_rounds = settings.spar_max_debate_rounds

        debate_rounds: dict[int, dict[str, Any]] = {}
        debate_raw_by_round: dict[int, dict[str, str]] = {}
        dcs_history: list[dict[str, Any]] = []
        debate_transcript: list[str] = [_build_round1_transcript(round1_displays)]
        prior_live_speeches: dict[str, str] | None = None
        round2_results: dict[str, Any] = {}
        round2_raw: dict[str, str] = {}

        for debate_round in range(2, max_debate_rounds + 1):
            debate_transcript.append(f"\n=== ROUND {debate_round} — Live cross-examination ===\n")
            round_results: dict[str, Any] = {}
            round_raw: dict[str, str] = {}
            round_speeches: dict[str, str] = {}

            for role_key, agent_id, prompt_file, ipc_role in SPAR_AGENT_SPECS:
                model_id = self._model_for_role(role_key)
                yield ThinkingIndicator(model=model_id)

                system = self._system_for_agent(layer0, role_key, prompt_file, task)
                transcript_so_far = _cap_transcript("\n".join(debate_transcript))
                round_user = LIVE_DEBATE_ROUND_INSTRUCTION.format(
                    round_num=debate_round,
                    role_label=_role_label(ipc_role),
                    transcript=transcript_so_far,
                )
                raw = await self._get_model_response(model_id, system, round_user)

                round_raw[agent_id] = raw
                round_results[agent_id] = {
                    "round": debate_round,
                    "live_response": raw,
                    "model": model_id,
                }
                round_speeches[agent_id] = raw
                debate_transcript.append(f"--- {ipc_role} (speaking now) ---\n{raw}\n")

                self._message_count += 1
                round_type = "round2" if debate_round == 2 else f"round{debate_round}"
                yield self._create_team_message(model_id, raw, ipc_role, round_type=round_type)

            debate_rounds[debate_round] = round_results
            debate_raw_by_round[debate_round] = round_raw
            round2_results = round_results
            round2_raw = round_raw

            if not dcs_enabled:
                break

            decision = compute_dcs(
                round_number=debate_round,
                round1_results=round1_results,
                prior_live_speeches=prior_live_speeches,
                current_live_speeches=round_speeches,
                debate_transcript="\n".join(debate_transcript),
                threshold=dcs_threshold,
                max_rounds=max_debate_rounds,
                round1_displays=round1_displays if debate_round == 2 else None,
            )
            dcs_history.append(decision.to_dict())
            self._message_count += 1
            yield self._create_team_message(
                self.model_ids[0],
                format_dcs_summary(decision),
                "DCS",
                round_type="dcs",
            )

            if decision.action == "exploit":
                break
            prior_live_speeches = round_speeches

        # === PHASE 4: Moderator ===
        yield self._create_phase_marker(4)

        moderator_model = self._model_for_role("Moderator")
        yield ThinkingIndicator(model=moderator_model)

        master = resolve_master_context(task or layer0.shock_text, _prompts_dir())
        mod = _load_prompt("moderator.txt")
        shared = build_agent_system_prompt(master, layer0, "Moderator", mod)
        user_msg = build_moderator_user_message(
            task,
            layer0,
            round1_displays,
            round2_results=round2_results,
            debate_rounds=debate_rounds if debate_rounds else None,
        )
        synthesis = await self._get_model_response(moderator_model, shared, user_msg)
        self._message_count += 1
        formatted_synthesis = format_moderator_synthesis(synthesis)
        yield self._create_team_message(
            moderator_model,
            formatted_synthesis,
            "MODERATOR",
            round_type="moderator",
        )

        scenario_id = layer0.shock_parsed.get("scenario_id", "generic")
        gate_decision, fsr_result = evaluate_plausibility_gate(
            synthesis,
            threshold=settings.spar_plausibility_threshold,
            enabled=settings.spar_plausibility_gate_enabled,
            scenario_id=scenario_id,
            fsr_enabled=settings.spar_fsr_benchmark_enabled,
            moderator_weight=settings.spar_fsr_moderator_weight,
            fsr_weight=settings.spar_fsr_weight,
        )
        self._message_count += 1
        yield self._create_team_message(
            moderator_model,
            format_plausibility_gate_summary(gate_decision, fsr_result),
            "PLAUSIBILITY_GATE",
            round_type="plausibility_gate",
        )

        if (
            settings.spar_plausibility_gate_enabled
            and not gate_decision.passed
            and settings.spar_human_review_block
        ):
            self._message_count += 1
            yield HumanReviewRequired(
                reason=gate_decision.reason,
                consensus_score=gate_decision.consensus_score,
                dissent_score=gate_decision.dissent_score,
                threshold=gate_decision.threshold,
            )

        transcript_text = "\n".join(debate_transcript)
        layer3_result = None
        if settings.spar_layer3_enabled and (
            not settings.spar_plausibility_gate_enabled or gate_decision.passed
        ):
            layer3_result = run_layer3_quantification(
                synthesis,
                round1_results=round1_results,
                moderator_plausibility=gate_decision.consensus_score,
            )
            self._message_count += 1
            yield self._create_team_message(
                moderator_model,
                format_layer3_summary(layer3_result),
                "LAYER3",
                round_type="layer3",
            )
            self._message_count += 1
            yield self._create_team_message(
                moderator_model,
                format_portfolio_recommendation(layer3_result.portfolio_recommendation),
                "PORTFOLIO",
                round_type="portfolio_recommendation",
            )

        snapshot = SparRunSnapshot(
            task=task,
            layer0=layer0,
            round1_results=round1_results,
            round1_raw=round1_raw,
            round1_displays=round1_displays,
            round2_results=round2_results,
            round2_raw=round2_raw,
            debate_transcript=transcript_text,
            moderator_raw=synthesis,
            model_map=build_model_map(self.model_ids, self.role_assignments),
            source="quorum-ui",
            debate_rounds=debate_rounds,
            debate_raw_by_round=debate_raw_by_round,
            dcs_history=dcs_history,
            plausibility_gate=gate_decision.to_dict(),
            layer3_quant=layer3_result.to_dict() if layer3_result else None,
            model_benchmark_report=preset_report,
        )
        self._artifact_run_dir = maybe_persist_spar_run(snapshot)
        if self._artifact_run_dir and layer3_result is not None:
            save_layer3_artifacts(self._artifact_run_dir, layer3_result)
        if self._artifact_run_dir:
            yield self._create_team_message(
                moderator_model,
                f"SPAR research artifacts saved to:\n{self._artifact_run_dir}",
                "ARTIFACTS",
                round_type="artifacts",
            )

        pipeline_summary = format_spar_pipeline_summary(
            dcs_enabled=dcs_enabled,
            dcs_history=dcs_history,
            gate_decision=gate_decision,
            layer3_ran=layer3_result is not None,
            artifact_dir=self._artifact_run_dir,
            debate_rounds=debate_rounds,
        )

        consensus_status = _spar_consensus_status(
            gate_decision,
            settings.spar_plausibility_gate_enabled,
        )
        differences = pipeline_summary

        self._synthesis_result = SynthesisResult(
            consensus=consensus_status,
            synthesis=formatted_synthesis,
            differences=differences,
            raw_content=synthesis,
            synthesizer_model=moderator_model,
            message_count=self._message_count,
            method="spar",
        )
        yield self._synthesis_result
