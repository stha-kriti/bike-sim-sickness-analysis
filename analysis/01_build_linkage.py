"""Phase 1: Build the participant <-> drive <-> session file <-> MISC linkage table.

Matches MISC survey entries (participants 61-68) to simulator sessions by day and
time. Survey timestamps run ~1 h ahead of the simulator clock, so 1 hour is
subtracted before matching. Sessions ending between the previous and current
(corrected) survey timestamp belong to that drive slot; the longest file in a slot
is the main recording, shorter ones are restarts/fragments.

Outputs: linkage_table.csv (one row per session file, with assignment) and
drives_summary.csv (one row per participant-drive, main file only).
"""
import csv
import glob
import os
import re
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data june")
SSQ = os.path.join(BASE, "ssq", "MISC (SSQ) [BikeSim2026].csv")
OUT = os.path.dirname(os.path.abspath(__file__))

CEST = timezone(timedelta(hours=2))
SURVEY_CLOCK_OFFSET = timedelta(hours=1)  # survey clock ahead of simulator clock
MATCH_WINDOW = timedelta(hours=2)  # max gap between session start and survey entry

MISC_SCALE = {
    "Nothing": 0,
    "Uneasiness": 1,
    "Dizziness, warmth, headache, stomach awareness, sweating - vague": 2,
    "Dizziness, warmth, headache, stomach awareness, sweating - slight": 3,
    "Dizziness, warmth, headache, stomach awareness, sweating - fairly": 4,
    "Dizziness, warmth, headache, stomach awareness, sweating - severe": 5,
    "Nausea - slight": 6,
    "Nausea - fairly": 7,
    "Nausea - severe": 8,
    "Nausea - (near) retching": 9,
    "Vomiting": 10,
}

DRIVE_ORDER = {"After first drive": 1, "After second drive": 2, "After third drive": 3}


def parse_survey_time(s):
    # e.g. "2026/06/22 5:45:37 PM OESZ"
    s = re.sub(r"\s+(OESZ|OEZ)$", "", s.strip())
    return datetime.strptime(s, "%Y/%m/%d %I:%M:%S %p").replace(tzinfo=CEST)


def session_times(simbike_path):
    """Return (start, end) datetimes of a session, tolerating malformed rows."""
    with open(simbike_path, encoding="utf-8-sig") as f:
        header = f.readline().strip().split(",")
        rows = f.readlines()
    if "UnixTimestamp" in header:
        idx = header.index("UnixTimestamp")
        ts = []
        for line in rows:
            parts = line.split(",")
            try:
                ts.append(int(parts[idx]) / 1000)
            except (ValueError, IndexError):
                continue
        if not ts:
            return None, None, len(rows)
        return (
            datetime.fromtimestamp(ts[0], tz=CEST),
            datetime.fromtimestamp(ts[-1], tz=CEST),
            len(rows),
        )
    # old schema: parse the human-readable Time column (local time)
    tidx = header.index("﻿Time") if "﻿Time" in header else header.index("Time")
    ts = []
    for line in rows:
        parts = line.split(",")
        try:
            ts.append(datetime.strptime(parts[tidx][:15], "%Y%m%d_%H%M%S").replace(tzinfo=CEST))
        except (ValueError, IndexError):
            continue
    if not ts:
        return None, None, len(rows)
    return ts[0], ts[-1], len(rows)


def main():
    # --- load survey entries for participants 61-68 ---
    entries = []  # (participant, drive_no, misc_text, misc_score, corrected_time)
    with open(SSQ, encoding="utf-8-sig", errors="replace") as f:
        for row in list(csv.reader(f))[1:]:
            try:
                pid = int(row[1])
            except ValueError:
                continue
            if not (61 <= pid <= 68) or row[2] not in DRIVE_ORDER:
                continue
            t = parse_survey_time(row[0]) - SURVEY_CLOCK_OFFSET
            entries.append(
                dict(
                    participant=pid,
                    drive=DRIVE_ORDER[row[2]],
                    misc_text=row[3],
                    misc=MISC_SCALE.get(row[3], ""),
                    survey_time_corrected=t,
                )
            )
    entries.sort(key=lambda e: e["survey_time_corrected"])

    # --- load all sessions ---
    sessions = []
    for f in sorted(glob.glob(os.path.join(DATA, "*_SimBike.csv"))):
        name = os.path.basename(f)
        m = re.match(r"SimulationData_P(\d+)_(\d{8}_\d{6})_SimBike\.csv", name)
        start, end, n = session_times(f)
        old_schema = False
        with open(f, encoding="utf-8-sig") as fh:
            old_schema = "UnixTimestamp" not in fh.readline()
        sessions.append(
            dict(
                file=name,
                permutation=int(m.group(1)),
                start=start,
                end=end,
                frames=n,
                duration_min=round((end - start).total_seconds() / 60, 2) if start else None,
                old_schema=old_schema,
                participant=None,
                drive=None,
                role=None,
            )
        )
    sessions.sort(key=lambda s: s["start"])

    # --- assign sessions to survey entries ---
    # A session belongs to survey entry E if it STARTED between the previous
    # entry's corrected time (same day) and E's corrected time. Matching on start
    # (not end) is deliberate: the logger keeps recording standstill while the
    # participant dismounts and fills in the survey, so a drive's logged end can
    # fall a few minutes after its own survey entry.
    prev_time_by_day = {}
    for e in entries:
        day = e["survey_time_corrected"].date()
        lower = prev_time_by_day.get(day)
        matched = []
        for s in sessions:
            if s["participant"] is not None or s["start"] is None:
                continue
            if s["start"].date() != day:
                continue
            if s["start"] >= e["survey_time_corrected"]:
                continue
            if lower and s["start"] <= lower:
                continue
            if e["survey_time_corrected"] - s["start"] > MATCH_WINDOW:
                continue
            matched.append(s)
        # Main recording = usable (new-schema) session ending closest to the survey
        # entry; after a restart the last completed run is the real drive.
        usable = [s for s in matched if not s["old_schema"]]
        main_file = (
            min(usable, key=lambda s: abs(e["survey_time_corrected"] - s["end"]))
            if usable
            else None
        )
        for s in matched:
            s["participant"] = e["participant"]
            s["drive"] = e["drive"]
            if s is main_file:
                s["role"] = "main"
            elif s["old_schema"]:
                s["role"] = "old-schema (excluded)"
            else:
                s["role"] = "restart/fragment"
        e["files"] = [s["file"] for s in matched]
        e["main_file"] = main_file["file"] if main_file else ""
        e["gap_min"] = (
            round((e["survey_time_corrected"] - main_file["end"]).total_seconds() / 60, 1)
            if main_file
            else ""
        )
        prev_time_by_day[day] = e["survey_time_corrected"]

    # --- write per-session linkage table ---
    with open(os.path.join(OUT, "linkage_table.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["file", "permutation_id", "start", "end", "duration_min", "frames",
             "old_schema", "participant", "drive", "role"]
        )
        for s in sessions:
            w.writerow(
                [s["file"], s["permutation"],
                 s["start"].strftime("%Y-%m-%d %H:%M:%S") if s["start"] else "",
                 s["end"].strftime("%Y-%m-%d %H:%M:%S") if s["end"] else "",
                 s["duration_min"], s["frames"], s["old_schema"],
                 s["participant"] or "unmatched", s["drive"] or "", s["role"] or ""]
            )

    # --- write per-drive summary ---
    with open(os.path.join(OUT, "drives_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["participant", "drive", "misc_score", "misc_text", "main_file",
             "permutation_id", "duration_min", "n_files", "survey_time_corrected",
             "gap_end_to_survey_min"]
        )
        by_file = {s["file"]: s for s in sessions}
        for e in entries:
            mf = by_file.get(e["main_file"])
            w.writerow(
                [e["participant"], e["drive"], e["misc"], e["misc_text"],
                 e["main_file"],
                 mf["permutation"] if mf else "", mf["duration_min"] if mf else "",
                 len(e["files"]),
                 e["survey_time_corrected"].strftime("%Y-%m-%d %H:%M:%S"), e["gap_min"]]
            )

    # --- console report ---
    print("Per-drive assignments:")
    for e in entries:
        print(
            f"  P{e['participant']} drive {e['drive']}: MISC={e['misc']:>2} "
            f"main={e['main_file'] or 'NO MATCH'} files={len(e['files'])} "
            f"gap={e['gap_min']} min"
        )
    unmatched = [s for s in sessions if s["participant"] is None]
    print(f"\nUnmatched sessions ({len(unmatched)}):")
    for s in unmatched:
        print(
            f"  {s['file']}  {s['start'].strftime('%m-%d %H:%M')}-"
            f"{s['end'].strftime('%H:%M')}  {s['duration_min']} min"
            f"{'  [old schema]' if s['old_schema'] else ''}"
        )


if __name__ == "__main__":
    main()
