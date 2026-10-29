"""Iteration 3 step 3: is the handlebar signal in the LATE part of a drive?

WHY THIS TEST EXISTS. Script 14 found that matching exposure (first 80/120 s of
every drive) collapses every handlebar-sickness correlation to ~0, and also collapses
the speed one. Two very different explanations fit that:

  (A) ARTIFACT  - the full-drive correlations were driven by unequal exposure
                  between cohorts; normalising removed a spurious effect.
  (B) TIMING    - motion sickness ACCUMULATES. The first 80 s is before symptoms
                  develop, so restricting to it removes the very window in which
                  behaviour could reflect sickness. The full-drive effect is real
                  but carried by the later portion.

These have opposite implications, so they must be separated. The decisive test is
within the Feb-Mar cohort alone, where drive durations are already nearly matched
(262-525 s, median 400 s): exposure is roughly constant there, so if EARLY and LATE
windows of the same length behave differently, that is timing (B), not exposure (A).

Windows compared (all 80 s of riding, same length => same exposure):
    early80   first 80 s
    late80    last 80 s
    mid80     middle 80 s
and the within-drive change  late80 - early80  (does behaviour degrade more in
drives that ended with a worse rating?).

MISC is rated AFTER the drive, so it describes end-of-drive state — which is what
makes the late window the theoretically correct comparison.

Outputs: early_late_drives.csv, early_late_stats.csv
"""
import glob
import os
import re

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon

import hb_core as hb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NEW = os.path.join(ROOT, "new data")
OLD = os.path.join(ROOT, "data june")

WIN_S = 80.0
log = []


def jobs():
    out = []
    for name in sorted(os.listdir(NEW)):
        full = os.path.join(NEW, name)
        if not os.path.isdir(full):
            continue
        m = re.match(r"^P(\d+)D(\d+)(_\d+)?$", name)
        if not m:
            continue
        for path in sorted(glob.glob(os.path.join(full, "*_SimBike.csv"))):
            out.append((int(m.group(1)), int(m.group(2)), "feb_mar", path, name))
    june = pd.read_csv(os.path.join(HERE, "drives_v2.csv"))
    june = june[june.practice == 0]
    for r in june.itertuples(index=False):
        out.append((r.participant, r.drive, "june",
                    os.path.join(OLD, r.main_file), ""))
    return out


def slice_window(clean, kind):
    t = clean["t_s"].to_numpy()
    total = t[-1] - t[0]
    if total < WIN_S * 1.5:      # need early and late to be genuinely disjoint
        return None
    if kind == "early":
        return clean[t <= t[0] + WIN_S]
    if kind == "late":
        return clean[t >= t[-1] - WIN_S]
    mid = t[0] + total / 2
    return clean[(t >= mid - WIN_S / 2) & (t <= mid + WIN_S / 2)]


def main():
    rows = {}
    for pid, drive, cohort, path, folder in jobs():
        clean = hb.load_clean(path, log)
        if clean is None:
            continue
        rec = dict(participant=pid, drive=drive, cohort=cohort,
                   source_file=os.path.basename(path),
                   total_riding_s=round(float(clean["t_s"].iloc[-1]), 1))
        ok = True
        for kind, pref in [("early", "early80_"), ("late", "late80_"),
                           ("mid", "mid80_")]:
            sub = slice_window(clean, kind)
            if sub is None:
                ok = False
                break
            m = hb.metrics(sub, prefix=pref)
            if m is None:
                ok = False
                break
            rec.update(m)
        if not ok:
            log.append(f"    too short for disjoint 80s windows: "
                       f"{folder or os.path.basename(path)} "
                       f"({rec['total_riding_s']}s)")
            continue
        key = (pid, drive)
        if key not in rows or rec["total_riding_s"] > rows[key]["total_riding_s"]:
            rows[key] = rec

    dr = pd.DataFrame(rows.values()).sort_values(["participant", "drive"])

    # within-drive change, same window length so directly comparable
    for col, _ in hb.METRIC_LABELS:
        dr[f"delta_{col}"] = dr[f"late80_{col}"] - dr[f"early80_{col}"]
    dr["delta_speed_mean_ms"] = dr["late80_speed_mean_ms"] - dr["early80_speed_mean_ms"]

    groups = pd.read_csv(os.path.join(HERE, "sickness_groups.csv"))
    ml = groups.melt(id_vars=["participant"],
                     value_vars=["misc_d1", "misc_d2", "misc_d3"],
                     var_name="which", value_name="misc")
    ml["drive"] = ml["which"].str[-1].astype(int)
    dr = dr.merge(ml[["participant", "drive", "misc"]],
                  on=["participant", "drive"], how="left")
    dr.to_csv(os.path.join(HERE, "early_late_drives.csv"), index=False)

    mcols = [c for c in dr.columns if c.startswith(("early80_", "late80_",
                                                    "mid80_", "delta_"))]
    part = dr.groupby("participant")[mcols].mean().round(3).reset_index()
    part["cohort"] = dr.groupby("participant")["cohort"].first().values
    keep = ["participant", "misc_peak", "misc_mean", "misc_delta", "traj2",
            "severity3"]
    part = part.merge(groups[keep], on="participant", how="left")

    if log:
        print("DATA NOTES")
        for line in dict.fromkeys(log):
            print(line)
        print()

    print("=" * 82)
    print(f"Drives with three disjoint {int(WIN_S)}s windows: {len(dr)}  "
          f"(participants {dr.participant.nunique()})")
    print("  by cohort:", dr.cohort.value_counts().to_dict())
    print("=" * 82)

    stats = []

    # ---- 1. per-drive: does each window's metric track that drive's rating? ----
    print("\n1) PER-DRIVE — window metric vs that drive's MISC rating")
    print("   (Feb-Mar only: durations already matched, so this isolates TIMING)")
    print("-" * 82)
    fm = dr[dr.cohort == "feb_mar"]
    print("  %-30s %12s %12s %12s" % ("metric", "early80", "mid80", "late80"))
    for col, desc in hb.METRIC_LABELS:
        line = "  %-30s" % desc
        for pref in ["early80_", "mid80_", "late80_"]:
            sub = fm[[pref + col, "misc"]].dropna()
            rho, p = spearmanr(sub[pref + col], sub["misc"])
            line += "%12s" % f"{rho:+.2f}{'*' if p < 0.05 else ' '}"
            stats.append(dict(level="per_drive", cohort="feb_mar", window=pref,
                              metric=col, test="vs_drive_misc",
                              rho=round(rho, 3), p=round(p, 4), n=len(sub)))
        print(line)
    sub = fm[["early80_speed_mean_ms", "misc"]].dropna()
    r1, p1 = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])
    sub = fm[["late80_speed_mean_ms", "misc"]].dropna()
    r2, p2 = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])
    print("  %-30s %12s %12s %12s" % ("mean speed", f"{r1:+.2f}", "", f"{r2:+.2f}"))
    print("  * p<0.05, uncorrected;  n = %d drives" % len(fm))

    # ---- 2. within-drive change vs rating ----
    print("\n2) WITHIN-DRIVE CHANGE  (late80 - early80)  vs that drive's MISC")
    print("   Same window length, so exposure is identical by construction.")
    print("-" * 82)
    for scope, src in [("feb_mar", fm), ("pooled", dr)]:
        print(f"  --- {scope} (n={len(src)} drives) ---")
        for col, desc in hb.METRIC_LABELS:
            sub = src[[f"delta_{col}", "misc"]].dropna()
            rho, p = spearmanr(sub[f"delta_{col}"], sub["misc"])
            print(f"    d({desc:28s}) rho={rho:+.2f} p={p:.3f}"
                  + ("  *" if p < 0.05 else ""))
            stats.append(dict(level="per_drive", cohort=scope, window="delta",
                              metric=col, test="vs_drive_misc",
                              rho=round(rho, 3), p=round(p, 4), n=len(sub)))
        sub = src[["delta_speed_mean_ms", "misc"]].dropna()
        rho, p = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])
        print(f"    d({'mean speed':28s}) rho={rho:+.2f} p={p:.3f}"
              + ("  *" if p < 0.05 else ""))
        stats.append(dict(level="per_drive", cohort=scope, window="delta",
                          metric="speed_mean_ms", test="vs_drive_misc",
                          rho=round(rho, 3), p=round(p, 4), n=len(sub)))

    # ---- 3. does behaviour drift within a drive at all? ----
    print("\n3) DOES BEHAVIOUR CHANGE WITHIN A DRIVE?  (early80 vs late80, all drives)")
    print("-" * 82)
    for col, desc in hb.METRIC_LABELS + [("speed_mean_ms", "mean speed")]:
        a = dr[f"early80_{col}"].dropna()
        b = dr[f"late80_{col}"].dropna()
        common = dr[[f"early80_{col}", f"late80_{col}"]].dropna()
        w, p = wilcoxon(common.iloc[:, 0], common.iloc[:, 1])
        med = (common.iloc[:, 1] - common.iloc[:, 0]).median()
        print(f"  {desc:30s} early={a.median():8.2f} late={b.median():8.2f}"
              f"  median change={med:+8.2f}  p={p:.4f}")
        stats.append(dict(level="per_drive", cohort="pooled", window="early_vs_late",
                          metric=col, test="wilcoxon", rho=round(float(med), 3),
                          p=round(p, 4), n=len(common)))

    # ---- 4. participant level, late window vs sickness ----
    print("\n4) PARTICIPANT LEVEL — late80 metric vs peak MISC")
    print("-" * 82)
    for scope, src in [("feb_mar", part[part.cohort == "feb_mar"]),
                       ("pooled", part)]:
        print(f"  --- {scope} (n={len(src)}) ---")
        for col, desc in hb.METRIC_LABELS + [("speed_mean_ms", "mean speed")]:
            sub = src[[f"late80_{col}", "misc_peak"]].dropna()
            rho, p = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1])
            print(f"    {desc:30s} rho={rho:+.2f} p={p:.3f}"
                  + ("  *" if p < 0.05 else ""))
            stats.append(dict(level="participant", cohort=scope, window="late80_",
                              metric=col, test="vs_misc_peak", rho=round(rho, 3),
                              p=round(p, 4), n=len(sub)))

    pd.DataFrame(stats).to_csv(os.path.join(HERE, "early_late_stats.csv"),
                              index=False)
    print("\nwrote early_late_drives.csv, early_late_stats.csv")


if __name__ == "__main__":
    main()
