"""Phase 3: Per-drive feature engineering.

Input:  cleaned/P<participant>_drive<N>.csv  (Phase 2 output)
Output: features.csv         one row per drive (22 rows), all features
        features_thirds.csv  same features computed per drive-third (RQ3)

All count-like features are rate-normalized (per minute) because route length
and duration differ by scenario (METHODS_LOG Finding 2.4). Speed maxima are
censored at the 7.5 m/s cap (Finding 2.2), so variability measures and
time-at-cap are used instead of absolute maxima.
"""
import glob
import os
import re

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN_DIR = os.path.join(HERE, "cleaned")

HARD_DECEL_MS2 = -8.0  # raw-accel threshold for a hard-braking/collision event
CAP_MS = 7.4  # counts as riding at the 7.5 m/s speed cap
STOP_MS = 0.5  # below this = stopped
STOP_MIN_S = 1.0  # sustained this long to count as a mid-drive stop
REVERSAL_DEADBAND_DEG = 2.0  # min steering swing between counted reversals


def count_events(mask, t, min_gap_s=0.5):
    """Count clusters of True frames; clusters closer than min_gap_s merge."""
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return 0
    breaks = np.flatnonzero(np.diff(t[idx]) > min_gap_s)
    return len(breaks) + 1


def count_stops(speed, t):
    """Mid-drive stops: sustained speed < STOP_MS for >= STOP_MIN_S."""
    stopped = speed < STOP_MS
    n = 0
    i = 0
    while i < len(stopped):
        if stopped[i]:
            j = i
            while j + 1 < len(stopped) and stopped[j + 1]:
                j += 1
            if t[j] - t[i] >= STOP_MIN_S:
                n += 1
            i = j + 1
        else:
            i += 1
    return n


def steering_reversal_count(steer_deg):
    """Count direction changes of steering movement larger than the deadband
    (classic steering-reversal-rate metric)."""
    n = 0
    ref = steer_deg[0]
    direction = 0  # +1 rising, -1 falling, 0 unknown
    for x in steer_deg[1:]:
        d = x - ref
        if direction >= 0 and d <= -REVERSAL_DEADBAND_DEG:
            if direction == 1:
                n += 1
            direction = -1
            ref = x
        elif direction <= 0 and d >= REVERSAL_DEADBAND_DEG:
            if direction == -1:
                n += 1
            direction = 1
            ref = x
        elif (direction >= 0 and d > 0) or (direction <= 0 and d < 0):
            ref = x  # extend the current excursion
    return n


def features(df):
    t = df["t_s"].to_numpy()
    dur_s = t[-1] - t[0]
    dur_min = dur_s / 60.0
    speed = df["speed_ms"].to_numpy()
    accel_raw = df["accel_ms2"].to_numpy()
    accel = df["accel_smooth_ms2"].to_numpy()
    steer = df["steer_deflection_deg"].to_numpy()
    yaw_rate = df["yaw_rate_dps"].to_numpy()
    dist = float(np.sum(np.hypot(np.diff(df["PosX"].to_numpy()),
                                 np.diff(df["PosZ"].to_numpy()))))
    riding = speed >= STOP_MS  # exclude stopped frames from steering stats
    return dict(
        duration_s=round(dur_s, 1),
        distance_m=round(dist, 1),
        speed_mean_ms=round(float(speed.mean()), 3),
        speed_std_ms=round(float(speed.std()), 3),
        speed_cv=round(float(speed.std() / speed.mean()), 3),
        time_at_cap_frac=round(float((speed > CAP_MS).mean()), 3),
        time_stopped_frac=round(float((speed < STOP_MS).mean()), 3),
        n_stops=count_stops(speed, t),
        accel_rms_ms2=round(float(np.sqrt(np.mean(accel**2))), 3),
        decel_p05_ms2=round(float(np.percentile(accel, 5)), 3),
        hard_decel_per_min=round(
            count_events(accel_raw < HARD_DECEL_MS2, t) / dur_min, 3
        ),
        steer_std_deg=round(float(steer[riding].std()), 3),
        steer_reversals_per_min=round(
            steering_reversal_count(steer[riding]) / dur_min, 3
        ),
        yaw_rate_std_dps=round(float(yaw_rate[riding].std()), 3),
    )


def main():
    rows, third_rows = [], []
    for f in sorted(glob.glob(os.path.join(CLEAN_DIR, "*.csv"))):
        m = re.match(r"P(\d+)_drive(\d)", os.path.basename(f))
        pid, drive = int(m.group(1)), int(m.group(2))
        df = pd.read_csv(f)
        misc = int(df["misc"].iloc[0])
        base = dict(participant=pid, drive=drive, misc=misc)
        rows.append(base | features(df))
        edges = np.quantile(df["t_s"], [0, 1 / 3, 2 / 3, 1])
        for k in range(3):
            part = df[(df["t_s"] >= edges[k]) & (df["t_s"] <= edges[k + 1])]
            third_rows.append(base | dict(third=k + 1) | features(part))

    feats = pd.DataFrame(rows).sort_values(["participant", "drive"])
    thirds = pd.DataFrame(third_rows).sort_values(["participant", "drive", "third"])
    feats.to_csv(os.path.join(HERE, "features.csv"), index=False)
    thirds.to_csv(os.path.join(HERE, "features_thirds.csv"), index=False)
    print(feats.to_string(index=False))
    print(f"\n{len(feats)} drives -> features.csv; {len(thirds)} rows -> features_thirds.csv")


if __name__ == "__main__":
    main()
