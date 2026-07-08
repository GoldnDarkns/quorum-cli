# SPAR Research ↔ Quorum Implementation Checklist

**Purpose:** Keep Quorum aligned with the research design in your project documents.  
**Last audited:** July 2026  
**Source-of-truth docs:** see §1 below  
**Code entry points:** `src/quorum/methods/spar_layer0.py`, `spar.py`, `examples/spar_ollama_pilot.py`, `quorum.bat`

---

## How to use this file

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and wired into Quorum or offline pilot |
| ⚠️ | Partial — works but diverges from paper or manual only |
| ❌ | Not implemented in code |
| 🔄 | In progress / needs validation run |

Update checkboxes as work completes. **Do not remove rows** — mark cancelled only if scope formally drops from the paper.

---

## 1. Document inventory (what defines “correct” behaviour)

| Document | Path | Defines |
|----------|------|---------|
| Full architecture + DCS math + Layer 3 | `Proejct Info/SPAR.html` | LangGraph flow, formulas, evaluation rubrics |
| Presentation / scope / 5 events | `Proejct Info/spar-presentation.html` | Four layers, Approach A vs B, test events, metrics |
| Agent prompts + manual R2/R3/DCS | `Proejct Info/spar-prompts.html` | JSON schemas, Round 2/3 protocol, DCS τ=0.35 |
| Overhaul status + pipeline | `Proejct Info/spar-overhaul-dashboard.html` | Channel-first L0, live R2, roadmap |
| Extracted prompts (runtime) | `Proejct Info/prompts/*.txt` | Master context, 5 agents, moderator |
| Offline workflow notes | `docs/SPAR_Offline_Workflow_And_Changes.md` | Pilot runs, gaps, hardware |
| Architecture PDF/DOCX | `docs/SPAR_Overhaul_And_Updates.pdf` | Faculty-facing summary |
| Research proposal | `Proejct Info/SPAR_Research_Proposal.docx` | Original scope |

---

## 2. Intended end-to-end flow (research design)

```
USER INPUT: shock scenario text (+ knowledge cutoff date)
    │
    ▼
┌─ LAYER 0 · Classification & evidence (deterministic + optional LLM profiler) ─┐
│  Regime Classifier → Shock Profiler → channel scores → per-channel RAG       │
│  → agent-specific evidence packets                                            │
└───────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ LAYER 1 · Debate + explore/exploit (up to 5 rounds) ─────────────────────────┐
│  Each round: 4 specialists → Devil's Advocate → Continuation Controller (DCS) │
│  DCS = w₁·Disagreement + w₂·InfoGain + w₃·(1 − RAG_exhaustion)               │
│  IF DCS > τ AND round < 5 → EXPLORE (another round)                          │
│  ELSE → EXPLOIT (stop debating)                                              │
└───────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ LAYER 2 · Moderation & validation ───────────────────────────────────────────┐
│  Moderator: consensus_scenario JSON + minority_dissent JSON                    │
│  plausibility_score (0–100)                                                  │
│  Plausibility Gate: low → Human Review │ ok → Layer 3                        │
└───────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ LAYER 3 · Quantification & portfolio action ─────────────────────────────────┐
│  Factor model (Fama–French) → sector P&L                                     │
│  Portfolio VaR + Expected Shortfall                                          │
│  Sector heatmap + confidence bands                                             │
│  Hedge / allocation (paper trials: e.g. GLD/TLT min-variance)                  │
│  Report Builder → risk-manager deliverable                                     │
└───────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
EVALUATION: compare predictions vs actual market moves (5 test events)
```

### What Quorum runs today (gap summary)

```
IMPLEMENTED NOW:     L0 ──► R1 JSON ──► ONE live R2 prose ──► Moderator
MISSING:                  Plausibility Gate ──► Layer 3
```

---

## 3. Expected inputs

| Input | Spec (documents) | Code status |
|-------|------------------|-------------|
| Shock narrative text | User types scenario; include knowledge cutoff | ✅ `--scenario`, `/spar`, custom `--task` |
| Pre-registered events (5) | 9/11, Iraq 2003, Ukraine 2022, Oct 7 2023, US-China tariffs Apr 2025 | ⚠️ Ukraine + Liberation Day in code; others manual |
| Macro regime (6 axes) | Live FRED + market data at cutoff | ⚠️ Hardcoded regime blocks per scenario in `spar_layer0.py` |
| Model assignment | Approach A: 1 model × 5 personas; Approach B: 5 providers + rotation | ⚠️ Presets + `/models` order; no auto rotation table |
| Sequential execution (8GB GPU) | One model at a time | ✅ `QUORUM_EXECUTION_MODE=sequential` |

---

## 4. Expected outputs (what you predict & save)

### 4.1 Layer 0 outputs

| Output | Content | Used for | Status |
|--------|---------|----------|--------|
| `layer0.json` | Channel scores, priorities, evidence, agent packets | Debate context, paper exhibits | ✅ pilot; ⚠️ not auto-saved from `quorum.bat` |
| `layer0_summary.txt` | Human-readable channel list | UI Phase 1 display | ✅ Quorum streams; ✅ pilot saves |
| Activated channel list | PRIMARY/SECONDARY per 13 channels | Moderator, Metric 3 | ✅ |

### 4.2 Layer 1 — Round 1 (per agent JSON)

Schema from `master_context*.txt` / `spar-prompts.html`:

| Field | Purpose | Status |
|-------|---------|--------|
| `direction` | negative / positive / neutral | ✅ |
| `magnitude_pct` | SP500, XLE, XLF, XLK, ITA, XLY (5-day %) | ✅ schema; ⚠️ local 7B often weak compliance |
| `confidence` | 0–1 | ✅ |
| `key_assumption` | Single critical assumption | ✅ |
| `supporting_evidence` | ≥3 traceable points from L0 packet | ✅ schema |
| `transmission_channels` | ≥3 channel pathways | ✅ schema |
| `channel_assessment` | primary_channel + adjustments | ✅ schema |

**Agents:** Political, Economic, Environmental, Social, Devil's Advocate — ✅ all five in `spar.py`

### 4.3 Layer 1 — Debate rounds 2–5

| Spec (original paper / spar-prompts) | Current code | Status |
|--------------------------------------|--------------|--------|
| Round 2+ JSON cross-exam with `response_to` | Live **prose** Round 2 only | ⚠️ **Intentional overhaul** (dashboard: “Live Sequential Debate”) |
| DA challenges weakest claim each round | DA in same loop as others | ✅ |
| DCS after each round; τ default 0.35 in prompts | Not computed | ❌ |
| Up to 5 rounds if DCS > τ | Fixed 1 live R2 | ❌ |
| Track position-change type (evidence / pressure / flip) | Not tracked | ❌ |

### 4.4 Layer 2 — Moderator / Scenario Validator

| Output | Schema | Status |
|--------|--------|--------|
| `consensus_scenario` | type, direction, magnitude_pct, confidence, channels, plausibility_score, consensus_summary | ✅ |
| `minority_dissent` | dissenting_agents, direction, magnitude_pct, preserved_dissent_summary, plausibility_score | ✅ |
| Plausibility Gate routing | low → human review | ✅ |
| Human review pause node | Safety stop | ✅ |

### 4.5 Layer 3 — Quantification & hedge (portfolio)

| Output | Spec (SPAR.html, presentation) | Status |
|--------|----------------------------------|--------|
| Sector P&L from factor model | Rᵢ − R_f = α + β(R_m−R_f) + s·SMB + h·HML + ε | ❌ |
| Portfolio VaR (95%) | μ − z_α·σ | ❌ |
| Expected Shortfall | E[L \| L ≥ VaR] | ❌ |
| Sector heatmap | Visual report | ⚠️ `scripts/generate_spar_report_pdf.py` (manual, Ukraine run) |
| **Hedge portfolio weights** | e.g. GLD/TLT min-variance (Trial 1 manual) | ❌ not in repo |
| “What to invest / how to rebalance” narrative | Report Builder | ❌ |
| Confidence bands from agent calibration | Feeds L3 | ❌ |

### 4.6 Evaluation outputs (post-hoc vs reality)

| Metric | Definition | Status |
|--------|------------|--------|
| **M1** Directional accuracy | Sign correct per sector (0/1) | ⚠️ manual in report script |
| **M2** Magnitude calibration | Within 20%/40% of actual | ⚠️ manual in report script |
| **M3** Transmission channel completeness | vs literature channel list | ❌ |
| Debate quality rubrics | Evidence grounding, engagement, calibration | ❌ automated |
| Cohen's κ | Human vs moderator agreement | ❌ |
| Approach A vs B comparison | Same 5 events | 🔄 Ukraine + Liberation Day runs only |

### 4.7 Artifact files (pilot / research folder)

| File | When | Status |
|------|------|--------|
| `model_manifest.json` | Start of run | ✅ pilot |
| `{agent}_round1.json` / `_raw.txt` | After R1 | ✅ pilot |
| `round1_displays.json` | Readable R1 for debate | ✅ pilot |
| `{agent}_round2.json` / `_raw.txt` | After R2+ | ✅ pilot (one round) |
| `live_debate_transcript.txt` | Full R1+R2 | ✅ pilot |
| `round2_all.json` | Aggregated R2 | ✅ pilot |
| `moderator_raw.txt` | Layer 2 output | ✅ pilot |
| `dcs_scores.json` | Per-round DCS + decision | ✅ |
| `plausibility_gate.json` | Gate decision + scores | ✅ |
| `SPAR_*_Report.pdf` | Final deliverable | ⚠️ manual script |

---

## 5. Layer-by-layer implementation checklist

### LAYER 0 — Classification & channel-first evidence

- [x] **L0.1** `detect_scenario_id()` — ukraine / liberation_day / generic (`spar_layer0.py`)
- [x] **L0.2** `parse_shock()` — entities, event_type, affected_systems
- [x] **L0.3** 13 transmission channels defined + `TRANSMISSION_CHANNELS`
- [x] **L0.4** Activation score formula S_c (30/25/20/15/10 weights)
- [x] **L0.5** Priority tiers + retrieval budgets (PRIMARY/SECONDARY/WATCHLIST/INACTIVE)
- [x] **L0.6** `SCENARIO_CHANNEL_BOOSTS` — Ukraine + Liberation Day
- [x] **L0.7** `SCENARIO_CHANNEL_EVIDENCE` — curated per-channel bullets
- [x] **L0.8** `build_agent_packets()` — route evidence to 5 agents
- [x] **L0.9** `resolve_master_context()` — scenario-specific master context files
- [x] **L0.10** Display in Quorum UI Phase 1 (`round_type=layer0`)
- [x] **L0.11** Offline compact mode for 8GB (`offline_compact_layer0`)
- [ ] **L0.12** Regime Classifier from **live FRED** (6 macro axes at cutoff date)
- [ ] **L0.13** Shock Profiler as **LLM node** (paper) vs current rule-based parser
- [ ] **L0.14** Live RAG: **yfinance** sector/VIX at cutoff
- [ ] **L0.15** Live RAG: **GPR index** retrieval
- [ ] **L0.16** Live RAG: **GDELT / NewsAPI** (replace curated dict)
- [ ] **L0.17** Top-3 **historical analogue** retrieval (3D: category × geography × regime) — paper; superseded by channel-first in overhaul but may still be needed for evaluation narrative
- [x] **L0.18** Auto-save Layer 0 from `quorum.bat` to `spar_outputs/run_*` (`spar_artifacts.py`)

### LAYER 1 — Multilateral debate + DCS

- [x] **L1.1** Five merged domain agents + Devil's Advocate prompts
- [x] **L1.2** Round 1 independent JSON (blind to each other)
- [x] **L1.3** Role → model mapping (`get_role_assignments`, `/models` order)
- [x] **L1.4** Live sequential Round 2 (prose, full transcript visibility)
- [x] **L1.5** Round 2 must reference peers by role (prompt enforced)
- [x] **L1.6** Quorum UI phases + i18n labels for SPAR
- [x] **L1.7** Approach A offline (`uniform` preset — one model)
- [x] **L1.8** Approach B offline (`thesis`, `demo-diverse` presets)
- [x] **L1.9** `spar_dcs.py` — Disagreement score (variance of magnitude_pct / direction)
- [x] **L1.10** `spar_dcs.py` — Information gain (position changes round-to-round)
- [x] **L1.11** `spar_dcs.py` — RAG exhaustion (evidence repetition detection)
- [x] **L1.12** Continuation Controller — `DCS > τ` → explore; else exploit
- [x] **L1.13** Configurable τ (default 0.35 per `spar-prompts.html`; elbow calibration per `SPAR.html`)
- [x] **L1.14** Debate loop Rounds 3–5 (max 5 cap)
- [x] **L1.15** DCS logged to `dcs_scores.json` + shown in Quorum UI
- [ ] **L1.16** Optional: Round 2+ **JSON mode** with `response_to` (paper) as config flag alongside live prose
- [ ] **L1.17** Position-change decomposition (evidence / consensus-pressure / unsupported flip)
- [ ] **L1.18** Approach B **role rotation table** across 5 events (automated manifest)
- [ ] **L1.19** Devil's Advocate **separate model session** enforcement (paper: separate Claude tab)

### LAYER 2 — Moderation & validation

- [x] **L2.1** Moderator prompt + dual JSON schema (`moderator.txt`)
- [x] **L2.2** `build_moderator_user_message()` — readable transcript (not raw JSON dump)
- [x] **L2.3** Moderator receives L0 channels + R1 + full R2 transcript
- [x] **L2.4** `plausibility_score` in moderator output
- [x] **L2.5** Quorum UI Phase 4 synthesis display
- [x] **L2.6** Plausibility Gate — threshold routing (low → human review)
- [x] **L2.7** Human Review UI pause / flag in Quorum
- [ ] **L2.8** Rename display “Moderator” → “Scenario Validator” in UI (optional paper alignment)
- [x] **L2.9** Federal Reserve FSR benchmark for plausibility (paper data source)

### LAYER 3 — Quantification, hedge & portfolio

- [ ] **L3.1** `spar_layer3.py` module
- [ ] **L3.2** Parse moderator `consensus_scenario` + `minority_dissent` → scenario factors
- [ ] **L3.3** Fama–French factor sensitivities per sector ETF
- [ ] **L3.4** Predicted sector returns under consensus + dissent scenarios
- [ ] **L3.5** Portfolio VaR (95%) + Expected Shortfall
- [ ] **L3.6** Sector P&L heatmap (automated, not one-off script)
- [ ] **L3.7** **Hedge portfolio optimizer** — min-variance or risk-parity (GLD/TLT or configurable universe)
- [ ] **L3.8** “What to hold / what to reduce” plain-English allocation summary
- [ ] **L3.9** Confidence bands from agent `confidence` + calibration rubric
- [ ] **L3.10** Wire Layer 3 as Quorum Phase 5 OR post-run command
- [ ] **L3.11** `layer3_quant.json` + integrated PDF report builder

### EVALUATION & RESEARCH OPS

- [ ] **E.1** Register all 5 test events in `config/spar_events.json`
- [ ] **E.2** `scripts/score_spar_run.py` — M1/M2/M3 vs yfinance actuals
- [ ] **E.3** Actuals table per event (1-day, 5-day) — SP500 + 5 ETFs
- [ ] **E.4** Approach A vs B batch runner + comparison table
- [ ] **E.5** Debate quality scoring (automated or assisted)
- [ ] **E.6** Ablation flags: DA on/off, DCS on/off, regime on/off
- [ ] **E.7** Export SPAR-specific JSON from Quorum `/export` (currently uses StandardParser)
- [ ] **E.8** Reproducibility bundle: prompts hash + model manifest + all artifacts per run

### QUORUM UX (how you run & watch)

- [x] **Q.1** `quorum.bat` launches terminal UI
- [x] **Q.2** `/method spar` + `/models` + `/spar <shock>`
- [x] **Q.3** Stream Layer 0 → R1 → R2 → Moderator in UI
- [x] **Q.4** Offline pilot with resume (`spar_ollama_pilot.py`)
- [x] **Q.5** Auto-write all artifacts from `quorum.bat` (parity with pilot)
- [x] **Q.6** UI shows DCS score + “explore / exploit” decision each round
- [ ] **Q.7** UI shows Layer 3 VaR + hedge weights after moderator
- [ ] **Q.8** Phase labels match paper layers (optional: “Layer 1 — Round 2” etc.)

---

## 6. Priority build order (recommended)

Use this order so each step unlocks the next for your research demos:

| Priority | ID | Task | Unblocks |
|----------|-----|------|----------|
| **P0** | Q.5 | Save full artifact tree from `quorum.bat` | Same outputs whether UI or pilot |
| **P1** | L1.9–L1.15 | `spar_dcs.py` + debate loop in `spar.py` | Paper-faithful explore/exploit |
| **P2** | L2.6–L2.7 | Plausibility Gate + human review flag | Layer 2 complete |
| **P3** | L3.1–L3.8 | `spar_layer3.py` + hedge optimizer | Portfolio / hedge deliverable |
| **P4** | E.2–E.3 | Automated scoring vs actuals | Metrics 1–2 for all trials |
| **P5** | L0.12–L0.16 | Live FRED/yfinance/GPR RAG | Regime + evidence freshness |
| **P6** | E.1, E.4 | Five events + Approach A/B batch | Full paper comparison |

---

## 7. How to run today (what you get vs what’s missing)

### Interactive (watch the debate) — **recommended for research observation**

```powershell
cd "d:\VS Code Projects\Debate AI\quorum-cli"
.\quorum.bat
```

Then: `/method spar` → `/models` (6 models in role order) → paste shock or `/spar ...`

**You will see:** Layer 0 → Round 1 JSON → Round 2 live debate → Moderator JSON → **artifact save path**  
**You will NOT see:** Layer 3 VaR/hedge (P3), automated M1/M2 scoring (P4), live FRED/GDELT RAG (P5)

### Offline pilot (artifacts on disk)

```powershell
uv run python examples/spar_ollama_pilot.py --preset demo-diverse --scenario liberation-day
```

**You get:** full `Proejct Info/spar_outputs/run_*` folder (see §4.7)  
**Still missing:** DCS, Layer 3, automated evaluation

### Manual Layer 3 (current workaround)

After a completed run, use/adapt `scripts/generate_spar_report_pdf.py` + external Python for GLD/TLT hedge (Trial 1 approach — not in repo).

---

## 8. Known intentional divergences (document in paper)

| Paper / prompts | Current implementation | Action |
|-----------------|------------------------|--------|
| Top-3 event analogues | Channel-first evidence | ✅ Already framed as overhaul contribution |
| Round 2+ JSON cross-exam | One live prose Round 2 | Decide: keep prose, add JSON mode, or both |
| Shock Profiler = LLM | Rule-based `parse_shock()` | Implement LLM profiler or document as simplification |
| LangGraph orchestration | Python `SparMethod.run_stream()` | LangGraph optional; behaviour must match |

---

## 9. Trial run log (update as you go)

| Event | Approach | Run ID | L0 | R1 | R2+ | DCS | Mod | L3 | Scored |
|-------|----------|--------|----|----|-----|-----|-----|-----|--------|
| Ukraine 2022 | A (uniform) | `run_20260701_211531` | ⚠️ old | ✅ | ⚠️ JSON | ❌ | ✅ | ❌ manual PDF | ⚠️ |
| Ukraine 2022 | B | `run_20260706_*` | ✅ | ✅ | ✅ live | ❌ | ✅ | ❌ | ❌ |
| Liberation Day 2025 | B demo-diverse | `run_20260707_223218` | ✅ | ✅ | ✅ live | ❌ | ✅ | ❌ | ❌ |
| 9/11 | — | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Iraq 2003 | — | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Oct 7 2023 | — | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 10. Single-page status (July 2026)

| Layer | Research scope | Quorum status |
|-------|----------------|---------------|
| **Layer 0** | Regime + channels + RAG | **~75%** — core pipeline done; live APIs missing |
| **Layer 1** | Debate + DCS loop | **~85%** — R1 + adaptive live R2–R5 with DCS; optional JSON mode / rotation table still open |
| **Layer 2** | Moderator + gate | **~95%** — synthesis + FSR benchmark + plausibility gate + human review |
| **Layer 3** | VaR + hedge + report | **~50%** — automated `layer3_quant.json` + GLD/TLT hedge; PDF report still manual |
| **Evaluation** | M1–M3 + rubrics | **~15%** — partial manual charts |

**Next milestone:** P3 (`spar_layer3.py` — VaR, Fama-French, GLD/TLT hedge) for portfolio quantification.

---

*Maintained for SP Jain Group 3 · AI in Finance · SPAR 2026*
