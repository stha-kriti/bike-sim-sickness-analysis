"""Iteration 3 figures — full dataset (48 participants, 131-133 drives).

Replaces figures_v2/ (built from 9 participants, now stale).
Each figure carries one claim from METHODS_LOG I3.4-I3.9.

  w1_cohort_problem.png     why the two cohorts cannot be pooled
  w2_nonreplication.png     the pilot effect reversed at full N
  w3_early_vs_late.png      THE KEY RESULT: signal is late in the drive, not early
  w4_withindrive_change.png within-drive change vs rating (the surviving finding)
  w5_normalisation.png      what survives matched exposure — mostly nothing
  w6_traces_earlylate.png   physical illustration on one drive
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import hb_core as hb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(HERE, "figures_v3")

BLUE = "#2a78d6"
ORANGE = "#eb6834"
GREEN = "#1baf7a"
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

LABELS = dict(hb.METRIC_LABELS)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print("wrote", name)


# --------------------------------------------------------------- w1
def w1_cohort(part, dr):
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.9))
    rng = np.random.default_rng(4)
    # a) drive duration
    ax = axes[0]
    for k, (coh, col, lab) in enumerate([("feb_mar", BLUE, "Feb–Mar"),
                                         ("june", ORANGE, "June")]):
        v = dr[dr.cohort == coh].riding_time_s
        x = k + 1 + rng.uniform(-0.12, 0.12, len(v))
        ax.scatter(x, v, s=20, color=col, alpha=0.65, edgecolors=SURFACE,
                   linewidths=0.5)
        ax.plot([k + 0.72, k + 1.28], [v.median()] * 2, color=INK, lw=2.4, zorder=5)
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Feb–Mar\n(n=108)", "June\n(n=25)"], fontsize=9)
    ax.set_ylabel("riding time per drive (s)")
    ax.set_title("Drives are 2.4× longer in Feb–Mar", fontsize=10)
    # b) sickness
    ax = axes[1]
    for k, (coh, col) in enumerate([("feb_mar", BLUE), ("june", ORANGE)]):
        v = part[part.cohort == coh].misc_peak
        x = k + 1 + rng.uniform(-0.12, 0.12, len(v))
        ax.scatter(x, v, s=42, color=col, alpha=0.85, edgecolors=SURFACE,
                   linewidths=1)
        ax.plot([k + 0.72, k + 1.28], [v.median()] * 2, color=INK, lw=2.4, zorder=5)
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Feb–Mar\n(n=39)", "June\n(n=9)"], fontsize=9)
    ax.set_ylabel("peak MISC")
    ax.set_title("…and June participants were far sicker", fontsize=10)
    # c) duration vs metric
    ax = axes[2]
    sub = dr[["riding_time_s", "steer_sd_deg", "cohort"]].dropna()
    for coh, col in [("feb_mar", BLUE), ("june", ORANGE)]:
        s = sub[sub.cohort == coh]
        ax.scatter(s.riding_time_s, s.steer_sd_deg, s=20, color=col, alpha=0.7,
                   edgecolors=SURFACE, linewidths=0.5,
                   label="Feb–Mar" if coh == "feb_mar" else "June")
    rho, p = spearmanr(sub.riding_time_s, sub.steer_sd_deg)
    ax.set_xlabel("riding time (s)")
    ax.set_ylabel("steering deviation (SD, °)")
    ax.set_title(f"Longer drives ⇒ less deviation\nρ = {rho:+.2f} (p = {p:.3f})",
                 fontsize=10)
    ax.legend(frameon=False, fontsize=8.5)
    fig.suptitle("Why the two cohorts cannot simply be pooled", fontsize=13,
                 color=INK)
    fig.text(0.5, -0.06, "Cohort is related to both the predictor (handlebar) and "
             "the outcome (sickness) — and drive duration links them. "
             "Feb–Mar (n=39) is therefore the primary sample.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "w1_cohort_problem.png")


# --------------------------------------------------------------- w2
def w2_nonreplication():
    pilot = {"steer_sd_deg": 0.62, "steer_absmean_deg": 0.50,
             "steer_iqr_deg": 0.50, "steer_p95_abs_deg": 0.38,
             "steerrate_absmean_dps": 0.62, "steerrate_sd_dps": 0.62,
             "steer_reversals_per_min": 0.62, "steer_jerk_rms_dps2": 0.38}
    full = {"steer_sd_deg": -0.05, "steer_absmean_deg": -0.11,
            "steer_iqr_deg": -0.07, "steer_p95_abs_deg": -0.07,
            "steerrate_absmean_dps": -0.35, "steerrate_sd_dps": -0.24,
            "steer_reversals_per_min": -0.23, "steer_jerk_rms_dps2": -0.40}
    keys = [k for k, _ in hb.METRIC_LABELS]
    y = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(10, 4.3))
    ax.barh(y - 0.2, [pilot[k] for k in keys], height=0.38, color=ORANGE,
            label="pilot — June only (n = 4 v 4)")
    ax.barh(y + 0.2, [full[k] for k in keys], height=0.38, color=BLUE,
            label="full — Feb–Mar (n = 22 v 14)")
    ax.axvline(0, color=INK, lw=1.2)
    ax.set_yticks(y)
    ax.set_yticklabels([LABELS[k] for k in keys], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("effect size (rank-biserial): escalating vs non-escalating")
    ax.set_xlim(-0.7, 0.8)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.grid(axis="y", visible=False)
    fig.suptitle("The pilot effect did not replicate — it reversed sign",
                 fontsize=13, color=INK)
    fig.text(0.5, -0.05, "Every metric moved from clearly positive to null or "
             "negative once the full sample arrived. A 4-vs-4 comparison cannot "
             "support a claim of this kind.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "w2_nonreplication.png")


# --------------------------------------------------------------- w3
def w3_early_late(el):
    fm = el[el.cohort == "feb_mar"]
    keys = [k for k, _ in hb.METRIC_LABELS]
    wins = [("early80_", "first 80 s"), ("mid80_", "middle 80 s"),
            ("late80_", "last 80 s")]
    vals = np.zeros((len(keys), 3))
    sig = np.zeros((len(keys), 3), dtype=bool)
    for i, k in enumerate(keys):
        for j, (pref, _) in enumerate(wins):
            sub = fm[[pref + k, "misc"]].dropna()
            r, p = spearmanr(sub[pref + k], sub["misc"])
            vals[i, j] = r
            sig[i, j] = p < 0.05
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    vmax = 0.32
    im = ax.imshow(vals, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(3))
    ax.set_xticklabels([w[1] for w in wins], fontsize=10)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([LABELS[k] for k in keys], fontsize=9)
    ax.grid(visible=False)
    for i in range(len(keys)):
        for j in range(3):
            txt = f"{vals[i, j]:+.2f}" + ("*" if sig[i, j] else "")
            ax.text(j, i, txt, ha="center", va="center", fontsize=9.5,
                    color=INK if abs(vals[i, j]) < 0.2 else "white",
                    fontweight="bold" if sig[i, j] else "normal")
    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.03)
    cb.set_label("Spearman ρ with that drive's MISC", color=INK2)
    cb.ax.tick_params(colors=MUTED)
    fig.suptitle("The handlebar signal is late in the drive, not early",
                 fontsize=13, color=INK)
    fig.text(0.5, -0.04,
             "Feb–Mar cohort, 108 drives. All three windows are 80 s long and "
             "drive durations are already matched, so exposure is constant —\n"
             "the contrast is position in the drive. Early: nothing. "
             "Mid/late: ρ ≈ +0.2 to +0.3.  * p < 0.05, uncorrected.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "w3_early_vs_late.png")


# --------------------------------------------------------------- w4
def w4_withindrive(el):
    metrics = [("steer_iqr_deg", "steering IQR"),
               ("steer_absmean_deg", "average angle"),
               ("steer_sd_deg", "deviation (SD)"),
               ("steer_p95_abs_deg", "large corrections")]
    fig, axes = plt.subplots(1, 4, figsize=(12.4, 3.6), sharey=True)
    for ax, (col, name) in zip(axes, metrics):
        sub = el[[f"delta_{col}", "misc", "cohort"]].dropna()
        for coh, c in [("feb_mar", BLUE), ("june", ORANGE)]:
            s = sub[sub.cohort == coh]
            ax.scatter(s[f"delta_{col}"], s["misc"], s=24, color=c, alpha=0.75,
                       edgecolors=SURFACE, linewidths=0.6,
                       label="Feb–Mar" if coh == "feb_mar" else "June")
        rho, p = spearmanr(sub[f"delta_{col}"], sub["misc"])
        ax.axvline(0, color=BASE, lw=1.2)
        ax.set_xlabel(f"change in {name}\n(last 80 s − first 80 s)", fontsize=9)
        ax.set_title(f"ρ = {rho:+.2f}   p = {p:.3f}", fontsize=10, color=INK2)
    axes[0].set_ylabel("MISC after that drive")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.suptitle("The surviving finding: steering amplitude grows more within a "
                 "drive when the rider ends up sicker", fontsize=12.5, color=INK)
    fig.text(0.5, -0.08, "131 drives. Both windows are 80 s, so exposure is "
             "identical by construction. The four amplitude metrics agree "
             "(ρ = +0.19 to +0.22), but after FDR correction across eight metrics "
             "p_BH = 0.057 —\nconsistent and coherent, yet short of conventional "
             "significance. Reported as suggestive.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "w4_withindrive_change.png")


# --------------------------------------------------------------- w5
def w5_normalisation(nc):
    d = nc[(nc.test == "vs_misc_peak")].copy()
    keys = [k for k, _ in hb.METRIC_LABELS] + ["speed_mean_ms"]
    lab = dict(LABELS)
    lab["speed_mean_ms"] = "mean speed"
    wins = ["full", "t80", "t120", "d500"]
    fig, ax = plt.subplots(figsize=(10.4, 4.4))
    y = np.arange(len(keys))
    colors = [BASE, BLUE, GREEN, ORANGE]
    for j, (w, c) in enumerate(zip(wins, colors)):
        vals = []
        for k in keys:
            r = d[(d.window == w) & (d.metric == k)]
            vals.append(r.febmar_rho.iloc[0] if len(r) else np.nan)
        off = (j - 1.5) * 0.2
        ax.barh(y + off, vals, height=0.19, color=c,
                label={"full": "whole drive", "t80": "first 80 s",
                       "t120": "first 120 s", "d500": "first 500 m"}[w])
    ax.axvline(0, color=INK, lw=1.2)
    ax.set_yticks(y)
    ax.set_yticklabels([lab[k] for k in keys], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Spearman ρ with peak MISC — Feb–Mar cohort (n = 39)")
    ax.legend(frameon=False, fontsize=8.5, ncol=2)
    ax.grid(axis="y", visible=False)
    fig.suptitle("Matching exposure removes almost every correlation",
                 fontsize=13, color=INK)
    fig.text(0.5, -0.05, "The whole-drive values (grey) are the ones reported "
             "earlier. Restricting every drive to a matched opening window "
             "collapses them — including mean speed.\nThis is what motivated the "
             "early-vs-late test, which located the signal later in the drive.",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "w5_normalisation.png")


# --------------------------------------------------------------- w6
def w6_traces(el):
    """One high-MISC drive: steering early vs late, same 80 s windows."""
    fm = el[(el.cohort == "feb_mar") & el.misc.notna()]
    pick = fm.sort_values("delta_steer_iqr_deg", ascending=False).iloc[0]
    folder = None
    for name in os.listdir(os.path.join(ROOT, "new data")):
        p = os.path.join(ROOT, "new data", name)
        if os.path.isdir(p) and pick.source_file in os.listdir(p):
            folder = p
            break
    if folder is None:
        print("skip w6: source folder not found")
        return
    clean = hb.load_clean(os.path.join(folder, pick.source_file))
    t = clean["t_s"].to_numpy()
    early = clean[t <= t[0] + 80]
    late = clean[t >= t[-1] - 80]

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.7), sharey=True)
    for ax, (sub, name, col) in zip(axes,
                                    [(early, "first 80 s", BLUE),
                                     (late, "last 80 s", CRITICAL)]):
        tt = sub["t_s"].to_numpy() - sub["t_s"].iloc[0]
        ax.plot(tt, sub["steer_deg"].to_numpy(), color=col, lw=0.8)
        ax.axhline(0, color=BASE, lw=1)
        iqr = np.percentile(sub["steer_deg"], 75) - np.percentile(sub["steer_deg"], 25)
        ax.set_title(f"{name}   IQR = {iqr:.2f}°", fontsize=11, color=col,
                     fontweight="bold")
        ax.set_xlabel("time within window (s)")
    axes[0].set_ylabel("steering deflection (°)")
    fig.suptitle(f"Illustration — P{int(pick.participant)} drive "
                 f"{int(pick.drive)}, rated MISC {int(pick.misc)} afterwards",
                 fontsize=12.5, color=INK)
    fig.text(0.5, -0.09, "Same drive, same window length; steering amplitude is "
             "visibly larger by the end. This is the per-drive quantity whose "
             "change across 131 drives tracks the post-drive rating.\n"
             "Chosen as the LARGEST within-drive change in the sample — an "
             "illustration of the measure, not a typical case. The pooled effect "
             "is modest (ρ ≈ +0.2).",
             ha="center", fontsize=9.5, color=INK2)
    fig.tight_layout()
    save(fig, "w6_traces_earlylate.png")


def main():
    os.makedirs(FIG, exist_ok=True)
    part = pd.read_csv(os.path.join(HERE, "handlebar_participants_all.csv"))
    dr = pd.read_csv(os.path.join(HERE, "handlebar_drives_all.csv"))
    el = pd.read_csv(os.path.join(HERE, "early_late_drives.csv"))
    nc = pd.read_csv(os.path.join(HERE, "normalisation_check.csv"))
    w1_cohort(part, dr)
    w2_nonreplication()
    w3_early_late(el)
    w4_withindrive(el)
    w5_normalisation(nc)
    w6_traces(el)


if __name__ == "__main__":
    main()
