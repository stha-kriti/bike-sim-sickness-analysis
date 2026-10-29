"""Iteration 3, step 1: audit the newly supplied archive in `new data/`.

The folders are named P<participant>D<drive>, so participant identity is EXPLICIT —
the timestamp-reconstruction linkage of iterations 1-2 is not needed for this data.
This script verifies that claim and checks every folder for usability before any
analysis depends on it.

Checks per folder:
  * which file types are present (SimBike / OpenFace / merged)
  * SimBike schema (the archive uses an older 19-column variant)
  * parseable rows, duration, sampling rate, speed sanity
  * whether the required handlebar columns exist and contain usable values
  * internal consistency: does the folder name's participant match the OpenFace
    `Participant_N_...` filename, and does the recording date match the survey date?

Output: new_data_audit.csv + console report of anything unusable.
"""
import csv
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
NEW = os.path.join(os.path.dirname(HERE), "new data")
CEST = timezone(timedelta(hours=2))

NEEDED = ["UnixTimestamp", "ForwardVel", "BikeYaw", "HandlebarYaw", "PosX", "PosZ"]


def folder_key(name):
    """P12D3 / P39D2_1 -> (12, 3, '') / (39, 2, '_1')"""
    m = re.match(r"^P(\d+)D(\d+)(_\d+)?$", name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), (m.group(3) or "")


def audit_simbike(path):
    """Return dict of health metrics for one SimBike file."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            header = f.readline().strip().lstrip("﻿").split(",")
    except OSError as e:
        return dict(readable=0, note=f"unreadable: {e}")
    missing = [c for c in NEEDED if c not in header]
    if missing:
        return dict(readable=1, n_cols=len(header), note="missing cols: "
                    + ",".join(missing))
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", usecols=NEEDED,
                         on_bad_lines="skip")
    except Exception as e:  # noqa: BLE001 - want any parse failure reported
        return dict(readable=1, n_cols=len(header), note=f"parse failed: {e}")

    n_raw = len(df)
    for c in NEEDED:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=NEEDED)
    n_ok = len(df)
    if n_ok < 50:
        return dict(readable=1, n_cols=len(header), rows_raw=n_raw, rows_ok=n_ok,
                    note="too few valid rows")

    t = df["UnixTimestamp"].to_numpy() / 1000.0
    dt = np.diff(t)
    speed = df["ForwardVel"].to_numpy()
    moving = np.abs(speed) > 0.5
    start = datetime.fromtimestamp(t[0], tz=CEST)
    # constant handlebar => sensor dead
    steer = (df["HandlebarYaw"].to_numpy() - df["BikeYaw"].to_numpy())
    notes = []
    if not np.all(dt > 0):
        notes.append("non-monotonic time")
    if np.nanstd(steer) < 1e-6:
        notes.append("handlebar constant (dead signal)")
    if moving.sum() < 50:
        notes.append("almost no movement")
    if np.nanmax(speed) < 1.0:
        notes.append("never moved")
    return dict(
        readable=1, n_cols=len(header), rows_raw=n_raw, rows_ok=n_ok,
        rows_dropped=n_raw - n_ok,
        date=start.strftime("%Y-%m-%d"), start_time=start.strftime("%H:%M:%S"),
        duration_s=round(float(t[-1] - t[0]), 1),
        median_dt_s=round(float(np.median(dt)), 4),
        hz=round(1.0 / float(np.median(dt)), 1) if np.median(dt) > 0 else "",
        moving_frac=round(float(moving.mean()), 3),
        speed_max=round(float(np.nanmax(speed)), 2),
        speed_mean_moving=round(float(np.nanmean(speed[moving])), 2)
        if moving.sum() else "",
        steer_sd_raw=round(float(np.nanstd(steer)), 3),
        note="; ".join(notes),
    )


def survey_dates():
    """participant -> first survey date (for cross-checking recording dates)."""
    ssq = os.path.join(os.path.dirname(HERE), "ssq",
                       "MISC (SSQ) [BikeSim2026].csv")
    out = {}
    with open(ssq, encoding="utf-8-sig", errors="replace") as f:
        for row in list(csv.reader(f))[1:]:
            try:
                pid = int(row[1])
            except (ValueError, IndexError):
                continue
            s = re.sub(r"\s+(OESZ|OEZ)$", "", row[0].strip())
            d = datetime.strptime(s, "%Y/%m/%d %I:%M:%S %p").date()
            if pid not in out or d < out[pid]:
                out[pid] = d
    return out


def main():
    sdates = survey_dates()
    rows = []
    for name in sorted(os.listdir(NEW)):
        full = os.path.join(NEW, name)
        if not os.path.isdir(full):
            continue
        key = folder_key(name)
        if key is None:
            rows.append(dict(folder=name, note="unrecognised folder name"))
            continue
        pid, drive, suffix = key
        files = os.listdir(full)

        simbikes = [f for f in files if f.endswith("_SimBike.csv")]
        openface = [f for f in files if re.match(r"Participant_\d+_", f)]
        merged = [f for f in files if f.startswith("merged")]
        summary = [f for f in files if f.startswith("summary")]

        rec = dict(folder=name, participant=pid, drive=drive,
                   variant=suffix.lstrip("_"),
                   n_simbike=len(simbikes), n_openface=len(openface),
                   n_merged=len(merged), n_summary=len(summary))

        # cross-check: OpenFace filename carries the participant number
        of_ids = {int(re.match(r"Participant_(\d+)_", f).group(1))
                  for f in openface}
        rec["openface_pid_match"] = ("" if not of_ids
                                     else int(of_ids == {pid}))

        if not simbikes:
            rec["note"] = "NO SimBike file"
            rows.append(rec)
            continue
        if len(simbikes) > 1:
            rec["note"] = f"{len(simbikes)} SimBike files"
        sb = sorted(simbikes)[0]
        rec["simbike_file"] = sb
        m = re.search(r"_P(\d+)_", sb)
        rec["scenario"] = int(m.group(1)) if m else ""
        health = audit_simbike(os.path.join(full, sb))
        prev_note = rec.get("note", "")
        rec.update(health)
        if prev_note:
            rec["note"] = (prev_note + "; " + rec.get("note", "")).strip("; ")

        # date cross-check against survey
        if rec.get("date") and pid in sdates:
            rec["date_matches_survey"] = int(
                str(sdates[pid]) == rec["date"])
        rows.append(rec)

    cols = ["folder", "participant", "drive", "variant", "scenario",
            "simbike_file", "n_simbike", "n_openface", "n_merged", "n_summary",
            "openface_pid_match", "date", "date_matches_survey", "start_time",
            "duration_s", "rows_raw", "rows_ok", "rows_dropped", "median_dt_s",
            "hz", "moving_frac", "speed_max", "speed_mean_moving",
            "steer_sd_raw", "n_cols", "readable", "note"]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]
    df.to_csv(os.path.join(HERE, "new_data_audit.csv"), index=False)

    # ---------------- report ----------------
    print("=" * 76)
    print(f"AUDIT of new data/  —  {len(df)} folders")
    print("=" * 76)
    parts = sorted(df.participant.dropna().unique().astype(int))
    print(f"Participants present: {len(parts)}  ->  {parts}")
    print(f"Drive folders: {len(df)} (incl. restart variants)")
    dup = df[df.variant != ""]
    if len(dup):
        print(f"Restart variants: {dup.folder.tolist()}")

    print("\n--- Completeness per participant ---")
    per = defaultdict(list)
    for r in df.itertuples(index=False):
        if pd.notna(r.participant):
            per[int(r.participant)].append(int(r.drive))
    incomplete = {p: sorted(set(d)) for p, d in per.items()
                  if sorted(set(d)) != [1, 2, 3]}
    print(f"Participants with all 3 drives: "
          f"{sum(1 for p, d in per.items() if sorted(set(d)) == [1, 2, 3])}")
    if incomplete:
        print("Incomplete:")
        for p, d in sorted(incomplete.items()):
            print(f"  P{p}: drives {d}")

    print("\n--- File-type coverage ---")
    print(f"folders with SimBike : {(df.n_simbike > 0).sum()}")
    print(f"folders with OpenFace: {(df.n_openface > 0).sum()}")
    print(f"folders with merged  : {(df.n_merged > 0).sum()}")

    print("\n--- Schema ---")
    print(df.n_cols.value_counts().to_string())

    print("\n--- Sampling rate ---")
    hz = pd.to_numeric(df.hz, errors="coerce").dropna()
    if len(hz):
        print(f"median {hz.median():.1f} Hz   range {hz.min():.1f}-{hz.max():.1f} Hz")

    print("\n--- Consistency cross-checks ---")
    ofm = pd.to_numeric(df.openface_pid_match, errors="coerce")
    print(f"OpenFace participant id matches folder: {int((ofm == 1).sum())} ok, "
          f"{int((ofm == 0).sum())} MISMATCH")
    dm = pd.to_numeric(df.date_matches_survey, errors="coerce")
    print(f"recording date matches survey date    : {int((dm == 1).sum())} ok, "
          f"{int((dm == 0).sum())} differ")
    if (dm == 0).any():
        print(df.loc[dm == 0, ["folder", "date"]].to_string(index=False))

    print("\n--- PROBLEMS ---")
    bad = df[df.note.astype(str).str.len() > 0]
    if len(bad) == 0:
        print("none")
    else:
        for r in bad.itertuples(index=False):
            print(f"  {r.folder:12s} {r.note}")

    print("\n--- Duration / movement outliers ---")
    dur = pd.to_numeric(df.duration_s, errors="coerce")
    mv = pd.to_numeric(df.moving_frac, errors="coerce")
    odd = df[(dur < 30) | (mv < 0.3)]
    if len(odd) == 0:
        print("none")
    else:
        print(odd[["folder", "duration_s", "moving_frac", "speed_max"]]
              .to_string(index=False))
    print("\nwrote new_data_audit.csv")


if __name__ == "__main__":
    main()
