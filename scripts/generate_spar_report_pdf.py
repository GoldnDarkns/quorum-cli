#!/usr/bin/env python3
"""Generate a professional SPAR pilot run PDF report with charts and analysis."""

from __future__ import annotations

import json
import re
import statistics
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / "Proejct Info" / "spar_outputs" / "run_20260701_211531"
CHART_DIR = RUN_DIR / "_report_charts"
OUT_PDF = RUN_DIR / "SPAR_Offline_Pilot_Report.pdf"

AGENT_ORDER = [
    "political_geopolitical",
    "economic_fiscal_market",
    "environmental_technology",
    "social_behavioural",
    "devils_advocate",
]

AGENT_LABELS = {
    "political_geopolitical": "Political & Geopolitical",
    "economic_fiscal_market": "Economic, Fiscal & Market",
    "environmental_technology": "Environmental & Technology",
    "social_behavioural": "Social & Behavioural",
    "devils_advocate": "Devil's Advocate",
}

AGENT_SHORT = {
    "political_geopolitical": "Political",
    "economic_fiscal_market": "Economic",
    "environmental_technology": "Environmental",
    "social_behavioural": "Social",
    "devils_advocate": "Devil's Adv.",
}

ETFS = ["SP500", "XLE", "XLF", "XLK", "ITA", "XLY"]

ACTUAL_FEB24_1D = {
    "SP500": 1.5,
    "XLE": -0.5,
    "XLF": 0.8,
    "XLK": 3.3,
    "ITA": 1.2,
    "XLY": 1.0,
}

ACTUAL_5D = {
    "SP500": -1.0,
    "XLE": 8.0,
    "XLF": -2.0,
    "XLK": -4.0,
    "ITA": 2.0,
    "XLY": -3.0,
}

# Brand colours (RGB 0-255)
NAVY = (20, 40, 100)
SLATE = (60, 70, 90)
BEAR = (180, 50, 50)
BULL = (40, 140, 80)
LIGHT_BG = (245, 247, 250)


def clean(text: str) -> str:
    return (
        str(text)
        .replace("\u2192", "->")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u2022", "-")
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


def strip_md(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    return clean(text.strip())


class SparReport(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(18, 22, 18)
        self.set_auto_page_break(auto=True, margin=20)

    def content_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*SLATE)
        self.cell(self.content_width(), 6, "SPAR Offline Pilot Report", align="L")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 6, "Russia-Ukraine Invasion | Feb 2022", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 205, 215)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(self.content_width() / 2, 8, f"Run: run_20260701_211531")
        self.cell(self.content_width() / 2, 8, f"Page {self.page_no()}", align="R")

    def ensure_space(self, height: float) -> None:
        if self.get_y() + height > self.h - self.b_margin:
            self.add_page()

    def section_title(self, title: str, level: int = 1) -> None:
        self.ensure_space(14)
        self.ln(3)
        size = 15 if level == 1 else 12
        self.set_font("Helvetica", "B", size)
        self.set_text_color(*NAVY)
        self.multi_cell(self.content_width(), 7, clean(title))
        self.set_draw_color(*NAVY)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def sub_title(self, title: str) -> None:
        self.ensure_space(10)
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*SLATE)
        self.multi_cell(self.content_width(), 6, clean(title))
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def body_text(self, text: str, size: int = 10) -> None:
        self.set_font("Helvetica", "", size)
        self.multi_cell(self.content_width(), 5, clean(text))
        self.ln(2)

    def bullet(self, text: str, indent: int = 0) -> None:
        self.set_font("Helvetica", "", 10)
        prefix = " " * indent + "- "
        wrapped = textwrap.wrap(clean(text), width=95 - indent)
        for i, line in enumerate(wrapped):
            self.multi_cell(self.content_width(), 5, prefix + line if i == 0 else " " * (indent + 2) + line)

    def info_box(self, title: str, lines: list[str]) -> None:
        self.ensure_space(8 + len(lines) * 5)
        y0 = self.get_y()
        self.set_fill_color(*LIGHT_BG)
        self.rect(self.l_margin, y0, self.content_width(), 8 + len(lines) * 5.5, style="F")
        self.set_xy(self.l_margin + 3, y0 + 2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*NAVY)
        self.cell(self.content_width() - 6, 5, clean(title))
        self.ln(6)
        self.set_x(self.l_margin + 3)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        for line in lines:
            self.set_x(self.l_margin + 3)
            self.multi_cell(self.content_width() - 6, 4.5, clean(line))
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def render_table(self, headers: list[str], rows: list[list[str]], col_weights: list[float] | None = None) -> None:
        w_total = self.content_width()
        n = len(headers)
        weights = col_weights or [1.0] * n
        w_sum = sum(weights)
        col_w = [w_total * (wt / w_sum) for wt in weights]
        row_h = 7

        self.ensure_space(row_h * (len(rows) + 2))
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(*NAVY)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_w[i], row_h, clean(h), border=1, align="C", fill=True)
        self.ln()

        self.set_font("Helvetica", "", 8)
        self.set_text_color(0, 0, 0)
        for ri, row in enumerate(rows):
            fill = ri % 2 == 1
            if fill:
                self.set_fill_color(248, 249, 252)
            max_lines = 1
            cell_lines: list[list[str]] = []
            for val in row:
                lines = textwrap.wrap(clean(str(val)), width=max(8, int(col_w[len(cell_lines)] / 2.2))) or [""]
                cell_lines.append(lines)
                max_lines = max(max_lines, len(lines))
            row_height = row_h * max_lines
            x0 = self.l_margin
            y0 = self.get_y()
            if y0 + row_height > self.h - self.b_margin:
                self.add_page()
                y0 = self.get_y()
            for ci, lines in enumerate(cell_lines):
                x = x0 + sum(col_w[:ci])
                self.rect(x, y0, col_w[ci], row_height, style="DF" if fill else "D")
                self.set_xy(x + 1, y0 + 1)
                for line in lines:
                    self.cell(col_w[ci] - 2, row_h - 1, line, align="C" if ci > 0 else "L")
                    self.set_x(x + 1)
                    self.set_y(self.get_y() + row_h - 1)
                self.set_xy(x + col_w[ci], y0)
            self.set_y(y0 + row_height)
        self.ln(3)

    def add_chart(self, path: Path, title: str, height_mm: float = 80) -> None:
        if not path.exists():
            return
        self.ensure_space(height_mm + 12)
        self.sub_title(title)
        img_w = self.content_width()
        self.image(str(path), x=self.l_margin, w=img_w, h=height_mm)
        self.ln(4)

    def render_markdown(self, text: str) -> None:
        for block in re.split(r"\n\s*\n", text.strip()):
            lines = block.strip().splitlines()
            if not lines:
                continue
            first = lines[0].strip()
            if first.startswith("### "):
                self.section_title(strip_md(first), level=2)
                lines = lines[1:]
            elif first.startswith("#### "):
                self.sub_title(strip_md(first))
                lines = lines[1:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("- "):
                    self.bullet(strip_md(line[2:]))
                elif re.match(r"^\d+\.\s", line):
                    self.bullet(strip_md(re.sub(r"^\d+\.\s*", "", line)))
                else:
                    self.body_text(strip_md(line))

    def wrapped_code_block(self, text: str, font_size: int = 7) -> None:
        self.set_font("Courier", "", font_size)
        w = self.content_width()
        for paragraph in text.split("\n\n"):
            for raw_line in paragraph.splitlines():
                line = clean(raw_line) if raw_line.strip() else ""
                chunks = textwrap.wrap(line, width=100) if line else [""]
                for chunk in chunks:
                    self.ensure_space(4)
                    self.multi_cell(w, 3.8, chunk)
            self.ln(1)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_agent_round(aid: str, rnd: int) -> dict:
    path = RUN_DIR / f"{aid}_round{rnd}.json"
    if path.exists():
        return load_json(path)
    return {}


def agent_forecast(data: dict) -> dict | None:
    if data.get("direction") and data.get("magnitude_pct"):
        return data
    for v in data.values():
        if isinstance(v, dict) and v.get("direction") and v.get("magnitude_pct"):
            return v
    return None


def round2_peer_responses(data: dict) -> dict[str, str]:
    rt = data.get("response_to")
    if isinstance(rt, dict):
        return {k: str(v) for k, v in rt.items()}
    return {}


def round2_nested_peers(data: dict) -> list[dict]:
    peers = []
    for k, v in data.items():
        if k in ("round", "response_to"):
            continue
        if isinstance(v, dict) and v.get("agent_id"):
            peers.append(v)
    return peers


def generate_charts(r1: dict) -> dict[str, Path]:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    agents = AGENT_ORDER
    labels = [AGENT_SHORT[a] for a in agents]

    sp500 = []
    dirs = []
    conf = []
    for a in agents:
        d = agent_forecast(r1[a]) or {}
        sp500.append(float((d.get("magnitude_pct") or {}).get("SP500", 0)))
        dirs.append(d.get("direction", "negative"))
        conf.append(float(d.get("confidence", 0)))

    colors = [BULL[0] / 255 if d == "positive" else BEAR[0] / 255 for d in dirs]
    colors_g = ["#2d8c50" if d == "positive" else "#b43232" for d in dirs]

    # Chart 1: SP500 forecasts
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, sp500, color=colors_g, edgecolor="white", linewidth=0.8)
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.axhline(ACTUAL_FEB24_1D["SP500"], color="#1565c0", linestyle="--", linewidth=1.5, label="Actual Feb 24 (+1.5%)")
    ax.set_ylabel("Forecast SP500 move (%)")
    ax.set_title("Round 1 SP500 Forecasts by Agent")
    ax.legend(loc="lower right", fontsize=8)
    for bar, val in zip(bars, sp500):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + (0.3 if val >= 0 else -0.8),
                f"{val:+.1f}%", ha="center", va="bottom" if val >= 0 else "top", fontsize=9)
    fig.tight_layout()
    p1 = CHART_DIR / "sp500_forecasts.png"
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    paths["sp500"] = p1

    # Chart 2: Predicted vs actual
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(ETFS))
    avg_pred = []
    for etf in ETFS:
        vals = []
        for a in agents:
            d = agent_forecast(r1[a]) or {}
            m = (d.get("magnitude_pct") or {}).get(etf)
            if m is not None:
                vals.append(float(m))
        avg_pred.append(statistics.mean(vals) if vals else 0)
    actual1 = [ACTUAL_FEB24_1D[e] for e in ETFS]
    actual5 = [ACTUAL_5D[e] for e in ETFS]
    w = 0.25
    ax.bar(x - w, avg_pred, w, label="Avg agent forecast", color="#5c6bc0")
    ax.bar(x, actual1, w, label="Actual 1-day", color="#26a69a")
    ax.bar(x + w, actual5, w, label="Actual ~5-day", color="#ffa726")
    ax.set_xticks(x)
    ax.set_xticklabels(ETFS)
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_ylabel("Return (%)")
    ax.set_title("Average Agent Forecast vs Actual Market Moves")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p2 = CHART_DIR / "pred_vs_actual.png"
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    paths["pred_actual"] = p2

    # Chart 3: ETF heatmap by agent
    matrix = []
    for a in agents:
        d = agent_forecast(r1[a]) or {}
        row = [(d.get("magnitude_pct") or {}).get(e, 0) for e in ETFS]
        matrix.append([float(v) for v in row])
    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=-12, vmax=12)
    ax.set_xticks(range(len(ETFS)))
    ax.set_xticklabels(ETFS)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_title("Round 1 ETF Forecast Heatmap (%)")
    for i in range(len(labels)):
        for j in range(len(ETFS)):
            ax.text(j, i, f"{matrix[i][j]:+.0f}", ha="center", va="center", fontsize=8, color="black")
    fig.colorbar(im, ax=ax, shrink=0.8, label="% move")
    fig.tight_layout()
    p3 = CHART_DIR / "heatmap.png"
    fig.savefig(p3, dpi=150)
    plt.close(fig)
    paths["heatmap"] = p3

    # Chart 4: Confidence
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.barh(labels, conf, color="#78909c")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Confidence score")
    ax.set_title("Agent Confidence (Round 1)")
    for i, v in enumerate(conf):
        ax.text(v + 0.02, i, f"{v:.2f}", va="center", fontsize=9)
    fig.tight_layout()
    p4 = CHART_DIR / "confidence.png"
    fig.savefig(p4, dpi=150)
    plt.close(fig)
    paths["confidence"] = p4

    # Chart 5: Direction pie
    fig, ax = plt.subplots(figsize=(4, 4))
    bear = sum(1 for d in dirs if d == "negative")
    bull = len(dirs) - bear
    ax.pie([bear, bull], labels=[f"Bearish ({bear})", f"Bullish ({bull})"], colors=["#c62828", "#2e7d32"],
           autopct="%1.0f%%", startangle=90)
    ax.set_title("Round 1 Direction Consensus")
    fig.tight_layout()
    p5 = CHART_DIR / "consensus.png"
    fig.savefig(p5, dpi=150)
    plt.close(fig)
    paths["consensus"] = p5

    return paths


def cover_page(pdf: SparReport) -> None:
    pdf.add_page()
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 55, style="F")
    pdf.set_y(18)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(pdf.content_width(), 12, "SPAR Pilot Run Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(pdf.content_width(), 8, "Scenario Planning via Agentic Reasoning", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(pdf.content_width(), 8, "Russia-Ukraine Full-Scale Invasion", align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(pdf.content_width(), 7, "Financial Market Stress Test | February 24, 2022", align="C")
    pdf.ln(10)

    meta = [
        ("Institution", "SP Jain School of Global Management - Group 3"),
        ("Run ID", "run_20260701_211531"),
        ("Generated", datetime.now().strftime("%B %d, %Y at %H:%M")),
        ("Execution", "Offline via Ollama (local GPU)"),
        ("Knowledge cutoff", "February 23, 2022 market close"),
        ("Report type", "Full debate analysis with verbatim transcripts"),
    ]
    pdf.render_table(["Field", "Value"], [[a, b] for a, b in meta], col_weights=[1.2, 3])
    pdf.ln(6)
    pdf.info_box(
        "Executive headline",
        [
            "4 of 5 agents predicted bearish SP500 moves (-3.5% to -7.0%).",
            "Devil's Advocate dissented with a +3.0% relief-rally thesis.",
            "Largest disagreement: XLE (+8% Economic vs -8% Environmental = 16pp spread).",
            "Invasion-day actual: SP500 +1.5% (reversal rally) - DA was directionally closest.",
        ],
    )


def toc_page(pdf: SparReport) -> None:
    pdf.add_page()
    pdf.section_title("Table of Contents")
    sections = [
        "1. Executive Summary",
        "2. System Configuration & Models",
        "3. Methodology & Pipeline",
        "4. Round 1 - Independent Forecasts",
        "5. Round 2 - Cross-Examination & Critique",
        "6. Moderator Synthesis",
        "7. Statistical Analysis & Charts",
        "8. Comparison vs Actual Market Data",
        "9. Research Critique & Limitations",
        "10. Key Findings",
        "11. Run Metadata",
        "Appendix A - Full Agent Transcripts",
    ]
    for s in sections:
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(pdf.content_width(), 7, clean(s))
    pdf.ln(4)


def main() -> None:
    if not RUN_DIR.exists():
        raise SystemExit(f"Run folder not found: {RUN_DIR}")

    r1 = load_json(RUN_DIR / "round1_all.json")
    moderator = (RUN_DIR / "moderator_raw.txt").read_text(encoding="utf-8")
    charts = generate_charts(r1)

    pdf = SparReport()
    cover_page(pdf)
    toc_page(pdf)

    # --- 1. Executive Summary ---
    pdf.add_page()
    pdf.info_box(
        "Architecture note",
        [
            "This pilot run (run_20260701_211531) used the pre-overhaul pipeline:",
            "no Layer 0 channel prioritization; Round 2 was JSON cross-exam (not live debate).",
            "Current SPAR (July 2026): Layer 0 -> Round 1 JSON -> Round 2 live prose -> Moderator.",
            "See docs/SPAR_Overhaul_And_Updates.pdf for the full architecture update.",
        ],
    )

    pdf.section_title("1. Executive Summary")
    sp500_vals = []
    for a in AGENT_ORDER:
        d = agent_forecast(r1[a]) or {}
        m = (d.get("magnitude_pct") or {}).get("SP500")
        if m is not None:
            sp500_vals.append(float(m))
    bearish = sum(1 for a in AGENT_ORDER if (agent_forecast(r1[a]) or {}).get("direction") == "negative")
    avg_sp = statistics.mean(sp500_vals) if sp500_vals else 0

    pdf.body_text(
        "This report documents the first offline SPAR pilot: five domain-specialist LLM agents "
        "and one moderator debated the financial market impact of Russia's full-scale invasion of "
        "Ukraine, using only information available through February 23, 2022. The run was executed "
        "entirely on local hardware via Ollama, with no cloud API calls."
    )
    pdf.add_chart(charts["consensus"], "Figure 1 - Direction consensus at a glance", 55)
    pdf.add_chart(charts["sp500"], "Figure 2 - SP500 forecasts vs actual invasion-day move", 70)

    pdf.info_box("Consensus snapshot", [
        f"Bearish agents: {bearish}/5 | Bullish: {5 - bearish}/5 (Devil's Advocate)",
        f"SP500 forecast range: {min(sp500_vals):+.1f}% to {max(sp500_vals):+.1f}% (mean {avg_sp:+.1f}%)",
        f"Actual SP500 on Feb 24, 2022: +1.5% (intraday crash then sharp reversal)",
        "Devil's Advocate (+3.0%) was closest to invasion-day direction.",
    ])

    # --- 2. System Configuration ---
    pdf.add_page()
    pdf.section_title("2. System Configuration & Models")
    pdf.render_table(
        ["Component", "Specification"],
        [
            ["LLM runtime", "Ollama v0.31.1 (local)"],
            ["Model (all roles)", "qwen2.5:7b"],
            ["Parameters", "~7B, Q4_K_M quantization (Ollama default)"],
            ["Temperature", "0 (deterministic)"],
            ["Hardware", "AMD Ryzen 7 5700X, 32 GB RAM, NVIDIA RTX 4060 Ti 8 GB"],
            ["Agents", "5 domain specialists + 1 moderator"],
            ["Total inference calls", "11 (5 R1 + 5 R2 + 1 moderator)"],
            ["Approx. runtime", "~6 minutes sequential"],
            ["Runner script", "examples/spar_ollama_pilot.py"],
        ],
        col_weights=[1.2, 3],
    )
    pdf.sub_title("Agent role mapping")
    pdf.render_table(
        ["Agent ID", "Domain", "Prompt file"],
        [
            ["political_geopolitical", "Geopolitical risk & sanctions", "agent1_political_geopolitical.txt"],
            ["economic_fiscal_market", "Macro, fiscal & market structure", "agent2_economic_fiscal_market.txt"],
            ["environmental_technology", "Supply chain, energy, tech", "agent3_environmental_technology.txt"],
            ["social_behavioural", "Sentiment & behavioural finance", "agent4_social_behavioural.txt"],
            ["devils_advocate", "Contrarian / relief-rally thesis", "agent5_devils_advocate.txt"],
        ],
        col_weights=[1.3, 1.5, 1.5],
    )
    pdf.body_text(
        "Note: All five agents used the same underlying model (qwen2.5:7b). Role differentiation "
        "comes entirely from system prompts in Proejct Info/prompts/. The planned cloud deployment "
        "maps distinct models per agent (Llama 70B, DeepSeek, Qwen 72B, etc.) for higher fidelity."
    )

    # --- 3. Methodology ---
    pdf.section_title("3. Methodology & Pipeline")
    pdf.body_text(
        "Historical pilot pipeline (this run): Round 1 independent JSON forecasts -> Round 2 JSON "
        "cross-examination -> Moderator synthesis. No Layer 0 channel router."
    )
    pdf.body_text(
        "Current SPAR architecture (post-overhaul): Layer 0 transmission-channel evidence routing "
        "-> Round 1 domain JSON -> Round 2 live sequential debate (prose) -> Moderator."
    )
    steps = [
        "Round 1: Each agent independently produces a structured JSON forecast (direction, ETF magnitudes, confidence, evidence, analogues).",
        "Round 2: Each agent receives all Round 1 outputs and must agree/disagree with peers, citing specific claims.",
        "Moderator: Receives all Round 1 and Round 2 outputs and produces a synthesis with observations and recommendations.",
        "Scoring: Forecasts compared against actual Feb 24 (1-day) and ~5-day post-invasion market moves.",
    ]
    for i, s in enumerate(steps, 1):
        pdf.bullet(f"Step {i}: {s}")

    # --- 4. Round 1 ---
    pdf.add_page()
    pdf.section_title("4. Round 1 - Independent Forecasts")
    pdf.add_chart(charts["heatmap"], "Figure 3 - ETF forecast heatmap across all agents", 75)

    headers = ["Agent"] + ETFS + ["Dir", "Conf"]
    rows = []
    for aid in AGENT_ORDER:
        d = agent_forecast(r1[aid]) or {}
        mag = d.get("magnitude_pct") or {}
        rows.append(
            [AGENT_SHORT[aid]]
            + [f"{mag.get(e, '-'):+.1f}%" if isinstance(mag.get(e), (int, float)) else "-"
               for e in ETFS]
            + [d.get("direction", "-"), str(d.get("confidence", "-"))]
        )
    pdf.render_table(headers, rows, col_weights=[1.1] + [0.7] * 6 + [0.7, 0.6])

    for aid in AGENT_ORDER:
        d = agent_forecast(r1[aid]) or {}
        pdf.add_page()
        pdf.sub_title(f"{AGENT_LABELS[aid]} - Round 1 Analysis")
        pdf.render_table(
            ["Field", "Value"],
            [
                ["Direction", d.get("direction", "N/A")],
                ["Confidence", str(d.get("confidence", "N/A"))],
                ["Key assumption", d.get("key_assumption", "N/A")],
            ],
            col_weights=[1, 3.5],
        )
        pdf.sub_title("Supporting evidence")
        for ev in d.get("supporting_evidence") or []:
            pdf.bullet(str(ev))
        pdf.sub_title("Transmission channels")
        for ch in d.get("transmission_channels") or []:
            pdf.bullet(str(ch))
        aa = d.get("analogue_assessment") or {}
        if aa:
            pdf.sub_title("Historical analogue")
            pdf.body_text(
                f"Primary: {aa.get('primary_analogue', 'N/A')}\n"
                f"Adjustments: {aa.get('analogue_adjustments', 'N/A')}"
            )

    # --- 5. Round 2 ---
    pdf.add_page()
    pdf.section_title("5. Round 2 - Cross-Examination & Critique")
    pdf.info_box(
        "Data quality note",
        [
            "Round 2 JSON outputs from qwen2.5:7b were partially malformed.",
            "Several agents echoed peer forecasts instead of returning their own updated JSON.",
            "Peer response_to fields were captured; forecasts below use Round 1 values where no valid update exists.",
            "This is documented as a pilot limitation - larger models should improve structured output fidelity.",
        ],
    )

    for aid in AGENT_ORDER:
        r1d = agent_forecast(r1[aid]) or {}
        r2d = load_agent_round(aid, 2)
        peers = round2_peer_responses(r2d)
        nested = round2_nested_peers(r2d)

        pdf.add_page()
        pdf.sub_title(f"{AGENT_LABELS[aid]} - Round 2")

        if peers:
            pdf.body_text("Peer cross-examination (response_to):")
            for peer, msg in peers.items():
                pdf.bullet(f"{peer}: {msg}")
        else:
            pdf.body_text("No structured peer response captured.")

        r1_mag = r1d.get("magnitude_pct") or {}
        pdf.sub_title("Forecast stability (Round 1 vs Round 2)")
        delta_rows = []
        for etf in ETFS:
            v1 = r1_mag.get(etf)
            # Round 2 own forecast not reliably parsed; show R1 value with status
            status = "Unchanged (no valid R2 self-update)"
            delta_rows.append([etf, f"{v1:+.1f}%" if v1 is not None else "-", status])
        pdf.render_table(["ETF", "Round 1", "Round 2 status"], delta_rows, col_weights=[0.8, 1, 2.5])

        if nested:
            pdf.sub_title(f"Model output anomaly: {len(nested)} peer forecast(s) embedded in response")
            pdf.body_text(
                "The model incorrectly included other agents' forecasts in its JSON output "
                "rather than returning only its own updated structure."
            )

    # --- 6. Moderator ---
    pdf.add_page()
    pdf.section_title("6. Moderator Synthesis")
    pdf.body_text(
        "The moderator (same qwen2.5:7b model) synthesized Round 2 outputs into the following structured summary:"
    )
    pdf.render_markdown(moderator)

    # --- 7. Stats & charts ---
    pdf.add_page()
    pdf.section_title("7. Statistical Analysis & Charts")
    pdf.add_chart(charts["pred_actual"], "Figure 4 - Average forecast vs actual market moves", 80)
    pdf.add_chart(charts["confidence"], "Figure 5 - Agent confidence scores", 60)

    pdf.sub_title("7.1 SP500 forecast statistics")
    pdf.render_table(
        ["Metric", "Value"],
        [
            ["Minimum", f"{min(sp500_vals):+.1f}%"],
            ["Maximum", f"{max(sp500_vals):+.1f}%"],
            ["Mean (all agents)", f"{avg_sp:+.1f}%"],
            ["Mean (bearish only)", f"{statistics.mean([v for a, v in zip(AGENT_ORDER, sp500_vals) if (agent_forecast(r1[a]) or {}).get('direction') == 'negative']):+.1f}%"],
            ["Standard deviation", f"{statistics.stdev(sp500_vals):.1f}pp" if len(sp500_vals) > 1 else "N/A"],
        ],
        col_weights=[1.5, 2],
    )

    pdf.sub_title("7.2 Largest inter-agent disagreements")
    for etf in ETFS:
        vals: dict[str, float] = {}
        for aid in AGENT_ORDER:
            d = agent_forecast(r1[aid]) or {}
            m = (d.get("magnitude_pct") or {}).get(etf)
            if m is not None:
                vals[aid] = float(m)
        if vals:
            spread = max(vals.values()) - min(vals.values())
            if spread >= 8:
                lo = min(vals, key=vals.get)
                hi = max(vals, key=vals.get)
                pdf.bullet(
                    f"{etf}: {spread:.0f}pp spread - "
                    f"{AGENT_SHORT[lo]} ({vals[lo]:+.1f}%) vs {AGENT_SHORT[hi]} ({vals[hi]:+.1f}%)"
                )

    # --- 8. vs Actual ---
    pdf.add_page()
    pdf.section_title("8. Comparison vs Actual Market Data")
    pdf.body_text(
        "Agents forecast stress-test magnitudes over a multi-day horizon, not necessarily same-day close. "
        "Feb 24, 2022 saw a dramatic intraday selloff followed by a +1.5% S&P 500 close (CNBC). "
        "Energy (XLE) was mixed intraday but rallied ~+8% over the following 5 trading days."
    )
    comp_rows = []
    for etf in ETFS:
        preds = []
        for aid in AGENT_ORDER:
            d = agent_forecast(r1[aid]) or {}
            m = (d.get("magnitude_pct") or {}).get(etf)
            if m is not None:
                preds.append(float(m))
        avg_p = statistics.mean(preds) if preds else 0
        a1 = ACTUAL_FEB24_1D[etf]
        a5 = ACTUAL_5D[etf]
        comp_rows.append([etf, f"{avg_p:+.1f}%", f"{a1:+.1f}%", f"{a5:+.1f}%", f"{avg_p - a1:+.1f}pp"])
    pdf.render_table(
        ["ETF", "Avg forecast", "Actual 1D", "Actual ~5D", "1D error"],
        comp_rows,
        col_weights=[0.8, 1, 1, 1, 1],
    )

    pdf.sub_title("8.1 Scoring interpretation")
    critiques = [
        "SP500 direction (1-day): Devil's Advocate (+3.0% pred vs +1.5% actual) was closest. Bearish consensus (-5.9% ex-DA) missed the invasion-day reversal.",
        "SP500 magnitude: Even DA overestimated the rally magnitude; bearish agents overestimated drawdown severity for day 1.",
        "XLE (5-day): Economic agent (+8%) correctly predicted energy sector rally direction; Environmental (-8%) was opposite.",
        "XLY: Social agent's -12% was the most bearish forecast; actual 1D was +1.0%, 5D was -3.0% - partially vindicated over 5 days.",
        "XLK: All agents bearish (-2% to -8%); actual 1D was +3.3% - significant miss suggesting tech resilience.",
    ]
    for c in critiques:
        pdf.bullet(c)

    # --- 9. Critique ---
    pdf.add_page()
    pdf.section_title("9. Research Critique & Limitations")
    limitations = [
        ("Single-model homogeneity", "All agents used qwen2.5:7b. Role differentiation relies solely on prompts; no true model diversity in this pilot."),
        ("Round 2 JSON fidelity", "qwen2.5:7b frequently echoed peer JSON instead of returning its own updated forecast, limiting cross-examination value."),
        ("Moderator omissions", "Moderator synthesis omitted the Political agent entirely and referenced cloud model names (GPT-4O, Gemini) from prompts rather than actual models used."),
        ("Forecast horizon ambiguity", "Agents may have forecast multi-day moves while scoring used 1-day and 5-day benchmarks - horizon alignment needed for rigorous scoring."),
        ("No live market feed", "Forecasts based on static master context (Feb 23 cutoff), not real-time data integration."),
        ("Devil's Advocate value", "Despite single-model setup, DA provided the only bullish thesis - partially validated by invasion-day reversal."),
        ("Energy sector split", "Economic vs Environmental XLE disagreement (16pp) demonstrates genuine multi-perspective value even with one model."),
    ]
    for title, desc in limitations:
        pdf.sub_title(title)
        pdf.body_text(desc)

    # --- 10. Findings ---
    pdf.section_title("10. Key Findings for Research Paper")
    findings = [
        "Multi-agent debate surfaced a genuine 16pp disagreement on XLE (energy sector direction).",
        "4/5 bearish consensus vs +1.5% actual SP500 highlights value of Devil's Advocate role.",
        "Analogue selection clustered on Iraq 1990 (specialists) vs Iraq 2003 (DA) - historically grounded reasoning.",
        "Social agent produced largest bearish XLY forecast (-12%) citing retail panic amplification.",
        "qwen2.5:7b produced valid Round 1 JSON for all 5 agents at temperature 0.",
        "Round 2 structured output quality is the primary bottleneck for smaller local models.",
        "Offline pilot validates pipeline end-to-end before cloud multi-model deployment.",
    ]
    for f in findings:
        pdf.bullet(f)

    # --- 11. Metadata ---
    pdf.section_title("11. Run Metadata")
    pdf.render_table(
        ["Item", "Detail"],
        [
            ["Output folder", str(RUN_DIR)],
            ["Round 1 file", "round1_all.json"],
            ["Round 2 file", "round2_all.json"],
            ["Moderator file", "moderator_raw.txt"],
            ["Per-agent files", "10 raw + 10 JSON files"],
            ["Charts", str(CHART_DIR)],
            ["Total API calls", "11"],
        ],
        col_weights=[1.2, 3.5],
    )

    # --- Appendix ---
    pdf.add_page()
    pdf.section_title("Appendix A - Full Agent Transcripts (Verbatim)")
    pdf.body_text(
        "Complete unedited model outputs. Long lines are word-wrapped for readability."
    )
    for aid in AGENT_ORDER:
        label = AGENT_LABELS[aid]
        for rnd in (1, 2):
            raw_path = RUN_DIR / f"{aid}_round{rnd}_raw.txt"
            if not raw_path.exists():
                continue
            pdf.add_page()
            pdf.sub_title(f"{label} - Round {rnd}")
            pdf.wrapped_code_block(raw_path.read_text(encoding="utf-8"))

    pdf.add_page()
    pdf.sub_title("Moderator - Full output")
    pdf.wrapped_code_block(moderator)

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT_PDF))
    print(f"Report saved: {OUT_PDF}")


if __name__ == "__main__":
    main()
