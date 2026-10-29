"""Figures for the GROUP report (written separately; not included in this repo), RQ2 sections 4.4/4.5.

Styled to match the group report's existing figures (seaborn-like):
white axes with light grey grid, all four spines boxed, DejaVu Sans,
bold centred titles, Set2-style teal/coral palette, diamond mean markers,
framed legends, small grey footnotes under the axes.

  r1_individual_differences.png   -> section 4.4, after the ICC paragraph
  r2_early_vs_late.png            -> section 4.4, after the window paragraph
  r3_withindrive_scatter.png      -> section 4.5, after the model table
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures_report")

TEAL = "#66c2a5"     # Set2 teal (her Pre colour)
CORAL = "#fc8d62"    # Set2 coral (her Post colour)
GREY = "#999999"
INK = "#222222"
GRID = "#dddddd"
SPINE = "#cccccc"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": SPINE, "axes.linewidth": 1.0,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": True, "axes.spines.right": True,
    "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.labelsize": 11, "axes.labelcolor": INK,
    "xtick.labelsize": 10, "ytick.labelsize": 10,
    "xtick.color": INK, "ytick.color": INK,
    "legend.frameon": True, "legend.framealpha": 1.0,
    "legend.edgecolor": SPINE, "legend.fontsize": 10,
    "figure.dpi": 120, "savefig.dpi": 200, "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print("wrote", name)


def footnote(fig, text, y=-0.02):
    fig.text(0.5, y, text, ha="center", fontsize=9, color="#555555")


# ---------------------------------------------------------------- r1
def r1_individual_differences(part):
    rows = []
    for _, r in part.iterrows():
        vals = [r.misc_d1, r.misc_d2, r.misc_d3]
        vals = [v for v in vals if pd.notna(v)]
        if len(vals) >= 2:
            rows.append((r.participant, vals))
    rows.sort(key=lambda x: np.mean(x[1]))

    fig, ax = plt.subplots(figsize=(6.3, 3.6))
    for i, (pid, vals) in enumerate(rows):
        x = np.linspace(-0.3, 0.3, len(vals)) + i
        ax.plot(x, vals, color=GREY, lw=1.0, alpha=0.75, zorder=2,
                marker="o", ms=2.4, markerfacecolor=GREY, markeredgewidth=0)
    means = [np.mean(v) for _, v in rows]
    ax.scatter(range(len(rows)), means, s=34, marker="D", facecolor="white",
               edgecolor="black", linewidth=1.0, zorder=4,
               label="rider average")

    ax.set_xlim(-1, len(rows))
    ax.set_ylim(-0.5, 10.5)
    ax.set_xticks([])
    ax.set_xlabel("riders, ordered by average MISC rating")
    ax.set_ylabel("MISC rating (0–10)")
    ax.legend(loc="upper left")
    ax.set_title("Sickness ratings per rider across their drives")
    footnote(fig, "Each grey line connects one rider's post-drive ratings "
                  "(drive 1→3); 69% of rating variance is between riders "
                  "(ICC = 0.69).")
    save(fig, "r1_individual_differences.png")


# ---------------------------------------------------------------- r2
def r2_early_vs_late(el):
    fm = el[el.cohort == "feb_mar"]
    windows = [("early80_steer_iqr_deg", "first 80 s"),
               ("mid80_steer_iqr_deg", "middle 80 s"),
               ("late80_steer_iqr_deg", "last 80 s")]
    rhos, ps = [], []
    for col, _ in windows:
        sub = fm[[col, "misc"]].dropna()
        r, p = spearmanr(sub[col], sub["misc"])
        rhos.append(r)
        ps.append(p)

    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    x = [0, 1, 2]
    ax.axhline(0, color=GREY, lw=1.0, zorder=1)
    ax.plot(x, rhos, color=TEAL, lw=2.2, zorder=3)
    for xi, r, p in zip(x, rhos, ps):
        sig = p < 0.05
        ax.scatter([xi], [r], s=110, marker="D",
                   facecolor=TEAL if sig else "white",
                   edgecolor="black", linewidth=1.0, zorder=4)
        ax.annotate(f"ρ = {r:+.2f}" + ("*" if sig else " (n.s.)"),
                    (xi, r), textcoords="offset points",
                    xytext=(0, 13 if r >= 0 else -20), ha="center",
                    fontsize=10, fontweight="bold" if sig else "normal",
                    color=INK if sig else "#666666")
    ax.set_xticks(x)
    ax.set_xticklabels([w[1] for w in windows])
    ax.set_xlim(-0.35, 2.35)
    ax.set_ylabel("correlation with the drive's MISC rating")
    ax.set_ylim(-0.14, 0.34)
    ax.set_title("Steering–sickness correlation by window position")
    footnote(fig, "Steering IQR per 80-s window vs the post-drive rating; "
                  "first collection wave, 108 drives.  * p < .05.")
    save(fig, "r2_early_vs_late.png")


# ---------------------------------------------------------------- r3
def r3_withindrive_scatter(el):
    col = "delta_steer_iqr_deg"
    sub = el[[col, "misc", "cohort"]].dropna()

    fig, ax = plt.subplots(figsize=(6.3, 3.9))
    for coh, c, lab in [("feb_mar", TEAL, "February–March wave"),
                        ("june", CORAL, "June wave")]:
        s = sub[sub.cohort == coh]
        ax.scatter(s[col], s["misc"], s=26, color=c, alpha=0.75,
                   edgecolors="white", linewidths=0.5, zorder=3, label=lab)
    z = np.polyfit(sub[col], sub["misc"], 1)
    xs = np.linspace(sub[col].min(), sub[col].max(), 100)
    ax.plot(xs, np.polyval(z, xs), color="black", lw=1.4, ls="--",
            zorder=2, alpha=0.7)
    ax.axvline(0, color=GREY, lw=1.0, zorder=1)
    ax.set_ylim(-0.6, 10.6)
    ax.set_xlabel("change in steering IQR within the drive "
                 "(last 80 s − first 80 s, °)")
    ax.set_ylabel("MISC rating after the drive")
    ax.legend(loc="upper left")
    ax.set_title("Within-drive steering change vs post-drive rating")
    footnote(fig, "131 drives, 48 riders; dashed line: linear trend. The "
                  "mixed-effects model estimates +0.57 MISC per SD of "
                  "within-rider change (p < 0.001).", y=-0.08)
    save(fig, "r3_withindrive_scatter.png")


def main():
    os.makedirs(FIG, exist_ok=True)
    part = pd.read_csv(os.path.join(HERE, "handlebar_participants_all.csv"))
    el = pd.read_csv(os.path.join(HERE, "early_late_drives.csv"))
    r1_individual_differences(part)
    r2_early_vs_late(el)
    r3_withindrive_scatter(el)


if __name__ == "__main__":
    main()
