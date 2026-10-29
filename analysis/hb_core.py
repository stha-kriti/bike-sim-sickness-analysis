"""Shared handlebar-analysis core (loader + metrics).

Canonical implementation, used by 14_normalised_metrics.py onward.
`12_handlebar_all.py` keeps its own inline copy so its already-committed outputs
stay bit-for-bit reproducible; this module is the version to maintain going forward.

Definitions (see ITERATION2_DESIGN.md Q3-Q4):
    steer_deflection = wrap180(HandlebarYaw - BikeYaw)   # route-independent input
All metrics use moving frames only (speed >= 0.5 m/s) and real timestamps.
"""
import os
import re

import numpy as np
import pandas as pd

NEEDED = ["UnixTimestamp", "ForwardVel", "BikeYaw", "HandlebarYaw", "PosX", "PosZ"]
STANDSTILL = 0.5
SUSTAIN_S = 1.0
REVERSAL_DEADBAND = 2.0


def wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


def _timestamps(df, header, path, log):
    """Epoch-relative seconds, resolution-safe, with Time-column fallback."""
    ts = None
    if "UnixTimestamp" in df.columns:
        u = pd.to_numeric(df["UnixTimestamp"], errors="coerce")
        if u.notna().sum() > 50 and u.nunique() > max(10, 0.5 * u.notna().sum()):
            ts = u / 1000.0
    if ts is None and "Time" in df.columns:
        parsed = pd.to_datetime(df["Time"], format="%Y%m%d_%H%M%S_%f",
                                errors="coerce", utc=True)
        if parsed.notna().sum() > 50:
            # pandas>=3 may yield datetime64[ms]; total_seconds() is unit-safe.
            ts = (parsed - parsed.iloc[0]).dt.total_seconds()
            if log is not None:
                log.append(f"    timestamp fallback to Time column: "
                           f"{os.path.basename(path)}")
    return ts


def load_clean(path, log=None):
    """Trimmed drive with derived steering signals, or None if unusable."""
    with open(path, encoding="utf-8-sig") as f:
        header = f.readline().strip().lstrip("﻿").split(",")
    use = [c for c in NEEDED if c in header]
    if "Time" in header:
        use.append("Time")
    df = pd.read_csv(path, encoding="utf-8-sig", usecols=use, on_bad_lines="skip")

    ts = _timestamps(df, header, path, log)
    if ts is None:
        return None
    df["_t"] = ts
    for c in ["_t", "ForwardVel", "BikeYaw", "HandlebarYaw", "PosX", "PosZ"]:
        if c not in df.columns:
            return None
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["_t", "ForwardVel", "BikeYaw", "HandlebarYaw",
                           "PosX", "PosZ"])
    df = df.sort_values("_t").reset_index(drop=True)
    if len(df) < 100:
        return None

    t = df["_t"].to_numpy()
    dt = np.diff(t)
    pos = dt[dt > 0]
    if len(pos) == 0:
        return None
    dt_med = float(np.median(pos))
    if dt_med <= 0:
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
        "PosX": df["PosX"].to_numpy(),
        "PosZ": df["PosZ"].to_numpy(),
        "steer_deg": wrap180(df["HandlebarYaw"].to_numpy()
                             - df["BikeYaw"].to_numpy()),
    })
    good = np.concatenate([[True], np.diff(out["t_s"].to_numpy()) > 0])
    out = out[good].reset_index(drop=True)
    if len(out) < 100:
        return None
    out["steer_rate_dps"] = np.gradient(out["steer_deg"].to_numpy(),
                                        out["t_s"].to_numpy())
    out["steer_jerk_dps2"] = np.gradient(out["steer_rate_dps"].to_numpy(),
                                         out["t_s"].to_numpy())
    step = np.concatenate([[0.0], np.hypot(np.diff(out["PosX"].to_numpy()),
                                           np.diff(out["PosZ"].to_numpy()))])
    out["dist_m"] = np.cumsum(step)
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


def metrics(df, prefix=""):
    """Handlebar metrics over the moving frames of `df`."""
    ride = df[df["speed_ms"] >= STANDSTILL]
    if len(ride) < 50:
        return None
    steer = ride["steer_deg"].to_numpy()
    rate = ride["steer_rate_dps"].to_numpy()
    jerk = ride["steer_jerk_dps2"].to_numpy()
    tt = df["t_s"].to_numpy()
    if len(tt) < 2:
        return None
    dt_med = float(np.median(np.diff(tt)))
    moving_min = len(ride) * dt_med / 60.0
    if moving_min <= 0:
        return None
    m = dict(
        window_s=round(float(tt[-1] - tt[0]), 1),
        window_dist_m=round(float(df["dist_m"].iloc[-1] - df["dist_m"].iloc[0]), 1),
        moving_time_min=round(moving_min, 3),
        hz=round(1 / dt_med, 1),
        steer_absmean_deg=round(float(np.mean(np.abs(steer))), 3),
        steer_sd_deg=round(float(np.std(steer, ddof=1)), 3),
        steer_p95_abs_deg=round(float(np.percentile(np.abs(steer), 95)), 3),
        steer_iqr_deg=round(float(np.percentile(steer, 75)
                                  - np.percentile(steer, 25)), 3),
        steerrate_absmean_dps=round(float(np.mean(np.abs(rate))), 3),
        steerrate_sd_dps=round(float(np.std(rate, ddof=1)), 3),
        steer_reversals_per_min=round(reversal_count(steer) / moving_min, 3),
        steer_jerk_rms_dps2=round(float(np.sqrt(np.mean(jerk ** 2))), 2),
        speed_mean_ms=round(float(ride["speed_ms"].mean()), 3),
        speed_sd_ms=round(float(ride["speed_ms"].std(ddof=1)), 3),
    )
    return {prefix + k: v for k, v in m.items()} if prefix else m


def window_by_time(df, seconds):
    return df[df["t_s"] <= df["t_s"].iloc[0] + seconds]


def window_by_distance(df, metres):
    return df[df["dist_m"] <= df["dist_m"].iloc[0] + metres]


def scenario_of(path):
    m = re.search(r"_P(\d+)_", os.path.basename(path))
    return int(m.group(1)) if m else None


METRIC_LABELS = [
    ("steer_sd_deg", "deviation of rotation (SD)"),
    ("steer_absmean_deg", "average rotation angle"),
    ("steer_iqr_deg", "typical spread (IQR)"),
    ("steer_p95_abs_deg", "large corrections (p95)"),
    ("steerrate_absmean_dps", "changing speed (mean |rate|)"),
    ("steerrate_sd_dps", "rate variability (SD)"),
    ("steer_reversals_per_min", "correction frequency"),
    ("steer_jerk_rms_dps2", "jerkiness (RMS)"),
]
