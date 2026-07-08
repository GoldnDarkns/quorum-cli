#!/usr/bin/env python3
"""Generate a fully self-contained SPAR run HTML report (embedded screenshots, no external deps)."""

from __future__ import annotations

import base64
import html
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = Path(r"C:\Users\madha\spar_outputs\run_20260708_003305")
OUT_NAME = "SPAR_Complete_Standalone_Report.html"

# Reuse curated analysis from the PDF/HTML report generator
_spec = importlib.util.spec_from_file_location(
    "spar_report",
    ROOT / "scripts" / "generate_spar_round1_proof_report.py",
)
_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_report)


def load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def img_b64(path: Path) -> str:
    if not path.exists():
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def esc(text: object) -> str:
    return html.escape(str(text))


HBAR_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"]


def html_hbar_chart(
    labels: list[str],
    values: list[float],
    *,
    title: str,
    fmt: str = ".0f",
    vmin: float | None = None,
    vmax: float | None = None,
    chart_id: str = "chart",
) -> str:
    lo = vmin if vmin is not None else min(values + [0])
    hi = vmax if vmax is not None else max(values + [1])
    span = hi - lo or 1
    rows = []
    for i, (lab, val) in enumerate(zip(labels, values)):
        pct = max(3.0, (val - lo) / span * 100)
        c = HBAR_COLORS[i % len(HBAR_COLORS)]
        rows.append(
            f'<div class="hbar-row" style="--delay:{i * 0.06:.2f}s">'
            f'<div class="hbar-label" title="{esc(lab)}">{esc(lab)}</div>'
            f'<div class="hbar-track"><div class="hbar-fill" data-animate-bar '
            f'style="--target:{pct:.1f}%;--bar-color:{c}"></div></div>'
            f'<div class="hbar-val">{val:{fmt}}</div></div>'
        )
    return (
        f'<div class="chart-panel" id="{chart_id}">'
        f'<h4 class="chart-title">{esc(title)}</h4>'
        f'<div class="hbar-chart">{"".join(rows)}</div></div>'
    )


def svg_line_chart(
    points: list[tuple[str, float]],
    *,
    title: str,
    threshold: float | None = 0.35,
    width: int = 800,
    height: int = 280,
) -> str:
    pad_l, pad_r, pad_t, pad_b = 56, 40, 48, 52
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    vals = [p[1] for p in points]
    lo, hi = min(vals + [threshold or 0]) - 0.04, max(vals) + 0.04
    span = hi - lo or 1

    def y_pos(val: float) -> float:
        return pad_t + inner_h - (val - lo) / span * inner_h

    coords = []
    for i, (_lab, val) in enumerate(points):
        x = pad_l + (i / max(len(points) - 1, 1)) * inner_w
        coords.append((x, y_pos(val)))

    area_pts = (
        f"{pad_l},{pad_t + inner_h} "
        + " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        + f" {pad_l + inner_w},{pad_t + inner_h}"
    )
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    grid = []
    for tick in range(5):
        gy = pad_t + inner_h * tick / 4
        gv = hi - (hi - lo) * tick / 4
        grid.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + inner_w}" y2="{gy:.1f}" '
            f'stroke="#334155" stroke-opacity="0.45" stroke-dasharray="4 6"/>'
            f'<text x="{pad_l - 10}" y="{gy + 4:.1f}" text-anchor="end" font-size="11" '
            f'fill="#94a3b8">{gv:.2f}</text>'
        )

    threshold_line = ""
    if threshold is not None:
        ty = y_pos(threshold)
        threshold_line = (
            f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{pad_l + inner_w}" y2="{ty:.1f}" '
            f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="8 5" opacity="0.85"/>'
            f'<text x="{pad_l + inner_w + 6}" y="{ty + 4:.1f}" font-size="10" fill="#fbbf24">'
            f'τ={threshold}</text>'
        )

    dots = []
    for (x, y), (lab, val) in zip(coords, points):
        dots.append(
            f'<g class="dcs-point" style="--delay:{len(dots) * 0.15:.2f}s">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#1e293b" stroke="#60a5fa" stroke-width="2.5"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#93c5fd"/>'
            f'<text x="{x:.1f}" y="{y - 16:.1f}" text-anchor="middle" font-size="12" '
            f'font-weight="600" fill="#f8fafc">{val:.3f}</text>'
            f'<text x="{x:.1f}" y="{height - 18}" text-anchor="middle" font-size="12" '
            f'font-weight="600" fill="#cbd5e1">{esc(lab)}</text></g>'
        )

    return (
        f'<div class="chart-panel chart-panel-line">'
        f'<h4 class="chart-title">{esc(title)}</h4>'
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="auto" role="img" '
        f'aria-label="{esc(title)}" class="line-chart-svg">'
        f'<defs><linearGradient id="dcsArea" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#3b82f6" stop-opacity="0.35"/>'
        f'<stop offset="100%" stop-color="#3b82f6" stop-opacity="0.02"/></linearGradient></defs>'
        f'{"".join(grid)}{threshold_line}'
        f'<polygon points="{area_pts}" fill="url(#dcsArea)"/>'
        f'<polyline class="dcs-line" points="{poly}" fill="none" stroke="#60a5fa" '
        f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        f'{"".join(dots)}</svg></div>'
    )


def svg_round_trajectory(
    models: list[dict],
    *,
    title: str,
    width: int = 800,
    height: int = 300,
) -> str:
    pad_l, pad_r, pad_t, pad_b = 56, 24, 44, 48
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    rounds = [1, 2, 3, 4, 5]
    all_vals = [v for m in models for v in m["round_totals"].values() if v is not None]
    lo, hi = min(all_vals) - 3, max(all_vals) + 3
    span = hi - lo or 1
    lines = []
    legend = []
    for i, m in enumerate(models):
        color = HBAR_COLORS[i % len(HBAR_COLORS)]
        pts = []
        for ri, rnd in enumerate(rounds):
            val = m["round_totals"].get(rnd)
            if val is None:
                continue
            x = pad_l + ri / 4 * inner_w
            y = pad_t + inner_h - (val - lo) / span * inner_h
            pts.append(f"{x:.1f},{y:.1f}")
        if len(pts) < 2:
            continue
        short = m["display"].replace(" Latest", "").split()[0]
        lines.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="2.2" stroke-linecap="round" opacity="0.9"/>'
        )
        legend.append(
            f'<span class="legend-item"><i style="background:{color}"></i>{esc(short)}</span>'
        )
    xlabels = "".join(
        f'<text x="{pad_l + i / 4 * inner_w:.1f}" y="{height - 14}" text-anchor="middle" '
        f'font-size="11" fill="#94a3b8">R{rnd}</text>'
        for i, rnd in enumerate(rounds)
    )
    return (
        f'<div class="chart-panel chart-panel-line">'
        f'<h4 class="chart-title">{esc(title)}</h4>'
        f'<div class="chart-legend">{"".join(legend)}</div>'
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="auto" role="img" '
        f'aria-label="{esc(title)}">'
        f'<line x1="{pad_l}" y1="{pad_t + inner_h}" x2="{pad_l + inner_w}" y2="{pad_t + inner_h}" '
        f'stroke="#475569" stroke-width="1"/>'
        f'{xlabels}{"".join(lines)}</svg></div>'
    )


def kpi_card(
    label: str,
    value: str,
    sub: str = "",
    accent: str = "#3b82f6",
    *,
    animate: str = "",
) -> str:
    data_anim = f' data-animate="{esc(animate)}"' if animate else ""
    return f"""<div class="kpi" style="--accent:{accent}"{data_anim}>
  <div class="kpi-glow"></div>
  <div class="kpi-label">{esc(label)}</div>
  <div class="kpi-value">{esc(value)}</div>
  <div class="kpi-sub">{esc(sub)}</div>
</div>"""


def section_open(sid: str, title: str, lead: str = "") -> str:
    lead_html = f'<p class="section-lead">{esc(lead)}</p>' if lead else ""
    return f'<section id="{sid}" class="section"><h2>{esc(title)}</h2>{lead_html}'


def terminal_frame(step: int, total: int, title: str, caption: str, b64: str, phase: str) -> str:
    if not b64:
        return f'<div class="terminal missing"><p>Image missing: {esc(title)}</p></div>'
    return f"""<article class="terminal" id="step-{step}">
  <div class="terminal-meta">
    <span class="phase">{esc(phase)}</span>
    <span class="step-badge">Step {step} / {total}</span>
  </div>
  <h3 class="terminal-title">{esc(title)}</h3>
  <p class="terminal-caption">{esc(caption)}</p>
  <div class="terminal-screen"><img src="{b64}" alt="{esc(title)}" loading="lazy"/></div>
</article>"""


def phase_for_step(fname: str) -> str:
    if fname.startswith("01") or fname.startswith("02"):
        return "Startup"
    if fname.startswith(("03", "04")):
        return "Layer 0"
    if fname.startswith(tuple(f"{i:02d}" for i in range(5, 10))):
        return "Round 1"
    if "dcs_r2" in fname or fname.startswith("10"):
        return "Round 2"
    if "r3" in fname:
        return "Round 3"
    if "r4" in fname or fname == "21_dcs_r4.png":
        return "Round 4"
    if "r5" in fname:
        return "Round 5"
    if fname.startswith("25"):
        return "Moderator"
    if fname.startswith(("26", "27", "28")):
        return "Layer 3"
    return "Synthesis"


REPORT_CSS = r"""
:root {
  --bg:#060a14; --surface:rgba(17,24,39,.82); --card:rgba(30,41,59,.75);
  --card2:rgba(36,48,68,.9); --text:#f1f5f9; --muted:#a8b4c8;
  --accent:#3b82f6; --accent2:#8b5cf6; --good:#22c55e; --warn:#f59e0b;
  --bad:#ef4444; --border:rgba(148,163,184,.18); --radius:16px;
  --shadow:0 20px 50px rgba(0,0,0,.45); --mx:.5; --my:.3;
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body {
  margin:0; font-family:"Segoe UI",system-ui,-apple-system,sans-serif;
  background:var(--bg); color:var(--text); line-height:1.65; overflow-x:hidden;
}
.bg-canvas {
  position:fixed; inset:0; z-index:-3; pointer-events:none;
  background:
    radial-gradient(900px 600px at calc(var(--mx)*100%) calc(var(--my)*100%), rgba(59,130,246,.18), transparent 55%),
    radial-gradient(700px 500px at calc((1 - var(--mx))*80%) calc((1 - var(--my))*70%), rgba(139,92,246,.14), transparent 50%),
    radial-gradient(600px 400px at 50% 0%, rgba(6,182,212,.08), transparent 60%),
    linear-gradient(180deg,#060a14 0%,#0b1220 45%,#0f172a 100%);
  transition:background .15s ease-out;
}
.bg-grid {
  position:fixed; inset:0; z-index:-2; pointer-events:none; opacity:.35;
  background-image:
    linear-gradient(rgba(148,163,184,.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148,163,184,.06) 1px, transparent 1px);
  background-size:48px 48px;
  mask-image:radial-gradient(ellipse at center, black 30%, transparent 80%);
}
#cursor-glow {
  position:fixed; width:420px; height:420px; border-radius:50%;
  pointer-events:none; z-index:-1; transform:translate(-50%,-50%);
  background:radial-gradient(circle, rgba(59,130,246,.12) 0%, transparent 70%);
  transition:opacity .3s; opacity:.8;
}
a { color:#93c5fd; text-decoration:none; }
a:hover { color:#bfdbfe; }
.hero {
  padding:3.5rem 1.5rem 2.5rem; text-align:center; position:relative;
  border-bottom:1px solid var(--border);
}
.hero::after {
  content:""; position:absolute; inset:auto 0 0; height:1px;
  background:linear-gradient(90deg, transparent, rgba(59,130,246,.6), transparent);
}
.hero h1 {
  margin:0 0 .6rem; font-size:clamp(1.8rem,4.5vw,2.6rem); font-weight:800;
  background:linear-gradient(135deg,#f8fafc 0%,#93c5fd 50%,#c4b5fd 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.hero .subtitle { color:var(--muted); max-width:760px; margin:0 auto 1.5rem; font-size:1.02rem; }
.badge-row { display:flex; flex-wrap:wrap; gap:.55rem; justify-content:center; }
.badge {
  background:rgba(30,41,59,.7); border:1px solid var(--border); padding:.4rem .85rem;
  border-radius:999px; font-size:.8rem; color:#cbd5e1; backdrop-filter:blur(8px);
  animation:fadeUp .6s ease both;
}
.badge:nth-child(2){animation-delay:.05s}.badge:nth-child(3){animation-delay:.1s}
.badge:nth-child(4){animation-delay:.15s}.badge:nth-child(5){animation-delay:.2s}
.nav {
  position:sticky; top:0; z-index:200; background:rgba(6,10,20,.88);
  backdrop-filter:blur(14px); border-bottom:1px solid var(--border);
  padding:.65rem 1rem; display:flex; flex-wrap:wrap; gap:.45rem; justify-content:center;
}
.nav a {
  font-size:.78rem; padding:.4rem .75rem; border-radius:999px;
  background:rgba(30,41,59,.6); border:1px solid var(--border); color:#e2e8f0;
  transition:all .25s ease;
}
.nav a:hover, .nav a.active {
  background:linear-gradient(135deg,#2563eb,#7c3aed); border-color:transparent;
  color:#fff; text-decoration:none; transform:translateY(-1px);
  box-shadow:0 8px 24px rgba(59,130,246,.35);
}
.wrap { max-width:1140px; margin:0 auto; padding:1.75rem 1.25rem 5rem; }
.section {
  background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  padding:1.75rem 2rem; margin-bottom:1.75rem; box-shadow:var(--shadow);
  backdrop-filter:blur(12px); opacity:0; transform:translateY(24px);
  transition:opacity .6s ease, transform .6s ease;
}
.section.visible { opacity:1; transform:none; }
.section h2 {
  margin:0 0 .85rem; font-size:1.45rem; color:#f8fafc; font-weight:700;
  display:flex; align-items:center; gap:.6rem;
}
.section h2::before {
  content:""; width:4px; height:1.2em; border-radius:4px;
  background:linear-gradient(180deg,var(--accent),var(--accent2));
}
.section h3 { margin:1.5rem 0 .6rem; font-size:1.08rem; color:#e2e8f0; font-weight:600; }
.section-lead { color:var(--muted); margin:0 0 1.25rem; font-size:.95rem; max-width:900px; }
.kpi-grid {
  display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
  gap:1rem; margin:1.25rem 0;
}
.kpi {
  position:relative; background:var(--card); border:1px solid var(--border);
  border-radius:14px; padding:1.1rem 1.15rem; overflow:hidden;
  border-top:3px solid var(--accent); cursor:default;
  transition:transform .3s ease, box-shadow .3s ease, border-color .3s ease;
}
.kpi:hover {
  transform:translateY(-6px) scale(1.02);
  box-shadow:0 16px 40px rgba(0,0,0,.4), 0 0 0 1px rgba(59,130,246,.25);
  border-color:rgba(59,130,246,.4);
}
.kpi-glow {
  position:absolute; inset:-50%; opacity:0; pointer-events:none;
  background:radial-gradient(circle, var(--accent) 0%, transparent 60%);
  transition:opacity .4s;
}
.kpi:hover .kpi-glow { opacity:.08; }
.kpi-label {
  font-size:.72rem; text-transform:uppercase; letter-spacing:.08em;
  color:var(--muted); font-weight:600;
}
.kpi-value {
  font-size:clamp(1.4rem,3vw,1.85rem); font-weight:800; margin:.3rem 0;
  color:#f8fafc; font-variant-numeric:tabular-nums;
}
.kpi-sub { font-size:.8rem; color:#94a3b8; }
.pipeline-wrap { margin:1.5rem 0 .5rem; overflow-x:auto; padding-bottom:.5rem; }
.pipeline {
  display:flex; gap:0; align-items:stretch; min-width:max-content;
  font-size:.82rem; position:relative;
}
.pipeline .step {
  background:var(--card2); padding:.65rem 1rem; border:1px solid var(--border);
  position:relative; flex-shrink:0; transition:all .3s ease;
}
.pipeline .step:first-child { border-radius:10px 0 0 10px; }
.pipeline .step:last-child { border-radius:0 10px 10px 0; }
.pipeline .step:hover {
  background:rgba(59,130,246,.2); border-color:rgba(59,130,246,.5); z-index:2;
}
.pipeline .step-num {
  display:block; font-size:.65rem; color:var(--muted); text-transform:uppercase;
  letter-spacing:.06em; margin-bottom:.15rem;
}
.pipeline .arrow {
  display:flex; align-items:center; color:#64748b; padding:0 .15rem; font-size:.9rem;
}
table, .data-table {
  width:100%; border-collapse:separate; border-spacing:0;
  font-size:.86rem; margin:.85rem 0; border-radius:10px; overflow:hidden;
}
th, td { border:1px solid var(--border); padding:.6rem .75rem; text-align:left; }
th { background:rgba(36,48,68,.95); color:#f1f5f9; font-weight:600; font-size:.8rem; }
tr:nth-child(even) td { background:rgba(15,23,42,.35); }
tr:hover td { background:rgba(59,130,246,.08); }
.channel-name { color:#e2e8f0; font-weight:500; }
.tier-badge {
  display:inline-block; font-size:.68rem; font-weight:700; letter-spacing:.04em;
  padding:.2rem .5rem; border-radius:6px; text-transform:uppercase;
}
.tier-primary { background:rgba(34,197,94,.2); color:#86efac; border:1px solid rgba(34,197,94,.35); }
.tier-secondary { background:rgba(245,158,11,.15); color:#fcd34d; border:1px solid rgba(245,158,11,.3); }
.tier-watch { background:rgba(148,163,184,.15); color:#cbd5e1; border:1px solid rgba(148,163,184,.25); }
.score-hi { background:rgba(34,197,94,.18)!important; color:#86efac; font-weight:700; }
.score-md { background:rgba(245,158,11,.15)!important; color:#fcd34d; font-weight:600; }
.score-lo { background:rgba(239,68,68,.15)!important; color:#fca5a5; font-weight:600; }
.chart-box, .chart-grid { margin:1.25rem 0; }
.chart-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:1.25rem; }
.chart-panel {
  background:rgba(15,23,42,.55); border:1px solid var(--border); border-radius:14px;
  padding:1.25rem 1.35rem; overflow:hidden;
}
.chart-title {
  margin:0 0 1rem; font-size:.95rem; font-weight:700; color:#f8fafc;
  letter-spacing:.01em;
}
.hbar-chart { display:flex; flex-direction:column; gap:.65rem; }
.hbar-row {
  display:grid; grid-template-columns:minmax(160px,1.5fr) 1fr auto;
  gap:.75rem; align-items:center; opacity:0; animation:fadeUp .5s ease forwards;
  animation-delay:var(--delay,0s);
}
.hbar-label {
  font-size:.82rem; color:#e2e8f0; font-weight:500; line-height:1.3;
  text-align:right; padding-right:.25rem; word-break:break-word;
}
.hbar-track {
  height:22px; background:rgba(30,41,59,.8); border-radius:999px;
  overflow:hidden; border:1px solid rgba(71,85,105,.5);
}
.hbar-fill {
  height:100%; width:0; border-radius:999px;
  background:linear-gradient(90deg, var(--bar-color), color-mix(in srgb, var(--bar-color) 70%, white));
  box-shadow:0 0 12px color-mix(in srgb, var(--bar-color) 50%, transparent);
  transition:width 1.1s cubic-bezier(.22,1,.36,1);
}
.hbar-fill.animated { width:var(--target); }
.hbar-val {
  font-size:.9rem; font-weight:700; color:#f8fafc; min-width:2.5rem;
  font-variant-numeric:tabular-nums;
}
.chart-legend {
  display:flex; flex-wrap:wrap; gap:.5rem 1rem; margin-bottom:.75rem;
}
.legend-item {
  display:inline-flex; align-items:center; gap:.35rem; font-size:.75rem; color:#cbd5e1;
}
.legend-item i {
  display:inline-block; width:10px; height:10px; border-radius:50%;
}
.line-chart-svg { display:block; max-width:100%; }
.dcs-line {
  stroke-dasharray:1200; stroke-dashoffset:1200;
  animation:drawLine 1.8s ease forwards .3s;
}
.dcs-point { opacity:0; animation:popIn .5s ease forwards; animation-delay:calc(.8s + var(--delay,0s)); }
.grid-2 { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:1.25rem; }
.callout {
  background:linear-gradient(135deg,rgba(37,99,235,.18),rgba(139,92,246,.12));
  border:1px solid rgba(59,130,246,.35); border-left:4px solid var(--accent);
  border-radius:12px; padding:1rem 1.3rem; margin:1rem 0; font-size:.9rem;
  color:#e2e8f0;
}
.terminal {
  background:rgba(6,10,20,.85); border:1px solid #374151; border-radius:14px;
  padding:1.15rem; margin:1.5rem 0; transition:border-color .3s, box-shadow .3s;
}
.terminal:hover { border-color:rgba(59,130,246,.4); box-shadow:0 8px 32px rgba(0,0,0,.3); }
.terminal-meta { display:flex; justify-content:space-between; align-items:center; margin-bottom:.5rem; }
.phase {
  background:linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; font-size:.68rem;
  font-weight:700; padding:.25rem .6rem; border-radius:6px; text-transform:uppercase;
  letter-spacing:.04em;
}
.step-badge { font-size:.75rem; color:var(--muted); }
.terminal-title { margin:.3rem 0; font-size:1.02rem; color:#f1f5f9; font-weight:600; }
.terminal-caption { margin:0 0 .85rem; font-size:.86rem; color:var(--muted); line-height:1.5; }
.terminal-screen img {
  width:100%; border-radius:10px; border:1px solid #1f2937;
  display:block; cursor:zoom-in; transition:transform .3s ease;
}
.terminal-screen img:hover { transform:scale(1.01); }
.terminal.missing { color:var(--warn); }
.model-card {
  background:var(--card); border:1px solid var(--border); border-radius:14px;
  padding:1.15rem 1.3rem; margin:.85rem 0; transition:transform .25s, border-color .25s;
}
.model-card:hover { transform:translateX(4px); border-color:rgba(139,92,246,.4); }
.model-card h4 { margin:0 0 .4rem; color:#f8fafc; font-size:1rem; }
.tag {
  display:inline-block; font-size:.7rem; padding:.2rem .5rem; border-radius:6px;
  background:rgba(30,41,59,.8); border:1px solid var(--border); margin:.2rem .25rem .2rem 0;
}
.tag.good { border-color:rgba(34,197,94,.5); color:#86efac; background:rgba(34,197,94,.1); }
.tag.warn { border-color:rgba(245,158,11,.5); color:#fcd34d; background:rgba(245,158,11,.1); }
footer {
  text-align:center; padding:2.5rem 1rem; color:var(--muted); font-size:.85rem;
  border-top:1px solid var(--border);
}
@keyframes fadeUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:none} }
@keyframes drawLine { to{stroke-dashoffset:0} }
@keyframes popIn { from{opacity:0;transform:scale(.5)} to{opacity:1;transform:scale(1)} }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.7} }
.live-dot {
  display:inline-block; width:8px; height:8px; border-radius:50%;
  background:#22c55e; margin-right:.4rem; animation:pulse 2s ease infinite;
  box-shadow:0 0 8px #22c55e;
}
@media (max-width:640px) {
  .hbar-row { grid-template-columns:1fr; gap:.35rem; }
  .hbar-label { text-align:left; }
  .section { padding:1.25rem 1rem; }
}
@media print {
  .nav, #cursor-glow, .bg-canvas, .bg-grid { display:none; }
  .section { break-inside:avoid; box-shadow:none; opacity:1; transform:none; }
  body { background:#fff; color:#111; }
}
"""

REPORT_JS = r"""
(function(){
  const root = document.documentElement;
  const glow = document.getElementById('cursor-glow');
  let mx = 0.5, my = 0.3;
  document.addEventListener('mousemove', function(e) {
    mx = e.clientX / window.innerWidth;
    my = e.clientY / window.innerHeight;
    root.style.setProperty('--mx', mx);
    root.style.setProperty('--my', my);
    if (glow) { glow.style.left = e.clientX + 'px'; glow.style.top = e.clientY + 'px'; }
  });
  const sections = document.querySelectorAll('.section');
  const navLinks = document.querySelectorAll('.nav a');
  if (sections[0]) sections[0].classList.add('visible');
  const obs = new IntersectionObserver(function(entries) {
    entries.forEach(function(en) {
      if (en.isIntersecting) {
        en.target.classList.add('visible');
        en.target.querySelectorAll('[data-animate-bar]').forEach(function(bar) {
          bar.classList.add('animated');
        });
        const id = en.target.id;
        navLinks.forEach(function(a) {
          a.classList.toggle('active', a.getAttribute('href') === '#' + id);
        });
      }
    });
  }, { threshold: 0.12 });
  sections.forEach(function(s) { obs.observe(s); });
  document.querySelectorAll('.kpi[data-animate]').forEach(function(kpi) {
    const target = parseFloat(kpi.dataset.animate);
    const valEl = kpi.querySelector('.kpi-value');
    if (!valEl || isNaN(target)) return;
    const raw = valEl.textContent.trim();
    const prefix = raw.match(/^[^0-9.-]*/)[0] || '';
    const suffix = raw.match(/[^0-9.]*$/)[0] || '';
    const obsKpi = new IntersectionObserver(function(entries) {
      if (!entries[0].isIntersecting) return;
      let start = null;
      const dur = 1200;
      function step(ts) {
        if (!start) start = ts;
        const p = Math.min((ts - start) / dur, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        const cur = target * eased;
        valEl.textContent = prefix + (Math.abs(target) < 10 ? cur.toFixed(2) : cur.toFixed(target % 1 ? 3 : 0)) + suffix;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
      obsKpi.disconnect();
    }, { threshold: 0.5 });
    obsKpi.observe(kpi);
  });
  document.querySelectorAll('.terminal-screen img').forEach(function(img) {
    img.addEventListener('click', function() {
      const w = window.open('', '_blank');
      if (w) { w.document.write('<img src="' + img.src + '" style="max-width:100%"/>'); }
    });
  });
})();
"""


def build_standalone_html(run_dir: Path) -> str:
    shot_dir = run_dir / "report_screenshots"
    layer0 = load_json(run_dir / "layer0.json")
    bench = load_json(run_dir / "model_benchmark_report.json")
    dcs_scores = load_json(run_dir / "dcs_scores.json")
    gate = load_json(run_dir / "plausibility_gate.json")
    layer3 = load_json(run_dir / "layer3_quant.json")

    run_ts = None
    m = re.search(r"run_(\d{8})_(\d{6})", run_dir.name)
    if m:
        run_ts = datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S")

    # Embed all screenshots
    images: dict[str, str] = {}
    for fname, _, _ in _report.SCREENSHOTS:
        images[fname] = img_b64(shot_dir / fname)

    channels = layer0.get("channel_rankings", [])
    ch_names = [c.get("name", "") for c in channels[:10]]
    ch_scores = [float(c.get("score", 0)) for c in channels[:10]]

    debate_models = sorted(
        [m for m in _report.MODEL_EVALUATIONS if m["round_totals"].get(1) is not None],
        key=lambda x: x["composite"],
        reverse=True,
    )
    model_labels = [m["display"].replace(" Latest", "") for m in debate_models]
    model_composites = [m["composite"] for m in debate_models]

    dcs_points = [
        ("R2", _report.DCS_ROUND2_TERMINAL["dcs_score"]),
        ("R3", _report.DCS_ROUND3_TERMINAL["dcs_score"]),
        ("R4", _report.DCS_ROUND4_TERMINAL["dcs_score"]),
        ("R5", _report.DCS_ROUND5_TERMINAL["dcs_score"]),
    ]

    mod = _report.MODERATOR_TERMINAL
    pg = _report.PLAUSIBILITY_TERMINAL
    l3t = _report.LAYER3_TERMINAL
    pr = _report.PORTFOLIO_TERMINAL

    total_steps = len(_report.SCREENSHOTS)
    parts: list[str] = []

    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SPAR Complete Run Report — Liberation Day Tariffs 2025</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<div class="bg-canvas"></div>
<div class="bg-grid"></div>
<div id="cursor-glow"></div>
<header class="hero">
  <h1>SPAR — Complete Terminal Run Report</h1>
  <p class="subtitle"><span class="live-dot"></span>Interactive proof-of-work dashboard · Scenario Planning via Agentic Reasoning<br/>
  Liberation Day Tariffs (Apr 2, 2025) · SP Jain Group 3 · Quorum v1.1.4 · Offline Ollama</p>
  <div class="badge-row">
    <span class="badge">Run: {esc(run_dir.name)}</span>
    <span class="badge">Session: {run_ts.strftime("%Y-%m-%d %H:%M") if run_ts else "2026-07-08"}</span>
    <span class="badge">GPU: RTX 4060 Ti 8GB</span>
    <span class="badge">6 Models · 5 Debate Rounds</span>
    <span class="badge">Gate: CLEARED</span>
  </div>
</header>
<nav class="nav">
  <a href="#overview">Overview</a>
  <a href="#methodology">Methodology</a>
  <a href="#benchmarks">Benchmarks</a>
  <a href="#layer0">Layer 0</a>
  <a href="#debate">Debate</a>
  <a href="#evaluation">Model Evaluation</a>
  <a href="#outcomes">Outcomes</a>
  <a href="#terminal">Terminal Walkthrough</a>
</nav>
<main class="wrap">
""")

    # --- Overview KPIs ---
    parts.append(section_open(
        "overview", "Executive Dashboard",
        "Key performance indicators from the full SPAR pipeline run.",
    ))
    parts.append('<div class="kpi-grid">')
    parts.append(kpi_card("Scenario", "liberation_day_2025", "Trade policy shock · 5-day horizon", "#8b5cf6"))
    parts.append(kpi_card("Channels Activated", "7 PRIMARY", "4 secondary · 2 watchlist", "#3b82f6"))
    parts.append(kpi_card("Debate Rounds", "4 live", "Rounds 2–5 + DCS gates", "#06b6d4"))
    parts.append(kpi_card("Final DCS", f"{_report.DCS_ROUND5_TERMINAL['dcs_score']:.3f}", "EXPLOIT (max cap)", "#f59e0b", animate="0.761"))
    parts.append(kpi_card("Plausibility", f"{pg['composite_score']}/100", "CLEARED · τ=60", "#22c55e", animate="70"))
    parts.append(kpi_card("Consensus SP500", f"{mod['consensus']['magnitude_pct']['SP500']:+.1f}%", "5-day moderator forecast", "#ef4444", animate="-3.5"))
    parts.append(kpi_card("Portfolio P&L", f"{l3t['consensus_portfolio_pnl_pct']:+.2f}%", "Consensus scenario shock", "#ef4444", animate="-5.66"))
    parts.append(kpi_card("VaR After Hedge", f"{pr['var_after_pct']:.2f}%", f"from {pr['var_before_pct']:.2f}%", "#22c55e", animate="5.85"))
    parts.append("</div>")

    parts.append('<div class="pipeline-wrap"><div class="pipeline">')
    pipeline_steps = [
        "Layer 0", "Benchmarks", "Round 1", "R2–R5 Debate", "DCS", "Moderator",
        "Plausibility Gate", "Layer 3", "Portfolio REC",
    ]
    for i, s in enumerate(pipeline_steps, 1):
        if i > 1:
            parts.append('<span class="arrow">→</span>')
        parts.append(f'<span class="step"><span class="step-num">Step {i}</span>{esc(s)}</span>')
    parts.append("</div></div></section>")

    # --- Methodology ---
    parts.append(section_open(
        "methodology", "What We Built & Why",
        "SPAR orchestrates six domain-specialist LLMs through a structured scenario-planning pipeline.",
    ))
    parts.append("""<div class="grid-2">
<div><h3>What is SPAR?</h3>
<p><strong>Scenario Planning via Agentic Reasoning</strong> — a multi-agent system where offline LLMs debate
macro-financial transmission channels, converge (or preserve dissent), pass a plausibility gate aligned to
Federal Reserve Financial Stability Report excerpts, and output quantitative portfolio recommendations.</p>
<h3>Why this scenario?</h3>
<p><em>Liberation Day Tariffs (Apr 2, 2025)</em> — broad reciprocal US tariffs on major trading partners.
Tests trade-policy shock propagation through 13 curated transmission channels with historical evidence corpora.</p>
</div>
<div><h3>How we ran it</h3>
<ul>
<li><strong>Platform:</strong> Quorum CLI v1.1.4 · <code>/method spar</code></li>
<li><strong>Models:</strong> 6 Ollama models (Phi4, Nemotron, Granite, Llama, Qwen, Gemma)</li>
<li><strong>Hardware:</strong> NVIDIA RTX 4060 Ti 8GB — fully offline</li>
<li><strong>Preset:</strong> demo-diverse benchmark stack</li>
<li><strong>Debate control:</strong> DCS (Debate Continuation Score) — EXPLORE until round cap</li>
</ul>
<h3>Runtime role assignment</h3>
<p>Models were assigned to SPAR roles in session order (not benchmark preset order).
See evaluation section for impact on performance.</p>
</div></div></section>""")

    # --- Benchmarks ---
    parts.append(section_open(
        "benchmarks", "Model Benchmark Analysis (demo-diverse)",
        "Public leaderboard scores inform model selection before the live run.",
    ))
    parts.append("<table><tr><th>Rank</th><th>Model</th><th>Provider</th><th>Overall</th><th>Role-Fit</th><th>Preset Role</th></tr>")
    for i, (role, mid, prov, overall, fit) in enumerate(_report.BENCHMARK_PRESET_ROLES, 1):
        parts.append(f"<tr><td>{i}</td><td>{esc(mid)}</td><td>{esc(prov)}</td><td>{overall:.1f}</td><td>{fit:.1f}</td><td>{esc(role)}</td></tr>")
    parts.append("</table>")
    parts.append("<h3>Runtime vs Preset Assignment</h3><table><tr><th>Model</th><th>Runtime Role</th><th>Preset Role</th><th>Benchmark Fit</th></tr>")
    for m in _report.MODEL_EVALUATIONS:
        parts.append(
            f"<tr><td>{esc(m['display'])}</td><td>{esc(m['runtime_role'])}</td>"
            f"<td>{esc(m['preset_role'])}</td><td>{m['benchmark_role_fit']:.1f}</td></tr>"
        )
    parts.append("</table></section>")

    # --- Layer 0 ---
    parts.append(section_open(
        "layer0", "Layer 0 — Transmission Channel Prioritization",
        "13 channels scored from shock text, macro regime, and historical evidence corpus.",
    ))
    parts.append('<div class="chart-box">')
    parts.append(html_hbar_chart(ch_names, ch_scores, title="Top 10 Channel Scores", vmin=0, vmax=100, chart_id="layer0-chart"))
    parts.append("</div>")
    parts.append("<h3>Full Channel Rankings</h3>")
    parts.append('<table class="data-table"><tr><th>Tier</th><th>Channel</th><th>Score</th><th>Evidence</th></tr>')
    for ch in channels:
        tier = ch.get("priority", "").upper()
        tier_cls = {"PRIMARY": "tier-primary", "SECONDARY": "tier-secondary", "WATCHLIST": "tier-watch"}.get(tier, "")
        parts.append(
            f'<tr><td><span class="tier-badge {tier_cls}">{esc(tier)}</span></td>'
            f'<td class="channel-name">{esc(ch.get("name", ""))}</td>'
            f'<td><strong>{float(ch.get("score", 0)):.1f}</strong></td>'
            f'<td>{int(ch.get("evidence_count", 0))} docs</td></tr>'
        )
    parts.append("</table></section>")

    # --- Debate summary ---
    parts.append(section_open(
        "debate", "Live Debate Rounds 2–5",
        "Agents cross-examine each other's Round 1 views. Phi4 Mini computes DCS after each round.",
    ))
    parts.append('<div class="chart-grid">')
    parts.append(svg_line_chart(dcs_points, title="DCS Progression — Rounds 2 to 5 (τ = 0.35)", threshold=0.35))
    parts.append("</div>")
    parts.append("<table><tr><th>Round</th><th>DCS</th><th>Action</th><th>Info Gain</th><th>Note</th></tr>")
    dcs_rows = [
        ("2", "0.793", "EXPLORE", "1.000", "78% novel vocabulary"),
        ("3", "0.746", "EXPLORE", "0.912", "Consumer convergence begins"),
        ("4", "0.769", "EXPLORE", "1.000", "GPR re-introduced"),
        ("5", "0.761", "EXPLOIT", "0.984", "Max round cap reached"),
    ]
    for row in dcs_rows:
        parts.append(f"<tr>{''.join(f'<td>{esc(c)}</td>' for c in row)}</tr>")
    parts.append("</table>")

    for rnd, summaries, dcs in [
        (2, _report.ROUND2_AGENT_SUMMARIES, _report.DCS_ROUND2_TERMINAL),
        (3, _report.ROUND3_AGENT_SUMMARIES, _report.DCS_ROUND3_TERMINAL),
        (4, _report.ROUND4_AGENT_SUMMARIES, _report.DCS_ROUND4_TERMINAL),
        (5, _report.ROUND5_AGENT_SUMMARIES, _report.DCS_ROUND5_TERMINAL),
    ]:
        parts.append(f"<h3>Round {rnd} Summary</h3>")
        for agent_title, bullets in summaries:
            parts.append(f"<p><strong>{esc(agent_title)}</strong></p><ul>")
            for b in bullets[:4]:
                parts.append(f"<li>{esc(b)}</li>")
            parts.append("</ul>")
        parts.append(
            f'<p class="callout"><strong>DCS after R{rnd}:</strong> {dcs["dcs_score"]:.3f} — '
            f'{esc(dcs["action"])} · {esc(dcs["reason"])}</p>'
        )
    parts.append("</section>")

    # --- Model evaluation ---
    parts.append(section_open(
        "evaluation", "Cross-Model Performance Evaluation",
        "Rubric-weighted scores (0–100) across all rounds. See rubric below.",
    ))
    parts.append("<table><tr><th>Dimension</th><th>Weight</th><th>Criterion</th></tr>")
    for _k, label, weight, desc in _report.EVALUATION_RUBRIC:
        parts.append(f"<tr><td>{esc(label)}</td><td>{weight}%</td><td>{esc(desc)}</td></tr>")
    parts.append("</table>")

    parts.append('<div class="chart-grid">')
    parts.append(html_hbar_chart(
        model_labels, model_composites,
        title="Debate Agent Composite Scores (Rounds 1–5)",
        vmin=50, vmax=90, fmt=".1f", chart_id="model-composite-chart",
    ))
    parts.append(svg_round_trajectory(debate_models, title="Per-Round Score Trajectories"))
    parts.append("</div>")

    parts.append("<h3>Per-Round Score Matrix</h3>")
    parts.append("<table><tr><th>Model</th><th>R1</th><th>R2</th><th>R3</th><th>R4</th><th>R5</th><th>Δ</th></tr>")
    for m in debate_models:
        r = m["round_totals"]
        delta = r[5] - r[1]

        def sc(v: int) -> str:
            cls = "score-hi" if v >= 80 else ("score-md" if v >= 65 else "score-lo")
            return f'<td class="{cls}">{v}</td>'

        parts.append(
            f"<tr><td>{esc(m['display'])}</td>"
            f"{sc(r[1])}{sc(r[2])}{sc(r[3])}{sc(r[4])}{sc(r[5])}"
            f"<td>{delta:+d}</td></tr>"
        )
    parts.append("</table>")

    for m in debate_models:
        parts.append(f'<div class="model-card"><h4>{esc(m["display"])} — {esc(m["runtime_role"])} '
                     f'(composite {m["composite"]:.1f})</h4>')
        parts.append(f'<p><em>{esc(m["trajectory"])}</em></p>')
        for s in m["strengths"]:
            parts.append(f'<span class="tag good">{esc(s)}</span>')
        for w in m["weaknesses"]:
            parts.append(f'<span class="tag warn">{esc(w)}</span>')
        parts.append("<ul>")
        for rev in m["revisions"]:
            parts.append(f"<li>{esc(rev)}</li>")
        parts.append("</ul></div>")

    parts.append("<h3>Peer Agreement Matrix</h3><table><tr><th>Agent A</th><th>Agent B</th>"
                 "<th>Agreement</th><th>Tension</th><th>Topic</th></tr>")
    for row in _report.PEER_AGREEMENT_MATRIX:
        parts.append(f"<tr>{''.join(f'<td>{esc(c)}</td>' for c in row)}</tr>")
    parts.append("</table></section>")

    # --- Outcomes ---
    parts.append(section_open(
        "outcomes", "Moderator, Plausibility Gate & Portfolio",
        "Final synthesis and hedge-fund-style portfolio recommendation.",
    ))
    c = mod["consensus"]
    d = mod["dissent"]
    parts.append('<div class="grid-2"><div>')
    parts.append(f"<h3>Consensus ({mod['model']})</h3>")
    parts.append(f"<p>Direction: <strong>{c['direction']}</strong> · Confidence: {c['confidence']} · "
                 f"Plausibility: {c['plausibility_score']}/100</p>")
    parts.append("<table><tr><th>ETF</th><th>5d %</th></tr>")
    for etf, mv in c["magnitude_pct"].items():
        parts.append(f"<tr><td>{etf}</td><td>{mv:+.2f}%</td></tr>")
    parts.append("</table></div><div>")
    parts.append("<h3>Minority Dissent (preserved)</h3>")
    parts.append(f"<p>Agents: {', '.join(d['agents'])} · Plausibility: {d['plausibility_score']}/100</p>")
    parts.append("<table><tr><th>ETF</th><th>Dissent 5d %</th></tr>")
    for etf, mv in d["magnitude_pct"].items():
        parts.append(f"<tr><td>{etf}</td><td>{mv:+.2f}%</td></tr>")
    parts.append("</table></div></div>")

    parts.append(f"""<div class="callout">
<strong>Plausibility Gate:</strong> {pg['decision']} — composite {pg['composite_score']}/100
(mod {pg['moderator_score']}, FSR {pg['fsr_score']}) · Top FSR match: {pg['top_fsr_match'][0]}
</div>""")

    parts.append("<h3>Recommended Trades</h3><table><tr><th>Action</th><th>Asset</th><th>From</th><th>To</th><th>Δ pp</th></tr>")
    for action, asset, fr, to, delta in pr["trades"]:
        parts.append(f"<tr><td>{action}</td><td>{asset}</td><td>{fr:.1f}%</td><td>{to:.1f}%</td><td>{delta:+.1f}</td></tr>")
    parts.append("</table></section>")

    # --- Terminal walkthrough ---
    parts.append(section_open(
        "terminal", "Complete Terminal Walkthrough",
        f"All {total_steps} screenshots embedded below — scroll to relive the full session.",
    ))
    for i, (fname, title, caption) in enumerate(_report.SCREENSHOTS, 1):
        parts.append(terminal_frame(
            i, total_steps, title, caption, images.get(fname, ""), phase_for_step(fname),
        ))
    parts.append("</section>")

    parts.append(f"""<footer>
<p>SPAR Complete Standalone Report · Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
<p>SP Jain Group 3 · Quorum CLI · All images embedded — share this single HTML file</p>
<p>Artifacts: {esc(_report.PIPELINE_SUMMARY_TERMINAL['artifacts_path'])}</p>
</footer>
</main>
<script>{REPORT_JS}</script>
</body>
</html>""")

    return "".join(parts)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate self-contained SPAR HTML report")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    out = args.output or (args.run_dir / OUT_NAME)
    content = build_standalone_html(args.run_dir)
    out.write_text(content, encoding="utf-8")
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"Written: {out}")
    print(f"Size: {size_mb:.2f} MB (self-contained, {len(_report.SCREENSHOTS)} screenshots embedded)")


if __name__ == "__main__":
    main()
