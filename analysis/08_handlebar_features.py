"""Iteration 2, step 3: handlebar-focused features (cleaning + metrics in one pass).

Answers the supervisor's questions 3-5 concretely.

WHAT IS "HANDLEBAR ROTATION"?  The logs give HandlebarYaw and BikeYaw both as
ABSOLUTE world headings. HandlebarYaw on its own is dominated by where the bike is
pointing along the route (it sweeps through 360 deg on every corner), so it is NOT a
measure of rider input. The steering input is the DIFFERENCE:

    steer_deflection = wrap180(HandlebarYaw - BikeYaw)

That is route-independent: 0 deg = bars aligned with the frame (straight ahead),
positive/negative = steering right/left relative to travel. Every handlebar metric
below is built on this quantity, which is why they are comparable across
participants who rode different scenarios.

METRICS (both of the supervisor's options, plus the rate she asked about):
  average rotation angle      -> steer_absmean_deg   (mean |deflection|)
  deviation of rotation       -> steer_sd_deg        (SD of deflection)  [PRIMARY]
  "changing speed"            -> steerrate_absmean_dps, steerrate_sd_dps
  micro-correction frequency  -> steer_reversals_per_min
  smoothness                  -> steer_jerk_rms_dps2

All computed on MOVING frames only (speed >= 0.5 m/s): handlebar wiggle while
parked is not riding behaviour. Rates use real timestamps (~32 Hz, jittered).

Outputs: handlebar_drives.csv       (one row per drive)
         handlebar_participants.csv (one row per participant, + group labels)
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data june")

STANDSTILL = 0.5      # m/s, below this the bike is stopped
SUSTAIN_S = 1.0       # riding must persist this long to mark drive start/end
REVERSAL_DEADBAND = 2.0   # deg, minimum excursion between counted reversals


def wrap180(deg):
    return (deg + 180.0) % 360.0 - 180.0


def load_and_clean(main_file):
    """Load one SimBike file, trim leading/trailing standstill, derive signals."""
    df = pd.read_csv(os.path.join(DATA, main_file), encoding="utf-8-sig")
    for c in ["UnixTimestamp", "PosX", "PosZ", "ForwardVel", "BikeYaw",
              "HandlebarYaw"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["UnixTimestamp", "ForwardVel", "BikeYaw",
                           "HandlebarYaw"]).reset_index(drop=True)

    t = df["UnixTimestamp"].to_numpy() / 1000.0
    speed = df["ForwardVel"].to_numpy()
    dt_med = float(np.median(np.diff(t)))

    # sustained-riding bounds
    win = max(1, int(round(SUSTAIN_S / dt_med)))
    moving = (np.abs(speed) > STANDSTILL).astype(int)
    sustained = np.convolve(moving, np.ones(win, int), "valid") == win
    idx = np.flatnonzero(sustained)
    if len(idx) == 0:
        return None
    lo, hi = idx[0], idx[-1] + win - 1
    df = df.iloc[lo:hi + 1].reset_index(drop=True)
    t = t[lo:hi + 1]

    out = pd.DataFrame({
        "t_s": t - t[0],
        "speed_ms": df["ForwardVel"].to_numpy(),
        # the steering input — see module docstring
        "steer_deg": wrap180(df["HandlebarYaw"].to_numpy()
                             - df["BikeYaw"].to_numpy()),
    })
    out["steer_rate_dps"] = np.gradient(out["steer_deg"].to_numpy(),
                                        out["t_s"].to_numpy())
    out["steer_jerk_dps2"] = np.gradient(out["steer_rate_dps"].to_numpy(),
                                         out["t_s"].to_numpy())
    return out


def reversal_count(steer):
    """Direction changes of steering movement exceeding the deadband."""
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


def handlebar_metrics(df):
    """Handlebar metrics over moving frames only."""
    ride = df[df["speed_ms"] >= STANDSTILL]
    if len(ride) < 20:
        return None
    steer = ride["steer_deg"].to_numpy()
    rate = ride["steer_rate_dps"].to_numpy()
    jerk = ride["steer_jerk_dps2"].to_numpy()
    moving_min = (len(ride) * float(np.median(np.diff(df["t_s"])))) / 60.0
    return dict(
        riding_time_s=round(float(df["t_s"].iloc[-1]), 1),
        moving_time_min=round(moving_min, 2),
        # --- the supervisor's two options ---
        steer_absmean_deg=round(float(np.mean(np.abs(steer))), 3),
        steer_sd_deg=round(float(np.std(steer, ddof=1)), 3),
        # --- distribution shape ---
        steer_p95_abs_deg=round(float(np.percentile(np.abs(steer), 95)), 3),
        steer_range_deg=round(float(steer.max() - steer.min()), 3),
        steer_iqr_deg=round(float(np.percentile(steer, 75)
                                  - np.percentile(steer, 25)), 3),
        # --- "changing speed" of the handlebar ---
        steerrate_absmean_dps=round(float(np.mean(np.abs(rate))), 3),
        steerrate_sd_dps=round(float(np.std(rate, ddof=1)), 3),
        # --- correction frequency and smoothness ---
        steer_reversals_per_min=round(reversal_count(steer) / moving_min, 3)
        if moving_min > 0 else np.nan,
        steer_jerk_rms_dps2=round(float(np.sqrt(np.mean(jerk ** 2))), 2),
        # --- speed kept only as a control variable, not a focus ---
        speed_mean_ms=round(float(ride["speed_ms"].mean()), 3),
    )


def main():
    drives = pd.read_csv(os.path.join(HERE, "drives_v2.csv"))
    groups = pd.read_csv(os.path.join(HERE, "sickness_groups.csv"))
    drives = drives[drives.practice == 0]  # exclude practice/aborted runs

    rows = []
    for r in drives.itertuples(index=False):
        clean = load_and_clean(r.main_file)
        if clean is None:
            print(f"  SKIP {r.main_file}: no sustained riding")
            continue
        m = handlebar_metrics(clean)
        if m is None:
            print(f"  SKIP {r.main_file}: too few moving frames")
            continue
        rows.append(dict(participant=r.participant, drive=r.drive,
                         misc=r.misc_score, scenario=r.permutation_id,
                         source_file=r.main_file, **m))

    dr = pd.DataFrame(rows).sort_values(["participant", "drive"])
    dr.to_csv(os.path.join(HERE, "handlebar_drives.csv"), index=False)

    # ---- per participant: mean across their drives + group labels ----
    metric_cols = [c for c in dr.columns
                   if c not in ("participant", "drive", "misc", "scenario",
                                "source_file")]
    agg = dr.groupby("participant")[metric_cols].mean().round(3).reset_index()
    agg["n_drives"] = dr.groupby("participant").size().values
    keep = ["participant", "misc_d1", "misc_d2", "misc_d3", "misc_first",
            "misc_last", "misc_peak", "misc_mean", "misc_delta", "traj_group",
            "traj2", "severity2", "severity3", "dropout"]
    part = agg.merge(groups[keep], on="participant", how="left")
    part.to_csv(os.path.join(HERE, "handlebar_participants.csv"), index=False)

    # ---- report ----
    pd.set_option("display.width", 200)
    print("\nPer-drive handlebar metrics (25 drives):")
    print(dr[["participant", "drive", "misc", "steer_absmean_deg", "steer_sd_deg",
              "steerrate_absmean_dps", "steer_reversals_per_min",
              "speed_mean_ms"]].to_string(index=False))
    print("\nPer-participant summary with sickness groups:")
    print(part[["participant", "n_drives", "misc_peak", "misc_delta", "traj_group",
                "traj2", "severity3", "steer_absmean_deg", "steer_sd_deg",
                "steerrate_absmean_dps"]].to_string(index=False))
    print("\nwrote handlebar_drives.csv, handlebar_participants.csv")


if __name__ == "__main__":
    main()
