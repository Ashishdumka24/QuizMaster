"""Matplotlib renderers for the SQC charts (guideline §7 step 6 requires
Pareto and Fishbone charts generated with Python/Matplotlib).

Each function returns PNG bytes. Used by the Quality Center pages and by
`tqm/generate_charts.py` for the written TQM report.
"""
from __future__ import annotations

import io
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

INK = "#1E1B4B"
MUTED = "#64748B"
GRID = "#E2E8F0"
PALETTE = ["#6366F1", "#8B5CF6", "#06B6D4", "#14B8A6", "#F97362", "#F59E0B", "#EC4899", "#3B82F6", "#22C55E",
           "#A855F7", "#0EA5E9"]


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _empty(title: str, message: str) -> bytes:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axis("off")
    ax.text(0.5, 0.6, title, ha="center", fontsize=15, color=INK, fontweight="bold")
    ax.text(0.5, 0.4, message, ha="center", fontsize=11, color=MUTED, wrap=True)
    return _png(fig)


def pareto_png(data: dict, title: str = "Pareto Analysis of Recorded Defects") -> bytes:
    items = data.get("items", [])
    if not items:
        return _empty(title, "No defects have been logged yet. Add entries in Quality Center → Defect Log.")
    labels = ["\n".join(textwrap.wrap(i["label"], 12)) for i in items]
    counts = [i["count"] for i in items]
    cum = [i["cum_pct"] for i in items]
    colors = ["#6366F1" if i["vital"] else "#C7D2FE" for i in items]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, counts, color=colors, edgecolor="white", linewidth=1.2, zorder=2)
    for b, c in zip(bars, counts):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), str(c), ha="center", va="bottom", fontsize=9,
                color=INK, fontweight="bold")
    ax.set_ylabel("Defect frequency (occurrences)", color=MUTED)
    _style(ax)
    ax2 = ax.twinx()
    ax2.plot(labels, cum, color="#F97362", marker="o", linewidth=2.4, zorder=3)
    ax2.axhline(80, color="#F59E0B", linestyle="--", linewidth=1.4)
    ax2.text(len(labels) - 0.5, 81.5, "80% cut-off", color="#B45309", fontsize=9, ha="right")
    ax2.set_ylim(0, 105)
    ax2.yaxis.set_major_formatter(PercentFormatter())
    ax2.tick_params(colors=MUTED, labelsize=9)
    for side in ("top",):
        ax2.spines[side].set_visible(False)
    ax2.set_ylabel("Cumulative %", color=MUTED)
    ax.set_title(title, color=INK, fontsize=14, fontweight="bold", loc="left", pad=14)
    vital = ", ".join(data.get("vital_few", []))
    fig.text(0.01, -0.04, f"Vital few (≈80% of occurrences): {vital}   •   Total occurrences: {data.get('total', 0)}",
             fontsize=9, color=MUTED)
    return _png(fig)


def fishbone_png(data: dict, title: str = "Ishikawa (Fishbone) Root-Cause Diagram") -> bytes:
    groups = data.get("groups", {})
    cats = list(groups.keys())[:4]
    while len(cats) < 4:
        cats.append(["People", "Process", "Software Code", "Infrastructure"][len(cats)])
    fig, ax = plt.subplots(figsize=(13, 6.8))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7)
    ax.axis("off")
    spine_y = 3.5
    ax.annotate("", xy=(10.3, spine_y), xytext=(0.4, spine_y),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.6, mutation_scale=22))
    effect = "\n".join(textwrap.wrap(data.get("effect", "Effect"), 20))
    ax.text(11.6, spine_y, effect, ha="center", va="center", fontsize=10.5, color="white", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.7", fc="#6366F1", ec="#4338CA", lw=1.5))
    positions = [(2.3, True), (6.3, True), (2.3, False), (6.3, False)]
    for idx, (cat, (x_end, top)) in enumerate(zip(cats, positions)):
        color = PALETTE[idx * 2 % len(PALETTE)]
        y_tip = 6.3 if top else 0.7
        x_tip = x_end - 1.6
        bone_end_x = x_end + 1.6
        ax.plot([x_tip, bone_end_x], [y_tip, spine_y], color=color, linewidth=2.2)
        ax.text(x_tip, y_tip + (0.28 if top else -0.28), cat, ha="center", va="center", fontsize=11,
                fontweight="bold", color="white", bbox=dict(boxstyle="round,pad=0.4", fc=color, ec=color))
        causes = groups.get(cat, [])[:5]
        if not causes:
            ax.text((x_tip + bone_end_x) / 2 + 0.3, (y_tip + spine_y) / 2, "(no causes logged)", fontsize=8,
                    color=MUTED, style="italic")
        for j, c in enumerate(causes):
            t = (j + 1) / (len(causes) + 1)
            bx = x_tip + (bone_end_x - x_tip) * t
            by = y_tip + (spine_y - y_tip) * t
            ax.plot([bx - 1.25, bx], [by, by], color=color, linewidth=1, alpha=0.8)
            label = textwrap.shorten(f"{c['cause']}", 46, placeholder="…")
            ax.text(bx - 1.3, by + 0.06, label, ha="right", va="bottom", fontsize=7.4, color=INK)
    ax.set_title(title, color=INK, fontsize=14, fontweight="bold", loc="left")
    return _png(fig)


def histogram_png(values: list[float], title: str = "Distribution of Quiz Scores (%)") -> bytes:
    if not values:
        return _empty(title, "No finished quiz attempts yet.")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist(values, bins=range(0, 110, 10), color="#8B5CF6", edgecolor="white", linewidth=1.5, zorder=2)
    _style(ax)
    ax.set_xlabel("Score %", color=MUTED)
    ax.set_ylabel("Attempts", color=MUTED)
    mean = sum(values) / len(values)
    ax.axvline(mean, color="#F97362", linestyle="--", linewidth=2)
    ax.text(mean + 1, ax.get_ylim()[1] * 0.92, f"mean {mean:.1f}%", color="#C2410C", fontsize=9)
    ax.set_title(title, color=INK, fontsize=14, fontweight="bold", loc="left")
    return _png(fig)


def control_chart_png(cc: dict, title: str = "I-MR Control Chart — Submission Processing Time") -> bytes:
    vals = cc.get("values", [])
    if len(vals) < 2:
        return _empty(title, "At least 2 submissions are needed (10+ recommended) before control limits are meaningful.")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = list(range(1, len(vals) + 1))
    ax.plot(x, vals, color="#6366F1", marker="o", markersize=4, linewidth=1.6, zorder=3)
    ax.axhline(cc["mean"], color="#14B8A6", linewidth=1.6, label=f"Mean {cc['mean']} ms")
    ax.axhline(cc["ucl"], color="#F97362", linestyle="--", linewidth=1.4, label=f"UCL {cc['ucl']} ms")
    ax.axhline(cc["lcl"], color="#F97362", linestyle="--", linewidth=1.4, label=f"LCL {cc['lcl']} ms")
    for i in cc.get("out_of_control", []):
        ax.plot(x[i], vals[i], "o", color="#DC2626", markersize=8, zorder=4)
    _style(ax)
    ax.set_xlabel("Submission (chronological)", color=MUTED)
    ax.set_ylabel("Processing time (ms)", color=MUTED)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    note = "" if cc.get("enough") else "  (fewer than 10 points — limits are provisional)"
    ax.set_title(title + note, color=INK, fontsize=13, fontweight="bold", loc="left")
    return _png(fig)


def fmea_png(items: list, title: str = "FMEA — Risk Priority Numbers (before vs after action)") -> bytes:
    if not items:
        return _empty(title, "No FMEA entries yet.")
    items = sorted(items, key=lambda i: i.rpn, reverse=True)[:12]
    labels = [textwrap.shorten(i.failure_mode, 38, placeholder="…") for i in items][::-1]
    before = [i.rpn for i in items][::-1]
    after = [i.new_rpn or 0 for i in items][::-1]
    fig, ax = plt.subplots(figsize=(10, 0.5 * len(items) + 1.6))
    y = range(len(items))
    ax.barh([v + 0.2 for v in y], before, height=0.4, color="#F97362", label="RPN (current)")
    ax.barh([v - 0.2 for v in y], after, height=0.4, color="#14B8A6", label="RPN (after action)")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(120, color="#F59E0B", linestyle="--", linewidth=1.2)
    ax.text(121, len(items) - 0.4, "action threshold 120", fontsize=8, color="#B45309")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title(title, color=INK, fontsize=13, fontweight="bold", loc="left")
    return _png(fig)
