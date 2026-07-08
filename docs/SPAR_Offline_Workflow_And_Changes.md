# SPAR Offline Workflow, Round Pipeline & Session Changes

**Project:** Quorum CLI — SPAR (Scenario Planning via Agentic Reasoning)  
**Date:** July 2026  
**Hardware target:** RTX 4060 Ti 8GB · 32GB RAM · Windows · Ollama  
**Primary trial event:** Liberation Day tariffs (April 2, 2025)

---

## 1. What SPAR does (end-to-end)

SPAR stress-tests a geopolitical or policy shock against US equity markets using **five specialist agents**, a **Layer 0 evidence pipeline**, **live multi-round debate**, and a **Moderator / Scenario Validator** synthesis.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INPUT: Shock scenario text (e.g. Liberation Day tariff announcement)   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 — LAYER 0 (deterministic Python, no LLM)                       │
│  • detect_scenario_id() → ukraine_2022 | liberation_day_2025 | generic  │
│  • parse_shock() → entities, event_type, affected sectors               │
│  • score + prioritize 13 transmission channels                          │
│  • retrieve per-channel evidence (not top-3 event analogues)            │
│  • route agent-specific evidence packets                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 2 — ROUND 1 (5 agents, sequential, JSON forecasts)               │
│  Political · Economic · Environmental · Social · Devil's Advocate       │
│  Each agent: master context + Layer 0 evidence + domain prompt          │
│  Output: direction, magnitude_pct (SP500 + 5 sector ETFs), confidence     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 3 — ROUND 2 (5 agents, sequential, live prose debate)            │
│  Each agent reads full transcript (R1 + prior R2 speakers)               │
│  Must cite peers by role; agree/disagree; no JSON                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 4 — MODERATOR / VALIDATOR (1 LLM, dual JSON)                     │
│  consensus_scenario + minority_dissent                                  │
│  plausibility_score, primary_transmission_channels, sector magnitudes   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  (Planned) LAYER 3 — Python quantification (VaR, hedge, vs actual)      │
│  Not yet automated in quorum-cli; manual for paper trials               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Quorum UI (`spar` method)** runs the same four phases with streaming.  
**Offline pilot** (`examples/spar_ollama_pilot.py`) runs the same pipeline via Ollama HTTP API and writes artifacts to `Proejct Info/spar_outputs/run_<timestamp>/`.

---

## 2. Conversation / agent workflow (who speaks when)

| Order | Role | Round 1 | Round 2 | Model family (`thesis` preset) |
|-------|------|---------|---------|--------------------------------|
| — | Layer 0 | Python pipeline | — | — |
| 1 | Political & Geopolitical | Independent JSON | Live rebuttal | `llama3.1:8b` |
| 2 | Economic, Fiscal & Market | Independent JSON | Live rebuttal | `qwen2.5:7b` |
| 3 | Environmental & Technology | Independent JSON | Live rebuttal | `mistral:7b` |
| 4 | Social & Behavioural | Independent JSON | Live rebuttal | `internlm2:7b` |
| 5 | Devil's Advocate | Independent JSON | Live rebuttal | `deepseek-r1:7b` |
| 6 | Moderator / Validator | — | Synthesis | `qwen2.5:7b` |

**Debate Controller (DCS)** — explore/exploit scoring between JSON rounds — is **manual** in paper trials; not wired in code yet.

**Important:** On 8GB VRAM, agents run **one at a time** (`QUORUM_EXECUTION_MODE=sequential`). Never load five models in parallel.

---

## 3. Offline model presets

Configuration: `config/spar_offline_models.json`

| Preset | Models pulled | Use case |
|--------|---------------|----------|
| `uniform` | 1× `qwen2.5:7b` | Baseline A — same model, five personas |
| `fast-thesis` | 3× llama, qwen, deepseek-r1 | Quick multi-family test (~35 min) |
| `thesis` | 5× families | Llama, Qwen, Mistral, InternLM, DeepSeek-R1 |
| `demo-diverse` | 6× families (**default**) | IBM Granite, Qwen, Mistral, Gemma, Nemotron, Phi |

Pull models (Windows):

```powershell
powershell -File scripts/pull_spar_offline_models.ps1 -Preset demo-diverse
```

Environment template: `.env.spar-offline.example`

### Ollama context settings (8GB GPU)

| Phase | `num_ctx` | Reason |
|-------|-----------|--------|
| Round 1 | 8192 | System prompt ~8–10k chars with **compact** Layer 0 evidence |
| Round 2 + Moderator | 12288 | System prompt + growing debate transcript |

Set `offline_compact_layer0: true` in `config/spar_offline_models.json` (default) to cap channel bullets for 8GB GPUs.

---

## 4. Scenario-aware Layer 0 & master context

### Before (problem)

- Layer 0 always used **Feb 2022 Ukraine regime** and Ukraine channel boosts.
- `master_context.txt` described **only** the Russia–Ukraine invasion.
- Liberation Day runs classified as `geopolitical_shock` with Russia/Ukraine entities.

### After (fix)

| Component | Change |
|-----------|--------|
| `detect_scenario_id()` | `liberation_day_2025` vs `ukraine_2022` vs `generic` |
| `get_regime_for_shock()` | Apr 2025 regime for tariffs; Feb 2022 for Ukraine |
| `SCENARIO_CHANNEL_BOOSTS` | Trade-policy primaries for Liberation Day |
| `SCENARIO_CHANNEL_EVIDENCE` | Tariff-specific retrieval bullets per channel |
| `resolve_master_context()` | Auto-selects master context file by scenario |
| `master_context_liberation_day_2025.txt` | New prompt: Apr 2025 regime, temporal isolation, JSON schema |

**Liberation Day primary channels (typical):**

1. Sanctions / Trade / Policy Shock  
2. Sector Earnings Exposure  
3. Inflation Shock  
4. Supply Chain Disruption  
5. Consumer Sentiment / Behavioural Shock  
6. Safe-Haven / FX Flow  

---

## 5. Moderator fix

### Before

- User message was a **massive `json.dumps()`** of the full debate.
- Small local models **echoed the last Round 2 speaker** instead of synthesising.

### After

- `build_moderator_user_message()` in `spar.py` — readable Round 1 displays + Round 2 prose + Layer 0 channel list.
- Updated `moderator.txt` — explicit dual-JSON schema (consensus + minority dissent).
- Pilot rebuilds `round1_displays.json` from saved raw/json before Round 2 and Moderator.

---

## 6. Files changed in this session

| File | Change |
|------|--------|
| `src/quorum/methods/spar_layer0.py` | Scenario detection, regimes, trade evidence, boosts, `resolve_master_context()` |
| `src/quorum/methods/spar.py` | Scenario master context, `build_moderator_user_message()`, richer `_format_agent_response()` |
| `examples/spar_ollama_pilot.py` | Per-agent presets, Liberation Day scenario, resume, context sizes, transcript cap, rebuild displays |
| `config/spar_offline_models.json` | **New** — `uniform` / `fast-thesis` / `thesis` presets + Ollama options |
| `.env.spar-offline.example` | **New** — sequential Ollama config for Quorum UI |
| `scripts/pull_spar_offline_models.ps1` | **New** — one-command model pull |
| `Proejct Info/prompts/master_context_liberation_day_2025.txt` | **New** — Apr 2025 master context |
| `Proejct Info/prompts/moderator.txt` | Clearer dual-JSON synthesis instructions |
| `tests/test_spar_layer0.py` | Liberation Day scenario tests |

---

## 7. How to run (offline Liberation Day)

```powershell
# 1. Ensure Ollama is running and models are pulled
powershell -File scripts/pull_spar_offline_models.ps1 -Preset demo-diverse

# 2. Full run (45–60 min on RTX 4060 Ti 8GB)
uv run python examples/spar_ollama_pilot.py --preset demo-diverse --scenario liberation-day

# 3. Step-by-step / resume after failure
uv run python examples/spar_ollama_pilot.py --preset demo-diverse --scenario liberation-day --round layer0
uv run python examples/spar_ollama_pilot.py --preset demo-diverse --scenario liberation-day --round 1
uv run python examples/spar_ollama_pilot.py --preset demo-diverse --scenario liberation-day --round 2 --run-id <id> --resume
uv run python examples/spar_ollama_pilot.py --preset demo-diverse --scenario liberation-day --round moderator --run-id <id> --resume
```

### Output artifacts (`run_<timestamp>/`)

| File | Content |
|------|---------|
| `layer0.json` / `layer0_summary.txt` | Channel prioritization |
| `model_manifest.json` | Preset, model map, Ollama options |
| `{agent}_round1.json` / `_raw.txt` | Round 1 structured forecast |
| `{agent}_round2.json` / `_raw.txt` | Round 2 live debate |
| `round1_displays.json` | Human-readable R1 for debate |
| `live_debate_transcript.txt` | Full R1 + R2 transcript |
| `moderator_raw.txt` | Consensus + dissent JSON |

---

## 8. Known limitations (8GB offline)

| Issue | Mitigation |
|-------|------------|
| HTTP 400 on DeepSeek R1 if `num_ctx` too small | Use 8192+ for Round 1 |
| Round 2 timeout on `internlm2:7b` | 1200s timeout; transcript capped at 10k chars |
| Local 7B models ignore JSON schema | `_format_agent_response()` fallbacks; consider frontier APIs for paper |
| Prompt ~17k chars | Future: trim Layer 0 evidence block for offline profile |
| Resume overwrote displays | Fixed: `rebuild_round1_displays()` |
| gpt-oss-20b | Requires 16GB+ VRAM — not viable on RTX 4060 Ti 8GB |

---

## 9. Trial runs from this session (local only, not in git)

| Run ID | Status | Notes |
|--------|--------|-------|
| `run_20260706_184859` | Partial / stale R1 | Pre–master-context fix; moderator re-run OK |
| `run_20260706_191644` | In progress | Clean R1 with new Layer 0; R2 may be incomplete |

---

## 10. Paper alignment

| Paper element | Code status |
|---------------|-------------|
| Layer 0 channel-first RAG | ✅ Automated |
| 5 merged agents + DA | ✅ |
| 3 JSON rounds (manual Trial 1) | Offline pilot: R1 JSON + R2 live prose |
| Debate Controller (DCS) | ❌ Manual |
| Scenario Validator rename | Moderator role in code |
| Layer 3 quant (VaR, GLD/TLT hedge) | ❌ Manual Python |
| Approach B multi-model | ✅ `thesis` preset (offline) |
| Liberation Day Trial 2 | 🔄 In progress |

---

## 11. Related docs

- `docs/SPAR_Overhaul_And_Updates.pdf` — architecture overview  
- `.env.spar-free.example` — frontier multi-API Trial 2 template  
- `.env.spar-offline.example` — local Ollama template  
- `examples/spar_live_demo.py` — Quorum UI streaming demo  
