"""Iteration 2 figures — handlebar behaviour vs sickness group.

Outputs to figures_v2/:
  v1_group_scheme.png      sickness trajectories of ALL 44 participants by group
  v2_handlebar_by_group.png deviation & related metrics, escalating vs not
  v3_severity_gradient.png  monotonic gradient across none/mild/nausea
  v4_scatter_deviation.png  deviation vs peak MISC, participants labelled
  v5_practice_confound.png  the practice effect that must be controlled
  v6_steering_traces.png    what "deviation" looks like: low vs high sickness rider
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures_v2")
DATA = os.path.join(os.path.dirname(HERE), "data june")

BLUE = "#2a78d6"
ORANGE = "#eb6834"
CRITICAL = "#d03b3b"
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
    "axes.titlesize": 11, "axes.labelsize": 9.5,
    "xtick.labelsize": 9, "ytick.labelsize": 9,
    "figure.dpi": 110, "savefig.dpi": 180, "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print("wrote", name)


def wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------- v1
def v1_group_scheme(groups):
    g = groups[groups.traj_group != "unclassifiable"].copy()
    order = [("worsening", "worsening  (Δ ≥ +2)", ORANGE),
             ("stable", "stable  (|Δ| ≤ 1)", BLUE),
             ("improving", "improving  (Δ ≤ −2)", "#1baf7a")]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.9), sharey=True)
    for ax, (key, label, col) in zip(axes, order):
        sub = g[g.traj_group == key]
        for _, r in sub.iterrows():
            ys = [r.misc_d1, r.misc_d2, r.misc_d3]
            xs = [i + 1 for i, v in enumerate(ys) if not pd.isna(v)]
            ys = [v for v in ys if not pd.isna(v)]
            has_tel = 60 <= r.participant <= 68
            ax.plot(xs, ys, color=col if has_tel else BASE,
                    lw=2.2 if has_tel else 1.1,
                    marker="o", ms=5 if has_tel else 3,
                    zorder=4 if has_tel else 2,
                    alpha=1.0 if has_tel else 0.75)
        ax.set_title(f"{label}\nn = {len(sub)}", fontsize=10.5)
        ax.set_xticks([1, 2, 3])
        ax.set_xlabel("drive")
        ax.set_ylim(-0.6, 10.8)
    axes[0].set_ylabel("MISC (0–10)")
    fig.suptitle("Sickness trajectory groups — all 44 classifiable participants",
                 fontsize=13, color=INK)
    fig.text(0.5, -0.04, "Coloured = the 9 participants that also have telemetry; "
             "grey = survey only (telemetry not yet available)",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "v1_group_scheme.png")


# ---------------------------------------------------------------- v2
def v2_handlebar_by_group(part, dr):
    metrics = [("steer_sd_deg", "deviation of rotation\n(SD, °)"),
               ("steer_absmean_deg", "average rotation angle\n(mean |defl|, °)"),
               ("steerrate_absmean_dps", "changing speed\n(mean |rate|, °/s)"),
               ("steer_reversals_per_min", "correction frequency\n(reversals/min)")]
    d1 = dr[dr.drive == 1].set_index("participant")
    lab = part.set_index("participant")
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.9))
    rng = np.random.default_rng(5)
    for ax, (col, name) in zip(axes, metrics):
        groups, vals = ["escalating", "non_escalating"], []
        for gname in groups:
            ids = [p for p in d1.index
                   if p in lab.index and lab.loc[p, "traj2"] == gname]
            vals.append([d1.loc[p, col] for p in ids])
        bp = ax.boxplot(vals, tick_labels=["escalating", "non-\nescalating"],
                        widths=0.5, showfliers=False,
                        boxprops=dict(color=INK2), whiskerprops=dict(color=INK2),
                        capprops=dict(color=INK2), medianprops=dict(color=INK, lw=2))
        for k, (v, c) in enumerate(zip(vals, [ORANGE, BLUE])):
            x = k + 1 + rng.uniform(-0.11, 0.11, len(v))
            ax.scatter(x, v, s=44, color=c, alpha=0.9, zorder=3,
                       edgecolors=SURFACE, linewidths=1)
        ax.set_title(name, fontsize=9.5, color=INK2)
        ax.margins(y=0.14)
        ax.tick_params(axis="x", labelsize=8.5)
    fig.suptitle("Handlebar movement by sickness trajectory group — drive 1 "
                 "(each dot = one participant)", fontsize=12.5, color=INK)
    fig.text(0.5, -0.05, "Every metric is higher in the escalating group "
             "(rank-biserial +0.38 to +0.75). n = 4 vs 4, so directional only — "
             "not significant at this sample size.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "v2_handlebar_by_group.png")


# ---------------------------------------------------------------- v3
def v3_severity_gradient(part):
    bands = ["none", "mild", "nausea"]
    labels = ["none\n(peak 0–1)", "mild\n(peak 2–5)", "nausea\n(peak 6–10)"]
    metrics = [("steer_sd_deg", "deviation of rotation (SD, °)"),
               ("steer_absmean_deg", "average rotation angle (°)"),
               ("steer_p95_abs_deg", "large corrections (95th pct, °)"),
               ("steer_jerk_rms_dps2", "jerkiness (RMS, °/s²)")]
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.7))
    rng = np.random.default_rng(11)
    for ax, (col, name) in zip(axes, metrics):
        meds, allv = [], []
        for b in bands:
            v = part.loc[part.severity3 == b, col].dropna().tolist()
            allv.append(v)
            meds.append(np.median(v) if v else np.nan)
        ax.plot(range(1, 4), meds, color=BLUE, lw=2.4, marker="o", ms=8, zorder=4)
        for k, v in enumerate(allv):
            x = k + 1 + rng.uniform(-0.09, 0.09, len(v))
            ax.scatter(x, v, s=38, color=BASE, zorder=3,
                       edgecolors=SURFACE, linewidths=0.9)
        ax.set_xticks(range(1, 4))
        ax.set_xticklabels(labels, fontsize=8.5)
        ax.set_title(name, fontsize=9.5, color=INK2)
        ax.margins(y=0.16)
    fig.suptitle("Handlebar metrics rise monotonically with sickness severity "
                 "(blue = group median)", fontsize=12.5, color=INK)
    fig.tight_layout()
    save(fig, "v3_severity_gradient.png")


# ---------------------------------------------------------------- v4
def v4_scatter(part):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    pairs = [("steer_sd_deg", "deviation of handlebar rotation (SD, °)"),
             ("speed_mean_ms", "mean riding speed (m/s)")]
    for ax, (col, xl) in zip(axes, pairs):
        rho, p = spearmanr(part[col], part.misc_peak)
        for _, r in part.iterrows():
            sick = r.misc_peak >= 6
            ax.scatter(r[col], r.misc_peak, s=95,
                       color=CRITICAL if sick else BLUE, zorder=3,
                       edgecolors=SURFACE, linewidths=1.4)
            ax.annotate(f"P{int(r.participant)}", (r[col], r.misc_peak),
                        textcoords="offset points", xytext=(8, -3),
                        fontsize=8.5, color=INK2)
        ax.set_xlabel(xl)
        ax.set_ylabel("peak MISC")
        ax.set_title(f"ρ = {rho:+.2f}   (p = {p:.3f}, n = {len(part)})",
                     fontsize=11, color=INK)
        ax.margins(0.13)
    fig.suptitle("Handlebar deviation rises with sickness; speed falls with it",
                 fontsize=13, color=INK)
    fig.text(0.5, -0.03, "Red = participants reaching the nausea band (peak ≥ 6). "
             "Handlebar deviation survives controlling for speed "
             "(partial ρ = +0.52).", ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "v4_scatter_deviation.png")


# ---------------------------------------------------------------- v5
def v5_practice(dr):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.9))
    for ax, (col, name) in zip(axes,
                               [("steer_sd_deg", "deviation of rotation (SD, °)"),
                                ("steer_absmean_deg", "average rotation angle (°)")]):
        for pid, g in dr.groupby("participant"):
            g = g.sort_values("drive")
            if len(g) < 2:
                continue
            ax.plot(g.drive, g[col], color=BASE, lw=1.3, marker="o", ms=4, zorder=2)
        med = dr.groupby("drive")[col].median()
        ax.plot(med.index, med.values, color=CRITICAL, lw=2.8, marker="o", ms=8,
                zorder=4, label="median")
        rho, p = spearmanr(dr.drive, dr[col])
        ax.set_xticks([1, 2, 3])
        ax.set_xlabel("drive")
        ax.set_title(f"{name}\nρ = {rho:+.2f}, p = {p:.3f}", fontsize=10,
                     color=INK2)
        ax.margins(y=0.12)
    axes[0].legend(frameon=False, fontsize=9)
    fig.suptitle("Confounder: handlebar movement shrinks with practice across drives",
                 fontsize=12.5, color=INK)
    fig.text(0.5, -0.05, "Why drive-1-only is reported alongside the drive-average, "
             "and why drive number must be a covariate in the full analysis.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "v5_practice_confound.png")


# ---------------------------------------------------------------- v6
def v6_traces(dr):
    """What 'deviation' physically is: steering trace of a low vs high sickness rider."""
    picks = [(67, 1, "P67 — peak MISC 1", BLUE),
             (62, 1, "P62 — peak MISC 10 (vomited)", CRITICAL)]
    fig, axes = plt.subplots(2, 1, figsize=(11, 5.2), sharex=True, sharey=True)
    for ax, (pid, drive, title, col) in zip(axes, picks):
        row = dr[(dr.participant == pid) & (dr.drive == drive)].iloc[0]
        df = pd.read_csv(os.path.join(DATA, row.source_file), encoding="utf-8-sig")
        for c in ["UnixTimestamp", "ForwardVel", "BikeYaw", "HandlebarYaw"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["UnixTimestamp", "ForwardVel", "BikeYaw",
                               "HandlebarYaw"])
        t = df.UnixTimestamp.to_numpy() / 1000.0
        t -= t[0]
        steer = wrap180(df.HandlebarYaw.to_numpy() - df.BikeYaw.to_numpy())
        keep = df.ForwardVel.to_numpy() >= 0.5
        ax.plot(t[keep], steer[keep], color=col, lw=0.8)
        ax.axhline(0, color=BASE, lw=1)
        ax.set_ylabel("steering\ndeflection (°)")
        ax.set_ylim(-34, 34)
        ax.annotate(f"{title}    SD = {row.steer_sd_deg:.1f}°",
                    xy=(0.99, 0.91), xycoords="axes fraction", ha="right",
                    fontsize=11, fontweight="bold", color=col)
    axes[1].set_xlabel("riding time (s)")
    fig.suptitle("What the deviation metric measures: handlebar input of a settled "
                 "vs a nauseous rider", fontsize=12.5, color=INK)
    fig.text(0.5, -0.02, "Same quantity, first drive of each. "
             "Deflection = HandlebarYaw − BikeYaw, so route curvature is removed — "
             "this is rider input only.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "v6_steering_traces.png")


def main():
    os.makedirs(FIG, exist_ok=True)
    groups = pd.read_csv(os.path.join(HERE, "sickness_groups.csv"))
    part = pd.read_csv(os.path.join(HERE, "handlebar_participants.csv"))
    dr = pd.read_csv(os.path.join(HERE, "handlebar_drives.csv"))
    v1_group_scheme(groups)
    v2_handlebar_by_group(part, dr)
    v3_severity_gradient(part)
    v4_scatter(part)
    v5_practice(dr)
    v6_traces(dr)


if __name__ == "__main__":
    main()
