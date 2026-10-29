"""Supervisor-review figures: iteration 3 only, one clear message per chart.

Distinct from figures_v3 (the technical/methodological figure set, which stays
in the written report). These four are simplified for a live presentation:
one message each, minimal panels, large type.

  s1_individual_differences.png   why we compare each rider to themselves
  s2_early_vs_late.png            the signal is late in the drive, not early
  s3_the_result.png               the primary registered result, one panel
  s4_model_summary.png            mixed-model coefficients, forest-plot style
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures_supervisor")

BLUE = "#2a78d6"
ORANGE = "#eb6834"
CRITICAL = "#d03b3b"
GREEN = "#1baf7a"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.edgecolor": BASE,
    "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.labelsize": 12,
    "xtick.labelsize": 11, "ytick.labelsize": 11,
    "figure.dpi": 120, "savefig.dpi": 190, "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print("wrote", name)


# ============================================================ S1
def s1_individual_differences(part):
    """Spaghetti plot: each rider's 3 ratings, sorted by their own average.
    Makes the ICC=0.69 finding visually self-evident: huge between-person
    spread, comparatively small within-person wiggle."""
    rows = []
    for _, r in part.iterrows():
        vals = [r.misc_d1, r.misc_d2, r.misc_d3]
        vals = [v for v in vals if pd.notna(v)]
        if len(vals) >= 2:
            rows.append((r.participant, vals))
    rows.sort(key=lambda x: np.mean(x[1]))

    fig, ax = plt.subplots(figsize=(11, 6.4))
    for i, (pid, vals) in enumerate(rows):
        x = np.linspace(-0.32, 0.32, len(vals)) + i
        ax.plot(x, vals, color=BASE, lw=1.3, alpha=0.85, zorder=2,
                marker="o", ms=3.2, markerfacecolor=BASE, markeredgewidth=0)
    means = [np.mean(v) for _, v in rows]
    ax.scatter(range(len(rows)), means, s=26, color=BLUE, zorder=4,
               label="each rider's average")

    ax.set_xlim(-1, len(rows))
    ax.set_ylim(-0.5, 10.8)
    ax.set_xticks([])
    ax.set_xlabel("48 riders, ordered from lowest to highest average sickness")
    ax.set_ylabel("MISC rating (0–10)")
    ax.legend(frameon=False, loc="upper left", fontsize=11)
    ax.set_title("Riders differ enormously from each other; each rider's own three "
                 "ratings stay fairly close together", pad=14)

    ax.annotate(
        "69% of all the differences\nyou see on this chart come from\n"
        "WHO is riding — not from anything\nthat happened in a particular drive.",
        xy=(len(rows) * 0.66, 8.7), fontsize=12, color=INK, fontweight="bold",
        ha="left", va="top",
        bbox=dict(boxstyle="round,pad=0.5", fc="#eef3fa", ec=BLUE, lw=1.2))

    fig.text(0.5, -0.02,
             "Each grey line = one rider's 3 drives (left to right = drive 1, 2, 3). "
             "Blue dot = that rider's own average.",
             ha="center", fontsize=10.5, color=INK2)
    fig.tight_layout()
    save(fig, "s1_individual_differences.png")


# ============================================================ S2
def s2_early_vs_late(el):
    """Single clean line: primary metric (steering IQR) correlation with that
    drive's rating, across the three matched-length windows."""
    fm = el[el.cohort == "feb_mar"]
    windows = [("early80_steer_iqr_deg", "first 80 seconds\nof the drive"),
               ("mid80_steer_iqr_deg", "middle 80 seconds"),
               ("late80_steer_iqr_deg", "last 80 seconds\nof the drive")]
    rhos, ps = [], []
    for col, _ in windows:
        sub = fm[[col, "misc"]].dropna()
        r, p = spearmanr(sub[col], sub["misc"])
        rhos.append(r)
        ps.append(p)

    fig, ax = plt.subplots(figsize=(9, 5.6))
    x = [0, 1, 2]
    ax.axhline(0, color=BASE, lw=1.2, zorder=1)
    ax.plot(x, rhos, color=BLUE, lw=2.8, zorder=3)
    for xi, r, p in zip(x, rhos, ps):
        sig = p < 0.05
        ax.scatter([xi], [r], s=190, color=BLUE if sig else BASE,
                   edgecolors=SURFACE, linewidths=2, zorder=4)
        ax.annotate(f"ρ = {r:+.2f}" + ("  (p < .05)" if sig else "  (n.s.)"),
                    (xi, r), textcoords="offset points",
                    xytext=(0, 16 if r >= 0 else -24), ha="center",
                    fontsize=12.5, fontweight="bold",
                    color=INK if sig else MUTED)
    ax.set_xticks(x)
    ax.set_xticklabels([w[1] for w in windows], fontsize=12)
    ax.set_ylabel("correlation with that drive's sickness rating")
    ax.set_ylim(-0.15, 0.35)
    ax.set_title("Steering only starts to reflect sickness partway through the "
                 "drive", pad=14)
    fig.text(0.5, -0.03,
             "Same 80-second window length used at each position, so this is a fair "
             "comparison — only WHERE in the drive changes.\n"
             "Data: 108 drives, February–March group (the larger, more consistent "
             "data-collection wave).",
             ha="center", fontsize=10.5, color=INK2)
    fig.tight_layout()
    save(fig, "s2_early_vs_late.png")


# ============================================================ S3
def s3_the_result(el):
    """The primary registered result: within-drive change in steering IQR
    vs the rating given after that drive. One panel, plain language."""
    col = "delta_steer_iqr_deg"
    sub = el[[col, "misc", "cohort"]].dropna()

    fig, ax = plt.subplots(figsize=(10, 6.2))
    for coh, c, lab in [("feb_mar", BLUE, "February–March"),
                        ("june", ORANGE, "June")]:
        s = sub[sub.cohort == coh]
        ax.scatter(s[col], s["misc"], s=60, color=c, alpha=0.8,
                   edgecolors=SURFACE, linewidths=1.1, zorder=3, label=lab)

    # simple OLS trend line for visual guidance
    z = np.polyfit(sub[col], sub["misc"], 1)
    xs = np.linspace(sub[col].min(), sub[col].max(), 100)
    ax.plot(xs, np.polyval(z, xs), color=INK, lw=2, ls="--", zorder=2, alpha=0.6)

    ax.axvline(0, color=BASE, lw=1.2, zorder=1)
    ax.set_ylim(-0.7, 10.8)
    ax.set_xlabel("change in steering wobble during the drive\n"
                 "(last 80s − first 80s; right = got wobblier)")
    ax.set_ylabel("sickness rating after that drive")
    ax.legend(frameon=False, loc="upper left", fontsize=11.5, title="data-collection wave")
    ax.set_title("Drives where steering got wobblier tended to end with a "
                 "worse rating", pad=14)

    ax.annotate(
        "The model result:\n+0.57 sickness points per extra\n"
        "unit of within-rider wobble increase\n(p = 0.0004)",
        xy=(0.98, 0.03), xycoords="axes fraction", ha="right", va="bottom",
        fontsize=12, color=INK, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.5", fc="#fff6ea", ec="#c98500", lw=1.2))

    fig.text(0.5, -0.02,
             "131 drives, 48 riders. Each dot = one drive. This is the pattern "
             "the mixed-effects model on the next chart confirms while accounting\n"
             "for practice, the two data-collection waves, and each rider's own "
             "typical sickness level.",
             ha="center", fontsize=10.5, color=INK2)
    fig.tight_layout()
    save(fig, "s3_the_result.png")


# ============================================================ S4
def s4_model_summary(mm):
    """Forest-plot style summary of the primary mixed model's key terms."""
    primary = mm[mm.model == "PRIMARY: delta steering IQR"].set_index("term")
    icc_row = mm[(mm.model == "null") & (mm.term == "ICC")]
    icc = float(icc_row.value.iloc[0]) if len(icc_row) else 0.69

    rows = [
        ("within_steer_iqr_deg", "Within-rider change in\nsteering wobble", BLUE),
        ("between_steer_iqr_deg", "Between-rider average\nsteering wobble", BASE),
        ("drive_c", "Drive number\n(practice / accumulation)", BASE),
        ("june", "June data-collection wave\n(vs February–March)", BASE),
    ]

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(11.5, 5.6),
        gridspec_kw={"width_ratios": [3, 1.15]})

    y = np.arange(len(rows))[::-1]
    for yi, (term, label, col) in zip(y, rows):
        est = primary.loc[term, "estimate"]
        lo = primary.loc[term, "ci_low"]
        hi = primary.loc[term, "ci_high"]
        p = primary.loc[term, "p"]
        sig = p < 0.05
        c = BLUE if (term == "within_steer_iqr_deg" and sig) else INK2
        ax.plot([lo, hi], [yi, yi], color=c, lw=2.6, zorder=2,
                solid_capstyle="round")
        ax.scatter([est], [yi], s=110, color=c, zorder=3,
                  edgecolors=SURFACE, linewidths=1.4)
        star = "  *" if sig else "  n.s."
        ax.annotate(f"{est:+.2f}{star}", (hi, yi), textcoords="offset points",
                    xytext=(10, 0), va="center", fontsize=11.5,
                    fontweight="bold" if sig else "normal",
                    color=c)
    ax.axvline(0, color=BASE, lw=1.2, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels([r[1] for r in rows], fontsize=11.5)
    ax.set_xlabel("effect on MISC rating (points)")
    ax.set_xlim(-1.8, 5.2)
    ax.set_title("What the model estimates, with 95% confidence ranges", pad=12,
                 fontsize=12.5)

    # ICC panel
    ax2.pie([icc, 1 - icc], colors=[CRITICAL, GRID], startangle=90,
           counterclock=False,
           wedgeprops=dict(width=0.42, edgecolor=SURFACE, linewidth=3))
    ax2.text(0, 0, f"{icc*100:.0f}%", ha="center", va="center",
             fontsize=30, fontweight="bold", color=INK)
    ax2.set_title("Share of all sickness\ndifferences explained\nsimply by "
                  "WHO is riding", fontsize=11.5, pad=10)
    ax2.set_aspect("equal")

    fig.text(0.5, -0.03,
             "* = statistically significant (p < .05). Bars show the range where the "
             "true effect most likely lies — the narrower and further from zero, "
             "the more confident the estimate.",
             ha="center", fontsize=10.2, color=INK2)
    fig.tight_layout()
    save(fig, "s4_model_summary.png")


def main():
    os.makedirs(FIG, exist_ok=True)
    part = pd.read_csv(os.path.join(HERE, "handlebar_participants_all.csv"))
    el = pd.read_csv(os.path.join(HERE, "early_late_drives.csv"))
    mm = pd.read_csv(os.path.join(HERE, "mixed_model_results.csv"))
    s1_individual_differences(part)
    s2_early_vs_late(el)
    s3_the_result(el)
    s4_model_summary(mm)


if __name__ == "__main__":
    main()
