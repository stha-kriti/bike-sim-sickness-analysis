"""Iteration 3 step 2: exposure-normalised handlebar metrics.

WHY. The two cohorts cannot be pooled as-is (METHODS_LOG I3.4): Feb-Mar drives run
~400 s, June ~167 s, and drive duration is itself negatively related to every
handlebar metric (rho -0.21..-0.34). So the cohort difference in handlebar movement
is partly an artifact of unequal exposure, and it contaminates the pooled
correlation with sickness.

FIX TESTED HERE. Recompute every metric over a matched window at the start of each
drive, so all drives contribute the same amount of riding:
    full     whole drive (baseline, what iteration 3 used)
    t80      first 80 s of riding   -> keeps all 133 drives / 48 participants
    t120     first 120 s            -> sensitivity check (131 drives)
    d500     first 500 m of path    -> distance-matched instead of time-matched
Distance matching is included because steering is driven by route geometry
(corners), not only by elapsed time.

The window is chosen by which normalisation actually REMOVES the cohort difference
(criterion: cohort rank-biserial nearest 0 across metrics) while retaining data.
Then the sickness analysis is re-run on that window.

Outputs: normalised_drives.csv, normalised_participants.csv, normalisation_check.csv
"""
import glob
import os
import re

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, rankdata, spearmanr

import hb_core as hb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NEW = os.path.join(ROOT, "new data")
OLD = os.path.join(ROOT, "data june")

WINDOWS = [("full", None, None), ("t80", 80, None), ("t120", 120, None),
           ("d500", None, 500)]
log = []


def rank_biserial(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0:
        return np.nan
    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    return (gt - lt) / (len(a) * len(b))


def partial_spearman(x, y, z):
    x, y, z = rankdata(x), rankdata(y), rankdata(z)
    rxy = np.corrcoef(x, y)[0, 1]
    rxz = np.corrcoef(x, z)[0, 1]
    ryz = np.corrcoef(y, z)[0, 1]
    return (rxy - rxz * ryz) / np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))


def jobs():
    """(participant, drive, cohort, scenario, path) for both archives."""
    out = []
    for name in sorted(os.listdir(NEW)):
        full = os.path.join(NEW, name)
        if not os.path.isdir(full):
            continue
        m = re.match(r"^P(\d+)D(\d+)(_\d+)?$", name)
        if not m:
            continue
        for path in sorted(glob.glob(os.path.join(full, "*_SimBike.csv"))):
            out.append((int(m.group(1)), int(m.group(2)), "feb_mar",
                        hb.scenario_of(path), path, name))
    june = pd.read_csv(os.path.join(HERE, "drives_v2.csv"))
    june = june[june.practice == 0]
    for r in june.itertuples(index=False):
        out.append((r.participant, r.drive, "june", r.permutation_id,
                    os.path.join(OLD, r.main_file), ""))
    return out


def main():
    # ---------- compute every window for every drive ----------
    rows = {}
    for pid, drive, cohort, scenario, path, folder in jobs():
        clean = hb.load_clean(path, log)
        if clean is None:
            log.append(f"    unusable: {folder or os.path.basename(path)}")
            continue
        rec = dict(participant=pid, drive=drive, cohort=cohort, scenario=scenario,
                   folder=folder, source_file=os.path.basename(path))
        ok = True
        for wname, secs, metres in WINDOWS:
            sub = clean
            if secs is not None:
                sub = hb.window_by_time(clean, secs)
            elif metres is not None:
                sub = hb.window_by_distance(clean, metres)
            m = hb.metrics(sub, prefix=f"{wname}_")
            if m is None:
                ok = False
                if wname == "full":
                    break
                continue
            rec.update(m)
        if not ok and f"full_steer_sd_deg" not in rec:
            continue
        # keep the longest candidate per (participant, drive)
        key = (pid, drive)
        if key not in rows or rec.get("full_moving_time_min", 0) > \
                rows[key].get("full_moving_time_min", 0):
            if key in rows:
                log.append(f"    P{pid}D{drive}: multiple files, kept longer")
            rows[key] = rec

    dr = pd.DataFrame(rows.values()).sort_values(["participant", "drive"])

    # attach MISC
    groups = pd.read_csv(os.path.join(HERE, "sickness_groups.csv"))
    ml = groups.melt(id_vars=["participant"],
                     value_vars=["misc_d1", "misc_d2", "misc_d3"],
                     var_name="which", value_name="misc")
    ml["drive"] = ml["which"].str[-1].astype(int)
    dr = dr.merge(ml[["participant", "drive", "misc"]], on=["participant", "drive"],
                  how="left")
    dr.to_csv(os.path.join(HERE, "normalised_drives.csv"), index=False)

    # ---------- per participant ----------
    mcols = [c for c in dr.columns if any(c.startswith(w + "_")
                                          for w, _, _ in WINDOWS)]
    agg = dr.groupby("participant")[mcols].mean().round(3).reset_index()
    agg["n_drives"] = dr.groupby("participant").size().values
    agg["cohort"] = dr.groupby("participant")["cohort"].first().values
    keep = ["participant", "misc_d1", "misc_d2", "misc_d3", "misc_peak",
            "misc_mean", "misc_delta", "traj_group", "traj2", "severity2",
            "severity3", "dropout"]
    part = agg.merge(groups[keep], on="participant", how="left")
    part.to_csv(os.path.join(HERE, "normalised_participants.csv"), index=False)

    if log:
        print("DATA NOTES")
        for line in dict.fromkeys(log):
            print(line)
        print()

    # ---------- 1. which window removes the cohort effect? ----------
    print("=" * 80)
    print("1) DOES NORMALISATION REMOVE THE COHORT DIFFERENCE?")
    print("   (rank-biserial nearest 0 = cohorts most comparable)")
    print("=" * 80)
    check = []
    fm = part[part.cohort == "feb_mar"]
    jn = part[part.cohort == "june"]
    hdr = "  %-30s" % "metric" + "".join("%12s" % w for w, _, _ in WINDOWS)
    print(hdr)
    for col, desc in hb.METRIC_LABELS:
        line = "  %-30s" % desc
        for wname, _, _ in WINDOWS:
            c = f"{wname}_{col}"
            if c not in part.columns:
                line += "%12s" % "-"
                continue
            a, b = fm[c].dropna(), jn[c].dropna()
            rb = rank_biserial(a, b)
            u, p = mannwhitneyu(a, b, alternative="two-sided")
            line += "%12s" % f"{rb:+.2f}{'*' if p < 0.05 else ' '}"
            check.append(dict(window=wname, metric=col, test="cohort_rb",
                              value=round(rb, 3), p=round(p, 4)))
        print(line)
    print("  * = cohorts still differ significantly (p<0.05)")
    print()
    summary = (pd.DataFrame(check).groupby("window")
               .agg(mean_abs_rb=("value", lambda s: np.mean(np.abs(s))),
                    n_sig=("p", lambda s: int((s < 0.05).sum())))
               .round(3))
    print("  Summary across the 8 metrics:")
    print(summary.to_string())
    exposure = {w: (part[f"{w}_window_s"].groupby(part.cohort).median().to_dict()
                    if f"{w}_window_s" in part.columns else {})
                for w, _, _ in WINDOWS}
    print("\n  median window actually realised (s), by cohort:")
    for w, v in exposure.items():
        if v:
            print(f"    {w:6s} feb_mar={v.get('feb_mar', float('nan')):6.1f}  "
                  f"june={v.get('june', float('nan')):6.1f}")

    best = summary.mean_abs_rb.idxmin()
    print(f"\n  => most cohort-neutral window: {best}")

    # ---------- 2. sickness analysis under each window ----------
    print("\n" + "=" * 80)
    print("2) HANDLEBAR vs SICKNESS LEVEL under each normalisation")
    print("   pooled rho | pooled partial-out-cohort | feb_mar only")
    print("=" * 80)
    res = []
    for wname, _, _ in WINDOWS:
        print(f"\n  --- window {wname} ---")
        for col, desc in hb.METRIC_LABELS:
            c = f"{wname}_{col}"
            if c not in part.columns:
                continue
            sub = part[[c, "misc_peak", "cohort"]].dropna()
            rho, p = spearmanr(sub[c], sub.misc_peak)
            pc = partial_spearman(sub[c], sub.misc_peak,
                                  (sub.cohort == "june").astype(int))
            f = part[part.cohort == "feb_mar"][[c, "misc_peak"]].dropna()
            rf, pf = spearmanr(f[c], f.misc_peak)
            print(f"    {desc:30s} {rho:+.2f}(p={p:.3f})   partial={pc:+.2f}   "
                  f"feb_mar={rf:+.2f}(p={pf:.3f})")
            res.append(dict(window=wname, metric=col, test="vs_misc_peak",
                            pooled_rho=round(rho, 3), pooled_p=round(p, 4),
                            partial_cohort=round(pc, 3),
                            febmar_rho=round(rf, 3), febmar_p=round(pf, 4),
                            n_pooled=len(sub), n_febmar=len(f)))
    # speed, for reference, under the same windows
    print("\n  --- mean speed vs peak MISC (reference) ---")
    for wname, _, _ in WINDOWS:
        c = f"{wname}_speed_mean_ms"
        if c not in part.columns:
            continue
        sub = part[[c, "misc_peak", "cohort"]].dropna()
        rho, p = spearmanr(sub[c], sub.misc_peak)
        pc = partial_spearman(sub[c], sub.misc_peak,
                              (sub.cohort == "june").astype(int))
        f = part[part.cohort == "feb_mar"][[c, "misc_peak"]].dropna()
        rf, pf = spearmanr(f[c], f.misc_peak)
        print(f"    {wname:6s} pooled={rho:+.2f}(p={p:.3f})  partial={pc:+.2f}  "
              f"feb_mar={rf:+.2f}(p={pf:.3f})")
        res.append(dict(window=wname, metric="speed_mean_ms",
                        test="vs_misc_peak", pooled_rho=round(rho, 3),
                        pooled_p=round(p, 4), partial_cohort=round(pc, 3),
                        febmar_rho=round(rf, 3), febmar_p=round(pf, 4),
                        n_pooled=len(sub), n_febmar=len(f)))

    # ---------- 3. group test under the chosen window ----------
    print("\n" + "=" * 80
          + f"\n3) GROUP TEST under '{best}' — escalating vs non_escalating\n"
          + "=" * 80)
    for col, desc in hb.METRIC_LABELS:
        c = f"{best}_{col}"
        if c not in part.columns:
            continue
        e = part[part.traj2 == "escalating"][c].dropna()
        n = part[part.traj2 == "non_escalating"][c].dropna()
        u, p = mannwhitneyu(e, n, alternative="two-sided")
        rb = rank_biserial(e, n)
        print(f"    {desc:30s} esc={e.median():7.2f} non={n.median():7.2f} "
              f"rb={rb:+.2f} p={p:.3f}  (n={len(e)}v{len(n)})")
        res.append(dict(window=best, metric=col, test="traj2_group",
                        pooled_rho=round(rb, 3), pooled_p=round(p, 4),
                        n_pooled=f"{len(e)}v{len(n)}"))

    pd.DataFrame(check + res).to_csv(
        os.path.join(HERE, "normalisation_check.csv"), index=False)
    print("\nwrote normalised_drives.csv, normalised_participants.csv, "
          "normalisation_check.csv")
    print(f"drives={len(dr)}  participants={part.participant.nunique()}")


if __name__ == "__main__":
    main()
