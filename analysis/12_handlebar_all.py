"""Iteration 3: handlebar features for the FULL dataset (both archives).

Sources
  new data/P<n>D<d>/*_SimBike.csv   participants 1-41  (identity from folder name)
  data june/*_SimBike.csv          participants 60-68  (identity from drives_v2.csv)

Robustness decisions, all forced by the audit (script 11):
  * Timestamps: use `UnixTimestamp` when usable; fall back to parsing the `Time`
    column (`YYYYMMDD_HHMMSS_mmm`) when it is constant/corrupt. This recovers
    P2D1, whose UnixTimestamp was destroyed by an Excel round-trip
    (all 11 100 rows hold "1.77126E+12") while `Time` stayed intact.
  * Schema: the archive mixes 19- and 22-column SimBike variants. Only the six
    columns the handlebar analysis needs are read, so both parse identically.
  * Restart variants (P39D2, P39D2_1, P39D2_2): the plain folder is empty; the
    variant with the most valid moving frames is used and the choice is logged.
  * Empty folders (P32D1) are skipped and reported.

Identity is validated independently: scenario == 3*(participant-1) + (drive-1)
holds for 107/107 new folders and 25/25 June drives, so the explicit folder labels
and the iteration-1/2 timestamp reconstruction agree.

Metrics are unchanged from 08_handlebar_features.py so the pilot and the full run
are directly comparable. See ITERATION2_DESIGN.md Q3-Q4 for definitions.

Outputs: handlebar_drives_all.csv, handlebar_participants_all.csv
"""
import glob
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NEW = os.path.join(ROOT, "new data")
OLD = os.path.join(ROOT, "data june")

NEEDED = ["UnixTimestamp", "ForwardVel", "BikeYaw", "HandlebarYaw", "PosX", "PosZ"]
STANDSTILL = 0.5
SUSTAIN_S = 1.0
REVERSAL_DEADBAND = 2.0

log = []


def wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


def read_times(path, n_rows_hint=None):
    """Epoch seconds, preferring UnixTimestamp, falling back to the Time column."""
    with open(path, encoding="utf-8-sig") as f:
        header = f.readline().strip().lstrip("﻿").split(",")
    use = [c for c in NEEDED if c in header]
    if "Time" in header:
        use.append("Time")
    df = pd.read_csv(path, encoding="utf-8-sig", usecols=use, on_bad_lines="skip")

    ts = None
    if "UnixTimestamp" in df.columns:
        u = pd.to_numeric(df["UnixTimestamp"], errors="coerce")
        if u.notna().sum() > 50 and u.nunique() > max(10, 0.5 * u.notna().sum()):
            ts = u / 1000.0
    if ts is None and "Time" in df.columns:
        parsed = pd.to_datetime(df["Time"], format="%Y%m%d_%H%M%S_%f",
                                errors="coerce", utc=True)
        if parsed.notna().sum() > 50:
            # Unit-safe: pandas >=3 may infer datetime64[ms] rather than [ns], so
            # astype("int64") does NOT reliably give nanoseconds. total_seconds()
            # is resolution-independent. (Epoch offset is irrelevant — every
            # downstream metric uses differences only.)
            ts = (parsed - parsed.iloc[0]).dt.total_seconds()
            log.append("    timestamp fallback to Time column: "
                       f"{os.path.basename(path)}")
    if ts is None:
        return None
    df["_t"] = ts
    return df


def load_clean(path):
    """Trimmed, derived signals for one SimBike file; None if unusable."""
    df = read_times(path)
    if df is None:
        return None
    for c in ["_t", "ForwardVel", "BikeYaw", "HandlebarYaw"]:
        if c not in df.columns:
            return None
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["_t", "ForwardVel", "BikeYaw", "HandlebarYaw"])
    df = df.sort_values("_t").reset_index(drop=True)
    if len(df) < 100:
        return None

    t = df["_t"].to_numpy()
    dt = np.diff(t)
    dt_med = float(np.median(dt[dt > 0])) if (dt > 0).any() else None
    if not dt_med or dt_med <= 0:
        return None

    speed = df["ForwardVel"].to_numpy()
    win = max(1, int(round(SUSTAIN_S / dt_med)))
    moving = (np.abs(speed) > STANDSTILL).astype(int)
    if len(moving) < win:
        return None
    sustained = np.convolve(moving, np.ones(win, int), "valid") == win
    idx = np.flatnonzero(sustained)
    if len(idx) == 0:
        return None
    lo, hi = idx[0], min(idx[-1] + win - 1, len(df) - 1)
    df = df.iloc[lo:hi + 1].reset_index(drop=True)
    t = t[lo:hi + 1]

    out = pd.DataFrame({
        "t_s": t - t[0],
        "speed_ms": df["ForwardVel"].to_numpy(),
        "steer_deg": wrap180(df["HandlebarYaw"].to_numpy()
                             - df["BikeYaw"].to_numpy()),
    })
    # guard against duplicate timestamps before differentiating
    good = np.concatenate([[True], np.diff(out["t_s"].to_numpy()) > 0])
    out = out[good].reset_index(drop=True)
    if len(out) < 100:
        return None
    out["steer_rate_dps"] = np.gradient(out["steer_deg"].to_numpy(),
                                        out["t_s"].to_numpy())
    out["steer_jerk_dps2"] = np.gradient(out["steer_rate_dps"].to_numpy(),
                                         out["t_s"].to_numpy())
    return out


def reversal_count(steer):
    n, ref, direction = 0, steer[0], 0
    for x in steer[1:]:
        d = x - ref
        if direction >= 0 and d <= -REVERSAL_DEADBAND:
            if direction == 1:
                n += 1
            direction, ref = -1, x
        elif direction <= 0 and d >= REVERSAL_DEADBAND:
            if direction == -1:
                n += 1
            direction, ref = 1, x
        elif (direction >= 0 and d > 0) or (direction <= 0 and d < 0):
            ref = x
    return n


def metrics(df):
    ride = df[df["speed_ms"] >= STANDSTILL]
    if len(ride) < 50:
        return None
    steer = ride["steer_deg"].to_numpy()
    rate = ride["steer_rate_dps"].to_numpy()
    jerk = ride["steer_jerk_dps2"].to_numpy()
    dt_med = float(np.median(np.diff(df["t_s"].to_numpy())))
    moving_min = len(ride) * dt_med / 60.0
    if moving_min <= 0:
        return None
    return dict(
        riding_time_s=round(float(df["t_s"].iloc[-1]), 1),
        moving_time_min=round(moving_min, 2),
        hz=round(1 / dt_med, 1),
        steer_absmean_deg=round(float(np.mean(np.abs(steer))), 3),
        steer_sd_deg=round(float(np.std(steer, ddof=1)), 3),
        steer_p95_abs_deg=round(float(np.percentile(np.abs(steer), 95)), 3),
        steer_range_deg=round(float(steer.max() - steer.min()), 3),
        steer_iqr_deg=round(float(np.percentile(steer, 75)
                                  - np.percentile(steer, 25)), 3),
        steerrate_absmean_dps=round(float(np.mean(np.abs(rate))), 3),
        steerrate_sd_dps=round(float(np.std(rate, ddof=1)), 3),
        steer_reversals_per_min=round(reversal_count(steer) / moving_min, 3),
        steer_jerk_rms_dps2=round(float(np.sqrt(np.mean(jerk ** 2))), 2),
        speed_mean_ms=round(float(ride["speed_ms"].mean()), 3),
        speed_sd_ms=round(float(ride["speed_ms"].std(ddof=1)), 3),
    )


def collect_new():
    """(participant, drive, cohort, scenario, path) for the new archive."""
    jobs = {}
    for name in sorted(os.listdir(NEW)):
        full = os.path.join(NEW, name)
        if not os.path.isdir(full):
            continue
        m = re.match(r"^P(\d+)D(\d+)(_\d+)?$", name)
        if not m:
            log.append(f"    skipped unrecognised folder: {name}")
            continue
        pid, drive = int(m.group(1)), int(m.group(2))
        sbs = sorted(glob.glob(os.path.join(full, "*_SimBike.csv")))
        if not sbs:
            log.append(f"    no SimBike file in {name} (empty folder)")
            continue
        for path in sbs:
            sc = re.search(r"_P(\d+)_", os.path.basename(path))
            jobs.setdefault((pid, drive), []).append(
                (int(sc.group(1)) if sc else None, path, name))
    return jobs


def main():
    rows = []
    print("Loading NEW archive (participants 1-41)...")
    for (pid, drive), cands in sorted(collect_new().items()):
        best = None
        for scenario, path, folder in cands:
            clean = load_clean(path)
            if clean is None:
                log.append(f"    unusable: {folder}/{os.path.basename(path)}")
                continue
            m = metrics(clean)
            if m is None:
                log.append(f"    too few moving frames: {folder}")
                continue
            cand = dict(participant=pid, drive=drive, cohort="feb_mar",
                        scenario=scenario, folder=folder,
                        source_file=os.path.basename(path), **m)
            if best is None or cand["moving_time_min"] > best["moving_time_min"]:
                best = cand
        if best is None:
            continue
        if len(cands) > 1:
            log.append(f"    P{pid}D{drive}: {len(cands)} candidate files, kept "
                       f"{best['folder']} (most moving time)")
        rows.append(best)

    print("Loading JUNE archive (participants 60-68)...")
    june = pd.read_csv(os.path.join(HERE, "drives_v2.csv"))
    june = june[june.practice == 0]
    for r in june.itertuples(index=False):
        clean = load_clean(os.path.join(OLD, r.main_file))
        if clean is None:
            log.append(f"    unusable: {r.main_file}")
            continue
        m = metrics(clean)
        if m is None:
            continue
        rows.append(dict(participant=r.participant, drive=r.drive, cohort="june",
                         scenario=r.permutation_id, folder="",
                         source_file=r.main_file, **m))

    dr = pd.DataFrame(rows).sort_values(["participant", "drive"])

    # identity validation: scenario == 3*(P-1) + (D-1)
    pred = 3 * (dr.participant - 1) + (dr.drive - 1)
    dr["scenario_formula_ok"] = (pred == dr.scenario).astype(int)

    dr.to_csv(os.path.join(HERE, "handlebar_drives_all.csv"), index=False)

    # ---- attach MISC per drive from the survey groups table ----
    groups = pd.read_csv(os.path.join(HERE, "sickness_groups.csv"))
    misc_long = groups.melt(id_vars=["participant"],
                            value_vars=["misc_d1", "misc_d2", "misc_d3"],
                            var_name="which", value_name="misc")
    misc_long["drive"] = misc_long["which"].str[-1].astype(int)
    dr = dr.merge(misc_long[["participant", "drive", "misc"]],
                  on=["participant", "drive"], how="left")
    dr.to_csv(os.path.join(HERE, "handlebar_drives_all.csv"), index=False)

    # ---- per participant ----
    mcols = [c for c in dr.columns if c not in
             ("participant", "drive", "cohort", "scenario", "folder",
              "source_file", "misc", "scenario_formula_ok")]
    agg = dr.groupby("participant")[mcols].mean().round(3).reset_index()
    agg["n_drives"] = dr.groupby("participant").size().values
    agg["cohort"] = dr.groupby("participant")["cohort"].first().values
    keep = ["participant", "misc_d1", "misc_d2", "misc_d3", "misc_first",
            "misc_last", "misc_peak", "misc_mean", "misc_delta", "traj_group",
            "traj2", "severity2", "severity3", "dropout", "baseline_misc",
            "n_post_ratings"]
    part = agg.merge(groups[keep], on="participant", how="left")
    part.to_csv(os.path.join(HERE, "handlebar_participants_all.csv"), index=False)

    # ---------------- report ----------------
    print("\n" + "=" * 74)
    print("DATA NOTES")
    print("=" * 74)
    for line in log:
        print(line)
    if not log:
        print("    (none)")

    print("\n" + "=" * 74)
    print("COVERAGE")
    print("=" * 74)
    print(f"drives with handlebar metrics : {len(dr)}")
    print(f"participants                  : {dr.participant.nunique()}")
    print(f"  Feb-Mar cohort : {dr[dr.cohort=='feb_mar'].participant.nunique()} "
          f"participants, {len(dr[dr.cohort=='feb_mar'])} drives")
    print(f"  June cohort    : {dr[dr.cohort=='june'].participant.nunique()} "
          f"participants, {len(dr[dr.cohort=='june'])} drives")
    print(f"scenario formula holds        : {dr.scenario_formula_ok.sum()}/{len(dr)}")
    print(f"sampling rate (Hz)           : median {dr.hz.median():.1f}, "
          f"range {dr.hz.min():.1f}-{dr.hz.max():.1f}")
    print(f"drives missing a MISC rating  : {int(dr.misc.isna().sum())}")

    usable = part[part.traj2.isin(["escalating", "non_escalating"])]
    print(f"\nparticipants usable for group tests (classifiable trajectory + "
          f"telemetry): {len(usable)}")
    print("  traj2      :", usable.traj2.value_counts().to_dict())
    print("  traj_group :", usable.traj_group.value_counts().to_dict())
    print("  severity3  :", part.severity3.value_counts().to_dict())
    print("\nwrote handlebar_drives_all.csv, handlebar_participants_all.csv")


if __name__ == "__main__":
    main()
