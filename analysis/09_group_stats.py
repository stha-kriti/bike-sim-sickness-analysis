"""Iteration 2, step 4: group comparison — handlebar behaviour vs sickness group.

Implements the supervisor's analysis plan:
  * classify participants into sickness groups (done in 06)
  * quantify handlebar movement (done in 08)
  * test whether handlebar deviation differs BETWEEN groups, and whether it
    correlates with sickness

Because the telemetry currently covers only 9 participants, effect sizes are
reported alongside p-values and treated as the primary output: with 4-vs-4 groups
a Mann-Whitney test cannot reach significance at any effect size, so p-values here
are diagnostics of the pipeline, not evidence. Rerunning this script unchanged on
the full telemetry archive is what produces the real result.

Two aggregations are reported because the practice effect is strong:
  mean   - metric averaged over a participant's drives
  drive1 - first drive only (uncontaminated by practice/habituation)

Output: group_stats.csv + console report
"""
import os

import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu, spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))

METRICS = [
    ("steer_sd_deg", "deviation of handlebar rotation (SD)"),
    ("steer_absmean_deg", "average handlebar angle (mean |defl|)"),
    ("steer_p95_abs_deg", "large corrections (95th pct |defl|)"),
    ("steer_iqr_deg", "typical spread (IQR)"),
    ("steerrate_absmean_dps", "handlebar changing speed (mean |rate|)"),
    ("steerrate_sd_dps", "handlebar rate variability (SD)"),
    ("steer_reversals_per_min", "correction frequency (reversals/min)"),
    ("steer_jerk_rms_dps2", "jerkiness (RMS jerk)"),
]

rows = []


def add(analysis, metric, agg, stat, value, p=None, n="", note=""):
    rows.append(dict(analysis=analysis, metric=metric, aggregation=agg,
                     statistic=stat,
                     value=None if value is None or (isinstance(value, float) and np.isnan(value))
                     else round(float(value), 3),
                     p=round(float(p), 4) if p is not None and not np.isnan(p) else "",
                     n=n, note=note))


def rank_biserial(a, b):
    """Effect size for Mann-Whitney: -1..+1, 0 = no difference."""
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0 or len(b) == 0:
        return np.nan
    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    return (gt - lt) / (len(a) * len(b))


def main():
    part = pd.read_csv(os.path.join(HERE, "handlebar_participants.csv"))
    dr = pd.read_csv(os.path.join(HERE, "handlebar_drives.csv"))
    d1 = dr[dr.drive == 1].set_index("participant")

    print("=" * 78)
    print("Participants available:", len(part), "| telemetry covers only the June cohort")
    print("=" * 78)

    # group membership overview
    for scheme in ["traj_group", "traj2", "severity3"]:
        counts = part[scheme].value_counts().to_dict()
        print(f"  {scheme:12s} {counts}")
    print()

    for agg_name in ["mean", "drive1"]:
        src = part.set_index("participant") if agg_name == "mean" else d1
        # group labels always come from the participant table
        labels = part.set_index("participant")
        common = [p for p in src.index if p in labels.index]

        print("=" * 78)
        print(f"A) BETWEEN-GROUP DIFFERENCE — escalating vs non_escalating  [{agg_name}]")
        print("=" * 78)
        for col, desc in METRICS:
            if col not in src.columns:
                continue
            esc = [src.loc[p, col] for p in common
                   if labels.loc[p, "traj2"] == "escalating"]
            non = [src.loc[p, col] for p in common
                   if labels.loc[p, "traj2"] == "non_escalating"]
            esc = [v for v in esc if not pd.isna(v)]
            non = [v for v in non if not pd.isna(v)]
            if len(esc) < 2 or len(non) < 2:
                continue
            u, p = mannwhitneyu(esc, non, alternative="two-sided")
            rb = rank_biserial(esc, non)
            add("A_traj2", col, agg_name, "mannwhitney_U", u, p,
                f"{len(esc)}v{len(non)}", f"rank_biserial={rb:.2f}")
            add("A_traj2", col, agg_name, "rank_biserial", rb, None,
                f"{len(esc)}v{len(non)}",
                f"escalating median={np.median(esc):.2f} non={np.median(non):.2f}")
            print(f"  {desc:42s} esc={np.median(esc):6.2f} non={np.median(non):6.2f}"
                  f"  rb={rb:+.2f}  p={p:.3f}")

        print("-" * 78)
        print(f"B) BETWEEN-GROUP DIFFERENCE — severity3 (none/mild/nausea)  [{agg_name}]")
        print("-" * 78)
        for col, desc in METRICS:
            if col not in src.columns:
                continue
            gs = []
            for g in ["none", "mild", "nausea"]:
                vals = [src.loc[p, col] for p in common
                        if labels.loc[p, "severity3"] == g]
                vals = [v for v in vals if not pd.isna(v)]
                gs.append(vals)
            if sum(len(g) >= 2 for g in gs) < 2:
                continue
            usable = [g for g in gs if len(g) >= 1]
            try:
                h, p = kruskal(*[g for g in usable if len(g) >= 1])
            except ValueError:
                continue
            add("B_severity3", col, agg_name, "kruskal_H", h, p,
                "/".join(str(len(g)) for g in gs))
            meds = "  ".join(f"{g}={np.median(v):.2f}" if v else f"{g}=--"
                             for g, v in zip(["none", "mild", "nausea"], gs))
            print(f"  {desc:42s} {meds}  H={h:.2f} p={p:.3f}")

        print("-" * 78)
        print(f"C) CORRELATION with sickness severity and change  [{agg_name}]")
        print("-" * 78)
        for target in ["misc_peak", "misc_mean", "misc_delta"]:
            print(f"  vs {target}:")
            for col, desc in METRICS:
                if col not in src.columns:
                    continue
                x, y = [], []
                for p_ in common:
                    a, b = src.loc[p_, col], labels.loc[p_, target]
                    if not (pd.isna(a) or pd.isna(b)):
                        x.append(a)
                        y.append(b)
                if len(x) < 4:
                    continue
                rho, pv = spearmanr(x, y)
                add(f"C_corr_{target}", col, agg_name, "spearman_rho", rho, pv, len(x))
                print(f"     {desc:40s} rho={rho:+.2f}  p={pv:.3f}  (n={len(x)})")
        print()

    # ---- within-participant: does handlebar deviation track MISC drive to drive? ----
    print("=" * 78)
    print("D) WITHIN-PARTICIPANT — change in handlebar metric vs change in MISC")
    print("=" * 78)
    deltas = []
    for pid, g in dr.groupby("participant"):
        g = g.sort_values("drive")
        if len(g) < 2:
            continue
        deltas.append(g[[c for c, _ in METRICS] + ["misc"]].diff().dropna())
    if deltas:
        dd = pd.concat(deltas)
        for col, desc in METRICS:
            rho, pv = spearmanr(dd[col], dd["misc"])
            add("D_within_deltas", col, "consecutive_drives", "spearman_rho",
                rho, pv, len(dd))
            print(f"  d({desc:40s}) vs dMISC  rho={rho:+.2f}  p={pv:.3f}")
        print(f"  (n={len(dd)} consecutive-drive transitions)")

    # ---- practice effect check (confounder) ----
    print("\n" + "=" * 78)
    print("E) CONFOUNDER CHECK — does handlebar deviation fall with practice?")
    print("=" * 78)
    for col, desc in METRICS[:4]:
        med = dr.groupby("drive")[col].median()
        rho, pv = spearmanr(dr["drive"], dr[col])
        add("E_practice", col, "per_drive", "spearman_rho_vs_drive", rho, pv, len(dr))
        print(f"  {desc:42s} d1={med.get(1, np.nan):6.2f} d2={med.get(2, np.nan):6.2f}"
              f" d3={med.get(3, np.nan):6.2f}  rho={rho:+.2f} p={pv:.3f}")

    pd.DataFrame(rows).to_csv(os.path.join(HERE, "group_stats.csv"), index=False)
    print(f"\nwrote group_stats.csv ({len(rows)} rows)")
    print("\nPOWER NOTE: with 4-vs-4 groups the smallest achievable Mann-Whitney "
          "p is 0.029;\nnothing here can be significant after correction. Effect "
          "sizes and medians are\nthe usable output until the full archive is linked.")


if __name__ == "__main__":
    main()
