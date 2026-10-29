"""Phase 2: Clean the 22 main drive recordings.

Per drive (main file from drives_summary.csv):
  1. Load, coerce numerics, drop malformed rows (truncated final lines etc.).
  2. Check sampling regularity (nominal 20 Hz) and report gaps.
  3. Trim leading/trailing standstill (|ForwardVel| < STANDSTILL_THRESH sustained).
  4. Unwrap BikeYaw / HandlebarYaw across the 0/360 boundary.
  5. Derive: elapsed time, steering deflection (handlebar minus bike heading,
     wrapped to +/-180), acceleration, yaw rate, steering rate.

Outputs one tidy CSV per drive in cleaned/ plus cleaning_report.csv documenting
every row dropped and second trimmed.
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data june")
CLEAN_DIR = os.path.join(HERE, "cleaned")

STANDSTILL_THRESH = 0.5  # m/s: below this the bike is considered stationary
SUSTAIN_S = 1.0  # riding must be sustained this long to count as start/end
NOMINAL_DT = 0.05  # 20 Hz
GAP_DT = 0.15  # a frame interval above this counts as a logging gap

NUMERIC_COLS = [
    "UnixTimestamp", "PosX", "PosY", "PosZ", "VelX", "VelY", "VelZ",
    "ForwardVel", "RotX", "RotY", "RotZ", "BikeYaw",
    "HandlesRotX", "HandlesRotY", "HandlesRotZ", "HandlebarYaw",
    "BusStationNumber", "BusHMIState", "Infra_HMI_5", "Infra_HMI_6",
]


def wrap180(deg):
    return (deg + 180.0) % 360.0 - 180.0


def riding_bounds(speed, dt):
    """First/last index of sustained riding (speed above threshold for SUSTAIN_S)."""
    win = max(1, int(round(SUSTAIN_S / dt)))
    moving = (np.abs(speed) > STANDSTILL_THRESH).astype(int)
    sustained = np.convolve(moving, np.ones(win, dtype=int), mode="valid") == win
    idx = np.flatnonzero(sustained)
    if len(idx) == 0:
        return None, None
    return idx[0], idx[-1] + win - 1


def clean_drive(row):
    path = os.path.join(DATA, row.main_file)
    df = pd.read_csv(path, encoding="utf-8-sig")
    n_raw = len(df)

    for c in NUMERIC_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # a malformed (truncated) row has NaNs in essential columns
    essential = ["UnixTimestamp", "PosX", "PosZ", "ForwardVel", "BikeYaw", "HandlebarYaw"]
    df = df.dropna(subset=essential).reset_index(drop=True)
    n_malformed = n_raw - len(df)

    t = df["UnixTimestamp"].to_numpy() / 1000.0
    dt = np.diff(t)
    n_gaps = int((dt > GAP_DT).sum())
    dt_median = float(np.median(dt))

    lo, hi = riding_bounds(df["ForwardVel"].to_numpy(), dt_median)
    if lo is None:
        raise ValueError(f"{row.main_file}: no sustained riding found")
    trimmed_lead_s = t[lo] - t[0]
    trimmed_trail_s = t[-1] - t[hi]
    df = df.iloc[lo : hi + 1].reset_index(drop=True)
    t = t[lo : hi + 1]

    out = pd.DataFrame()
    out["participant"] = np.full(len(df), row.participant)
    out["drive"] = np.full(len(df), row.drive)
    out["misc"] = np.full(len(df), row.misc_score)
    out["t_s"] = t - t[0]
    out["UnixTimestamp"] = df["UnixTimestamp"]
    out["PosX"] = df["PosX"]
    out["PosZ"] = df["PosZ"]
    out["speed_ms"] = df["ForwardVel"]

    bike_yaw = np.unwrap(df["BikeYaw"].to_numpy(), period=360.0)
    bar_yaw = np.unwrap(df["HandlebarYaw"].to_numpy(), period=360.0)
    out["bike_yaw_deg"] = bike_yaw
    out["handlebar_yaw_deg"] = bar_yaw
    out["steer_deflection_deg"] = wrap180(
        df["HandlebarYaw"].to_numpy() - df["BikeYaw"].to_numpy()
    )
    out["accel_ms2"] = np.gradient(out["speed_ms"].to_numpy(), out["t_s"].to_numpy())
    # Smoothed speed/accel for feature computation: raw accel contains sharp
    # multi-frame events (collisions / hard maneuvers in the sim physics) plus
    # noise from sampling jitter (median dt ~0.03 s, gaps up to ~0.14 s).
    # Rolling median (5) kills single-frame glitches, rolling mean (5) tames
    # jitter; the underlying events remain visible, just band-limited.
    speed_smooth = (
        out["speed_ms"].rolling(5, center=True, min_periods=1).median()
        .rolling(5, center=True, min_periods=1).mean()
    )
    out["speed_smooth_ms"] = speed_smooth
    out["accel_smooth_ms2"] = np.gradient(speed_smooth.to_numpy(), out["t_s"].to_numpy())
    out["yaw_rate_dps"] = np.gradient(bike_yaw, out["t_s"].to_numpy())
    out["steer_rate_dps"] = np.gradient(bar_yaw, out["t_s"].to_numpy())

    for c in ["BusStationNumber", "BusHMIState", "Infra_HMI_5", "Infra_HMI_6"]:
        out[c] = df[c].astype(int)

    dest = os.path.join(CLEAN_DIR, f"P{row.participant}_drive{row.drive}.csv")
    out.to_csv(dest, index=False)

    dist = float(
        np.sum(np.hypot(np.diff(out["PosX"].to_numpy()), np.diff(out["PosZ"].to_numpy())))
    )
    return dict(
        participant=row.participant,
        drive=row.drive,
        misc=row.misc_score,
        source_file=row.main_file,
        rows_raw=n_raw,
        rows_malformed_dropped=n_malformed,
        rows_clean=len(out),
        trimmed_lead_s=round(trimmed_lead_s, 2),
        trimmed_trail_s=round(trimmed_trail_s, 2),
        duration_clean_s=round(float(out["t_s"].iloc[-1]), 2),
        distance_m=round(dist, 1),
        dt_median_s=round(dt_median, 4),
        n_logging_gaps=n_gaps,
        speed_max_ms=round(float(out["speed_ms"].max()), 2),
        speed_mean_ms=round(float(out["speed_ms"].mean()), 2),
    )


def main():
    os.makedirs(CLEAN_DIR, exist_ok=True)
    drives = pd.read_csv(os.path.join(HERE, "drives_summary.csv"))
    report = [clean_drive(row) for row in drives.itertuples(index=False)]
    rep = pd.DataFrame(report)
    rep.to_csv(os.path.join(HERE, "cleaning_report.csv"), index=False)
    print(rep.to_string(index=False))
    print(
        f"\n{len(rep)} drives cleaned -> {CLEAN_DIR}"
        f"\ntotal rows dropped as malformed: {rep.rows_malformed_dropped.sum()}"
        f"\ntotal standstill trimmed: "
        f"{(rep.trimmed_lead_s + rep.trimmed_trail_s).sum():.1f} s"
    )


if __name__ == "__main__":
    main()
