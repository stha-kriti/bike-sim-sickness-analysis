"""Phase 5: Statistics.

A) Pooled Spearman feature vs MISC (n=22 drives; drives within participant are
   not independent -> descriptive, exact p reported but exploratory).
B) Within-participant change: consecutive-drive deltas (d1->d2, d2->d3) for the
   7 participants with 3 drives; Spearman of delta-feature vs delta-MISC (n=14).
   Removes stable between-person differences (METHODS_LOG Finding 3.1).
C) Within-drive degradation (RQ3): per drive, feature(third 3) - feature(third 1);
   Spearman of that change vs MISC (n=22), plus Wilcoxon third1 vs third3 overall
   (habituation/fatigue direction regardless of sickness).
D) Dropout case (RQ4): P66's single drive vs the other 7 first drives (z-scores).

Output: stats_summary.csv (long format) + console report.
"""
import os

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURES = [
    "steer_reversals_per_min", "steer_std_deg", "yaw_rate_std_dps",
    "n_stops", "time_stopped_frac", "speed_cv",
    "accel_rms_ms2", "decel_p05_ms2", "hard_decel_per_min",
]

rows = []


def add(analysis, feature, stat_name, stat, p=None, n=None, note=""):
    rows.append(dict(analysis=analysis, feature=feature, statistic=stat_name,
                     value=round(float(stat), 3),
                     p=round(float(p), 4) if p is not None else "",
                     n=n, note=note))


def main():
    feats = pd.read_csv(os.path.join(HERE, "features.csv"))
    thirds = pd.read_csv(os.path.join(HERE, "features_thirds.csv"))

    print("=" * 72)
    print("A) Pooled Spearman feature vs MISC (n=22, exploratory)")
    print("=" * 72)
    for f in FEATURES:
        rho, p = spearmanr(feats[f], feats.misc)
        add("A_pooled", f, "spearman_rho", rho, p, len(feats))
        print(f"  {f:28s} rho={rho:+.2f}  p={p:.3f}")
    rho, p = spearmanr(feats.drive, feats.misc)
    add("A_pooled", "drive_number", "spearman_rho", rho, p, len(feats),
        "confounder check")
    print(f"  {'drive_number (confounder)':28s} rho={rho:+.2f}  p={p:.3f}")

    print("\n" + "=" * 72)
    print("B) Within-participant deltas: consecutive drives (n=14 transitions)")
    print("=" * 72)
    deltas = []
    for pid, g in feats.groupby("participant"):
        g = g.sort_values("drive")
        if len(g) < 2:
            continue
        d = g[FEATURES + ["misc"]].diff().dropna()
        deltas.append(d)
    dd = pd.concat(deltas)
    for f in FEATURES:
        rho, p = spearmanr(dd[f], dd.misc)
        add("B_within_deltas", f, "spearman_rho", rho, p, len(dd))
        print(f"  d({f:26s}) vs dMISC  rho={rho:+.2f}  p={p:.3f}")

    print("\n" + "=" * 72)
    print("C) Within-drive change, third 3 minus third 1 (RQ3)")
    print("=" * 72)
    t1 = thirds[thirds.third == 1].set_index(["participant", "drive"])
    t3 = thirds[thirds.third == 3].set_index(["participant", "drive"])
    misc = feats.set_index(["participant", "drive"]).misc
    for f in FEATURES:
        change = (t3[f] - t1[f]).reindex(misc.index)
        rho, p = spearmanr(change, misc)
        add("C_thirds_vs_misc", f, "spearman_rho", rho, p, len(misc))
        w, pw = wilcoxon(t1[f], t3[f])
        add("C_third1_vs_third3", f, "wilcoxon_W", w, pw, len(t1),
            f"median change {np.median(t3[f]-t1[f]):+.3f}")
        print(f"  {f:28s} change-vs-MISC rho={rho:+.2f} p={p:.3f} | "
              f"third1->3 median {np.median(t3[f]-t1[f]):+.3f} (Wilcoxon p={pw:.3f})")

    print("\n" + "=" * 72)
    print("D) P66 (dropout) vs the other 7 first drives (z-scores)")
    print("=" * 72)
    first = feats[feats.drive == 1]
    p66 = first[first.participant == 66].iloc[0]
    others = first[first.participant != 66]
    for f in FEATURES:
        mu, sd = others[f].mean(), others[f].std()
        z = (p66[f] - mu) / sd if sd > 0 else np.nan
        add("D_p66_vs_first_drives", f, "z_score", z, None, len(others),
            f"P66={p66[f]:.3f} others mean={mu:.3f}")
        print(f"  {f:28s} P66={p66[f]:8.3f}  others {mu:8.3f} ± {sd:.3f}  z={z:+.2f}")

    pd.DataFrame(rows).to_csv(os.path.join(HERE, "stats_summary.csv"), index=False)
    print(f"\nwrote stats_summary.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
