"""Phase 4: Figure set for report and slides.

Outputs to figures/:
  fig1_misc_trajectories.png   MISC vs drive, small multiples per participant
  fig2_feature_vs_misc.png     six feature-vs-MISC scatter panels with Spearman rho
  fig3_trajectory_maps.png     top-down path colored by speed, calm vs sick drive
  fig4_p62_escalation.png      P62 speed & steering per drive (2 -> 6 -> 10)
  fig5_p66_dropout.png         P66's single drive (vomited, dropped out)
  fig6_features_by_band.png    feature distributions by MISC band
  fig7_habituation.png         practice effect: smoother riding by drive 3

Palette: validated light-mode reference palette (dataviz skill).
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
CLEAN = os.path.join(HERE, "cleaned")

# --- palette (light mode) ---
BLUE = "#2a78d6"
ORANGE = "#eb6834"
CRITICAL = "#d03b3b"  # status: vomit / dropout markers (always with a label)
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
SURFACE = "#fcfcfb"
SEQ_BLUE = LinearSegmentedColormap.from_list(
    "seq_blue",
    ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
)

plt.rcParams.update(
    {
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": BASE,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 11,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 110,
        "savefig.dpi": 180,
        "savefig.bbox": "tight",
    }
)

STORY = {61: "steady", 62: "escalated to vomiting", 63: "worsening", 64: "mostly fine",
         65: "fluctuating", 66: "dropped out", 67: "adapted", 68: "severe throughout"}


def load(pid, drive):
    return pd.read_csv(os.path.join(CLEAN, f"P{pid}_drive{drive}.csv"))


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print("wrote", name)


def fig1(feats):
    fig, axes = plt.subplots(2, 4, figsize=(11, 5), sharex=True, sharey=True)
    for ax, pid in zip(axes.flat, sorted(feats.participant.unique())):
        sub = feats[feats.participant == pid].sort_values("drive")
        # MISC severity bands as recessive background
        ax.axhspan(1.5, 5.5, color="#f2f1ed", zorder=0)
        ax.axhspan(5.5, 10.5, color="#e8e6df", zorder=0)
        ax.plot(sub.drive, sub.misc, color=BLUE, lw=2, marker="o", ms=6, zorder=3)
        for _, r in sub.iterrows():
            if r.misc == 10:
                ax.plot(r.drive, r.misc, marker="X", ms=11, color=CRITICAL, zorder=4)
                ax.annotate("vomited", (r.drive, r.misc), textcoords="offset points",
                            xytext=(0, -13), ha="center", fontsize=8, color=CRITICAL)
        if pid == 66:
            ax.annotate("dropped out", (1, 10), textcoords="offset points",
                        xytext=(10, -30), fontsize=8, color=CRITICAL)
        ax.set_title(f"P{pid} — {STORY[pid]}", fontsize=9.5)
        ax.set_xticks([1, 2, 3])
        ax.set_ylim(-0.5, 10.9)
        ax.set_xlim(0.7, 3.3)
    axes[0, 0].set_ylabel("MISC (0–10)")
    axes[1, 0].set_ylabel("MISC (0–10)")
    for ax in axes[1]:
        ax.set_xlabel("drive")
    axes[0, 0].annotate("nausea band (6–10)", (0.8, 8.1), fontsize=7.5, color=MUTED)
    axes[0, 0].annotate("mild band (2–5)", (0.8, 4.6), fontsize=7.5, color=MUTED)
    fig.suptitle("Simulator sickness (MISC) after each drive — all participants",
                 fontsize=13, color=INK)
    fig.tight_layout()
    save(fig, "fig1_misc_trajectories.png")


def fig2(feats):
    panels = [
        ("steer_reversals_per_min", "steering reversals / min"),
        ("steer_std_deg", "steering deflection std (°)"),
        ("n_stops", "mid-drive stops (count)"),
        ("decel_p05_ms2", "strong braking, accel p05 (m/s²)"),
        ("accel_rms_ms2", "acceleration RMS (m/s²)"),
        ("speed_cv", "speed variability (CV)"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.4), sharey=True)
    rng = np.random.default_rng(7)
    jitter = rng.uniform(-0.15, 0.15, len(feats))
    for ax, (col, label) in zip(axes.flat, panels):
        rho, p = spearmanr(feats[col], feats.misc)
        ax.scatter(feats[col], feats.misc + jitter, s=42, color=BLUE, alpha=0.85,
                   edgecolors=SURFACE, linewidths=1, zorder=3)
        drop = feats[(feats.participant == 66)]
        ax.scatter(drop[col], drop.misc, s=70, marker="X", color=CRITICAL, zorder=4)
        ax.set_xlabel(label)
        ax.set_title(f"ρ = {rho:.2f}", fontsize=10, color=INK2)
        ax.set_ylim(-0.8, 11)
    for ax in axes[:, 0]:
        ax.set_ylabel("MISC after drive")
    axes[0, 0].annotate("P66 (dropout)",
                        (feats.loc[feats.participant == 66, panels[0][0]].iloc[0], 10),
                        textcoords="offset points", xytext=(8, -2), fontsize=8,
                        color=CRITICAL)
    fig.suptitle("Riding-behavior features vs post-drive sickness (22 drives, Spearman ρ)",
                 fontsize=13, color=INK)
    fig.tight_layout()
    save(fig, "fig2_feature_vs_misc.png")


def fig3():
    picks = [(64, 2, "calm: P64 drive 2 — MISC 0"),
             (65, 3, "sick: P65 drive 3 — MISC 6")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), sharex=True, sharey=True)
    sc = None
    for ax, (pid, d, title) in zip(axes, picks):
        df = load(pid, d)
        sc = ax.scatter(df.PosX, df.PosZ, c=df.speed_ms, cmap=SEQ_BLUE, vmin=0,
                        vmax=7.6, s=4)
        st = df.iloc[0]
        ax.plot(st.PosX, st.PosZ, marker="^", ms=10, color=INK, zorder=5)
        ax.annotate("start", (st.PosX, st.PosZ), textcoords="offset points",
                    xytext=(6, 6), fontsize=8.5, color=INK2)
        ax.set_title(title)
        ax.set_aspect("equal")
        ax.set_xlabel("PosX (m)")
        ax.grid(False)
    axes[0].set_ylabel("PosZ (m)")
    cb = fig.colorbar(sc, ax=axes, shrink=0.85, pad=0.02)
    cb.set_label("speed (m/s)", color=INK2)
    cb.ax.tick_params(colors=MUTED)
    fig.suptitle("Same route, top-down: riding speed of a symptom-free vs a nauseous drive",
                 fontsize=13, color=INK)
    fig.text(0.42, 0.045, "pale segments = slowed or stopped — the nauseous drive "
             "shows several; the symptom-free drive almost none",
             ha="center", fontsize=9.5, color=INK2)
    save(fig, "fig3_trajectory_maps.png")


def fig4():
    misc = {1: 2, 2: 6, 3: 10}
    fig, axes = plt.subplots(3, 2, figsize=(11, 7), sharex="col")
    for i, d in enumerate([1, 2, 3]):
        df = load(62, d)
        axes[i, 0].plot(df.t_s, df.speed_ms, color=BLUE, lw=1.2)
        axes[i, 1].plot(df.t_s, df.steer_deflection_deg, color=ORANGE, lw=1.0)
        axes[i, 0].set_ylabel(f"drive {d}\nspeed (m/s)")
        axes[i, 1].set_ylabel("steering (°)")
        axes[i, 1].set_ylim(-46, 46)
        axes[i, 0].set_ylim(-0.4, 8.2)
        label = f"MISC {misc[d]}" + ("  (vomited)" if misc[d] == 10 else "")
        axes[i, 1].annotate(label, xy=(0.99, 0.92), xycoords="axes fraction",
                            ha="right", fontsize=10, fontweight="bold",
                            color=CRITICAL if misc[d] == 10 else INK2)
    for ax in axes[2]:
        ax.set_xlabel("riding time (s)")
    fig.suptitle("P62 — riding behavior while sickness escalated 2 → 6 → 10 (vomiting)",
                 fontsize=13, color=INK)
    fig.tight_layout()
    save(fig, "fig4_p62_escalation.png")


def fig5():
    df = load(66, 1)
    fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    axes[0].plot(df.t_s, df.speed_ms, color=BLUE, lw=1.2)
    axes[0].set_ylabel("speed (m/s)")
    axes[1].plot(df.t_s, df.steer_deflection_deg, color=ORANGE, lw=1.0)
    axes[1].set_ylabel("steering deflection (°)")
    axes[1].set_xlabel("riding time (s)")
    fig.suptitle("P66 — the dropout's only drive\n"
                 "rated MISC 10 (vomiting) ~3 min after this drive — study stopped",
                 fontsize=12, color=CRITICAL)
    fig.tight_layout()
    save(fig, "fig5_p66_dropout.png")


def fig6(feats):
    bands = pd.cut(feats.misc, [-1, 1.5, 5.5, 10.5],
                   labels=["none\n(0–1)", "mild\n(2–5)", "nausea\n(6–10)"])
    panels = [
        ("steer_reversals_per_min", "steering reversals / min"),
        ("steer_std_deg", "steering deflection std (°)"),
        ("accel_rms_ms2", "acceleration RMS (m/s²)"),
        ("n_stops", "mid-drive stops (count)"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(11.5, 3.6))
    rng = np.random.default_rng(3)
    for ax, (col, label) in zip(axes, panels):
        groups = [feats.loc[bands == b, col] for b in bands.cat.categories]
        bp = ax.boxplot(groups, tick_labels=bands.cat.categories, widths=0.5,
                        showfliers=False,
                        boxprops=dict(color=INK2), whiskerprops=dict(color=INK2),
                        capprops=dict(color=INK2), medianprops=dict(color=INK, lw=2))
        for k, g in enumerate(groups):
            x = k + 1 + rng.uniform(-0.12, 0.12, len(g))
            ax.scatter(x, g, s=26, color=BLUE, alpha=0.8, zorder=3,
                       edgecolors=SURFACE, linewidths=0.8)
        ax.set_title(label, fontsize=9.5, color=INK2)
        ax.tick_params(axis="x", labelsize=8.5)
        ax.margins(y=0.09)
    fig.suptitle("Riding-behavior features by sickness band (each dot = one drive)",
                 fontsize=13, color=INK)
    fig.tight_layout()
    save(fig, "fig6_features_by_band.png")


def fig7(feats):
    panels = [("steer_reversals_per_min", "steering reversals / min"),
              ("speed_cv", "speed variability (CV)"),
              ("accel_rms_ms2", "acceleration RMS (m/s²)")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    for ax, (col, label) in zip(axes, panels):
        for pid in sorted(feats.participant.unique()):
            sub = feats[feats.participant == pid].sort_values("drive")
            if len(sub) < 2:
                continue
            ax.plot(sub.drive, sub[col], color=BASE, lw=1.2, marker="o", ms=3.5,
                    zorder=2)
        med = feats.groupby("drive")[col].median()
        ax.plot(med.index, med.values, color=BLUE, lw=2.6, marker="o", ms=7,
                zorder=4, label="median")
        ax.set_xticks([1, 2, 3])
        ax.set_xlabel("drive")
        ax.set_title(label, fontsize=10, color=INK2)
    axes[0].legend(frameon=False, fontsize=9)
    fig.suptitle("Practice effect: riding gets smoother across drives (gray = participants)",
                 fontsize=13, color=INK)
    fig.tight_layout()
    save(fig, "fig7_habituation.png")


def main():
    os.makedirs(FIG, exist_ok=True)
    feats = pd.read_csv(os.path.join(HERE, "features.csv"))
    fig1(feats)
    fig2(feats)
    fig3()
    fig4()
    fig5()
    fig6(feats)
    fig7(feats)


if __name__ == "__main__":
    main()
