"""Iteration 3: group statistics at full N (48 participants, 133 drives).

Same tests as 09_group_stats.py so the pilot and full run are comparable, plus
what only becomes possible/necessary at this sample size:

  * Benjamini-Hochberg FDR correction across the primary metric family
  * a COHORT check (Feb-Mar vs June): the two archives differ in SimBike schema
    (19 vs 22 columns => HMI features added later), so a batch effect is a real
    threat to pooling them
  * speed-adjusted (partial) correlations as standard, not an afterthought
  * practice effect controlled by using drive-1-only as a parallel aggregation

Output: group_stats_all.csv
"""
import os

import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu, rankdata, spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))

PRIMARY = [
    ("steer_sd_deg", "deviation of rotation (SD)"),
    ("steer_absmean_deg", "average rotation angle"),
    ("steerrate_absmean_dps", "changing speed (mean |rate|)"),
    ("steer_reversals_per_min", "correction frequency"),
]
SECONDARY = [
    ("steer_p95_abs_deg", "large corrections (p95)"),
    ("steer_iqr_deg", "typical spread (IQR)"),
    ("steerrate_sd_dps", "rate variability (SD)"),
    ("steer_jerk_rms_dps2", "jerkiness (RMS)"),
]
ALL_METRICS = PRIMARY + SECONDARY

rows = []


def add(**kw):
    rows.append(kw)


def bh(pvals):
    """Benjamini-Hochberg adjusted p-values."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    adj = np.empty(n)
    prev = 1.0
    for rank, i in enumerate(reversed(order), start=1):
        val = p[i] * n / (n - rank + 1)
        prev = min(prev, val)
        adj[i] = min(1.0, prev)
    return adj


def rank_biserial(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    return (gt - lt) / (len(a) * len(b))


def partial_spearman(x, y, z):
    x, y, z = rankdata(x), rankdata(y), rankdata(z)
    rxy = np.corrcoef(x, y)[0, 1]
    rxz = np.corrcoef(x, z)[0, 1]
    ryz = np.corrcoef(y, z)[0, 1]
    return (rxy - rxz * ryz) / np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))


def main():
    part = pd.read_csv(os.path.join(HERE, "handlebar_participants_all.csv"))
    dr = pd.read_csv(os.path.join(HERE, "handlebar_drives_all.csv"))
    d1 = dr[dr.drive == 1].set_index("participant")

    print("=" * 78)
    print(f"FULL DATASET — {len(part)} participants, {len(dr)} drives")
    print("=" * 78)
    print("cohorts  :", part.cohort.value_counts().to_dict())
    print("traj2    :", part.traj2.value_counts().to_dict())
    print("severity3:", part.severity3.value_counts().to_dict())

    # ---------------------------------------------------------------- G) cohort
    print("\n" + "=" * 78)
    print("G) COHORT / BATCH CHECK — can the two archives be pooled?")
    print("=" * 78)
    fm = part[part.cohort == "feb_mar"]
    jn = part[part.cohort == "june"]
    for col, desc in ALL_METRICS:
        a, b = fm[col].dropna(), jn[col].dropna()
        u, p = mannwhitneyu(a, b, alternative="two-sided")
        rb = rank_biserial(a, b)
        add(analysis="G_cohort", metric=col, aggregation="mean",
            statistic="mannwhitney_p", value=round(p, 4),
            extra=f"rb={rb:+.2f}", n=f"{len(a)}v{len(b)}",
            note=f"feb_mar median={a.median():.2f} june={b.median():.2f}")
        flag = "  <-- DIFFERS" if p < 0.05 else ""
        print(f"  {desc:34s} feb-mar={a.median():7.2f} june={b.median():7.2f}"
              f"  rb={rb:+.2f} p={p:.3f}{flag}")
    # is sickness itself different between cohorts?
    for tgt in ["misc_peak", "misc_delta"]:
        a, b = fm[tgt].dropna(), jn[tgt].dropna()
        u, p = mannwhitneyu(a, b, alternative="two-sided")
        print(f"  {tgt:34s} feb-mar={a.median():7.2f} june={b.median():7.2f}"
              f"        p={p:.3f}")
        add(analysis="G_cohort", metric=tgt, aggregation="mean",
            statistic="mannwhitney_p", value=round(p, 4), n=f"{len(a)}v{len(b)}")

    # ------------------------------------------------- A/B/C/D per aggregation
    for agg_name in ["mean", "drive1"]:
        src = part.set_index("participant") if agg_name == "mean" else d1
        lab = part.set_index("participant")
        common = [p for p in src.index if p in lab.index]

        print("\n" + "=" * 78)
        print(f"A) escalating vs non_escalating   [{agg_name}]")
        print("=" * 78)
        praw, keys = [], []
        for col, desc in ALL_METRICS:
            esc = [src.loc[p, col] for p in common
                   if lab.loc[p, "traj2"] == "escalating"]
            non = [src.loc[p, col] for p in common
                   if lab.loc[p, "traj2"] == "non_escalating"]
            esc = [v for v in esc if pd.notna(v)]
            non = [v for v in non if pd.notna(v)]
            u, p = mannwhitneyu(esc, non, alternative="two-sided")
            rb = rank_biserial(esc, non)
            praw.append(p)
            keys.append((col, desc, np.median(esc), np.median(non), rb, len(esc),
                         len(non)))
        adj = bh(praw)
        for (col, desc, me, mn, rb, ne, nn), p, pa in zip(keys, praw, adj):
            star = "*" if pa < 0.05 else ""
            print(f"  {desc:34s} esc={me:7.2f} non={mn:7.2f}  rb={rb:+.2f}"
                  f"  p={p:.3f}  p_BH={pa:.3f}{star}")
            add(analysis="A_traj2", metric=col, aggregation=agg_name,
                statistic="mannwhitney_p", value=round(p, 4),
                p_bh=round(pa, 4), extra=f"rb={rb:+.2f}", n=f"{ne}v{nn}",
                note=f"esc median={me:.2f} non={mn:.2f}")

        print("-" * 78)
        print(f"B) severity3  none / mild / nausea   [{agg_name}]")
        print("-" * 78)
        praw, keys = [], []
        for col, desc in ALL_METRICS:
            gs = []
            for g in ["none", "mild", "nausea"]:
                v = [src.loc[p, col] for p in common
                     if lab.loc[p, "severity3"] == g]
                gs.append([x for x in v if pd.notna(x)])
            h, p = kruskal(*gs)
            praw.append(p)
            keys.append((col, desc, [np.median(g) if g else np.nan for g in gs], h,
                         [len(g) for g in gs]))
        adj = bh(praw)
        for (col, desc, meds, h, ns), p, pa in zip(keys, praw, adj):
            star = "*" if pa < 0.05 else ""
            mono = "monotonic" if meds[0] <= meds[1] <= meds[2] else ""
            print(f"  {desc:34s} {meds[0]:6.2f} {meds[1]:6.2f} {meds[2]:6.2f}"
                  f"  H={h:5.2f} p={p:.3f} p_BH={pa:.3f}{star} {mono}")
            add(analysis="B_severity3", metric=col, aggregation=agg_name,
                statistic="kruskal_p", value=round(p, 4), p_bh=round(pa, 4),
                n="/".join(map(str, ns)),
                note=f"medians none={meds[0]:.2f} mild={meds[1]:.2f} "
                     f"nausea={meds[2]:.2f}")

        print("-" * 78)
        print(f"C) trajectory 3-class (supervisor's scheme)   [{agg_name}]")
        print("-" * 78)
        for col, desc in PRIMARY:
            gs = []
            for g in ["improving", "stable", "worsening"]:
                v = [src.loc[p, col] for p in common
                     if lab.loc[p, "traj_group"] == g]
                gs.append([x for x in v if pd.notna(x)])
            h, p = kruskal(*gs)
            meds = [np.median(g) if g else np.nan for g in gs]
            print(f"  {desc:34s} impr={meds[0]:6.2f}(n={len(gs[0])}) "
                  f"stab={meds[1]:6.2f} wors={meds[2]:6.2f}  H={h:5.2f} p={p:.3f}")
            add(analysis="C_traj3", metric=col, aggregation=agg_name,
                statistic="kruskal_p", value=round(p, 4),
                n="/".join(str(len(g)) for g in gs),
                note="improving arm under-powered (n=3)")

        print("-" * 78)
        print(f"D) correlations (raw and speed-adjusted)   [{agg_name}]")
        print("-" * 78)
        for target in ["misc_peak", "misc_mean", "misc_delta"]:
            print(f"  vs {target}:")
            praw, keys = [], []
            for col, desc in ALL_METRICS:
                x, y, z = [], [], []
                for p_ in common:
                    a = src.loc[p_, col]
                    b = lab.loc[p_, target]
                    c = src.loc[p_, "speed_mean_ms"]
                    if pd.notna(a) and pd.notna(b) and pd.notna(c):
                        x.append(a)
                        y.append(b)
                        z.append(c)
                rho, pv = spearmanr(x, y)
                pr = partial_spearman(x, y, z)
                praw.append(pv)
                keys.append((col, desc, rho, pr, len(x)))
            adj = bh(praw)
            for (col, desc, rho, pr, n), pv, pa in zip(keys, praw, adj):
                star = "*" if pa < 0.05 else ""
                print(f"     {desc:32s} rho={rho:+.2f} p={pv:.3f} "
                      f"p_BH={pa:.3f}{star}  partial(speed)={pr:+.2f}  n={n}")
                add(analysis=f"D_corr_{target}", metric=col, aggregation=agg_name,
                    statistic="spearman_rho", value=round(rho, 3),
                    p=round(pv, 4), p_bh=round(pa, 4),
                    extra=f"partial_speed={pr:+.3f}", n=n)

        # speed itself
        for target in ["misc_peak", "misc_delta"]:
            x = [src.loc[p, "speed_mean_ms"] for p in common]
            y = [lab.loc[p, target] for p in common]
            ok = [(a, b) for a, b in zip(x, y) if pd.notna(a) and pd.notna(b)]
            rho, pv = spearmanr([a for a, _ in ok], [b for _, b in ok])
            print(f"  speed_mean_ms vs {target:12s} rho={rho:+.2f} p={pv:.3f} "
                  f"(n={len(ok)})   <- secondary finding")
            add(analysis=f"D_corr_{target}", metric="speed_mean_ms",
                aggregation=agg_name, statistic="spearman_rho",
                value=round(rho, 3), p=round(pv, 4), n=len(ok))

    # ------------------------------------------------------ E) within-participant
    print("\n" + "=" * 78)
    print("E) WITHIN-PARTICIPANT — change in metric vs change in MISC")
    print("=" * 78)
    deltas = []
    for pid, g in dr.groupby("participant"):
        g = g.sort_values("drive")
        if len(g) < 2:
            continue
        deltas.append(g[[c for c, _ in ALL_METRICS] + ["misc"]].diff().dropna())
    dd = pd.concat(deltas)
    for col, desc in ALL_METRICS:
        sub = dd[[col, "misc"]].dropna()
        rho, pv = spearmanr(sub[col], sub["misc"])
        print(f"  d({desc:32s}) vs dMISC  rho={rho:+.2f}  p={pv:.3f}  n={len(sub)}")
        add(analysis="E_within_deltas", metric=col, aggregation="consecutive",
            statistic="spearman_rho", value=round(rho, 3), p=round(pv, 4),
            n=len(sub))

    # ------------------------------------------------------------- F) practice
    print("\n" + "=" * 78)
    print("F) PRACTICE EFFECT across drives")
    print("=" * 78)
    for col, desc in PRIMARY:
        med = dr.groupby("drive")[col].median()
        sub = dr[[col, "drive"]].dropna()
        rho, pv = spearmanr(sub["drive"], sub[col])
        print(f"  {desc:34s} d1={med.get(1, np.nan):7.2f} d2={med.get(2, np.nan):7.2f}"
              f" d3={med.get(3, np.nan):7.2f}  rho={rho:+.2f} p={pv:.4f}")
        add(analysis="F_practice", metric=col, aggregation="per_drive",
            statistic="spearman_rho_vs_drive", value=round(rho, 3),
            p=round(pv, 4), n=len(sub))

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(HERE, "group_stats_all.csv"), index=False)
    print(f"\nwrote group_stats_all.csv ({len(out)} rows)")
    print("* = survives Benjamini-Hochberg FDR correction within its metric family")


if __name__ == "__main__":
    main()
