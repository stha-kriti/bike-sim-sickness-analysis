"""Iteration 2, step 2: participant-agnostic linkage.

Differences from 01_build_linkage.py (iteration 1):
  * No hard-coded participant range — every surveyed participant is considered,
    so P60 is recovered (iteration 1 followed the brief's "61-68" and discarded
    three real sessions: scenarios 177/178/179).
  * Handles duplicate survey labels: post-drive entries are ordered
    chronologically per participant; when there are more than three, the EARLIEST
    extras are labelled practice/aborted runs (drive 0) and the last three become
    drives 1-3. Only P60 needs this.
  * Reports which surveyed participants have no telemetry at all, so the coverage
    gap is explicit rather than silent.

Matching rule is unchanged and still validated by scenario-ID continuity:
a session belongs to drive N if it STARTED between survey entry N-1 and N, same
day (survey clock corrected by -1 h). See METHODS_LOG Phase 1.

Outputs: linkage_v2.csv (per session file), drives_v2.csv (per participant-drive).
"""
import csv
import glob
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data june")
SSQ = os.path.join(os.path.dirname(HERE), "ssq", "MISC (SSQ) [BikeSim2026].csv")

CEST = timezone(timedelta(hours=2))
SURVEY_CLOCK_OFFSET = timedelta(hours=1)
MATCH_WINDOW = timedelta(hours=2)

MISC_SCALE = {
    "Nothing": 0, "Uneasiness": 1,
    "Dizziness, warmth, headache, stomach awareness, sweating - vague": 2,
    "Dizziness, warmth, headache, stomach awareness, sweating - slight": 3,
    "Dizziness, warmth, headache, stomach awareness, sweating - fairly": 4,
    "Dizziness, warmth, headache, stomach awareness, sweating - severe": 5,
    "Nausea - slight": 6, "Nausea - fairly": 7, "Nausea - severe": 8,
    "Nausea - (near) retching": 9, "Vomiting": 10,
}
POST_LABELS = {"After first drive", "After second drive", "After third drive"}


def parse_survey_time(s):
    s = re.sub(r"\s+(OESZ|OEZ)$", "", s.strip())
    return datetime.strptime(s, "%Y/%m/%d %I:%M:%S %p").replace(tzinfo=CEST) \
        - SURVEY_CLOCK_OFFSET


def session_times(path):
    """(start, end, n_rows, old_schema) tolerating malformed rows."""
    with open(path, encoding="utf-8-sig") as f:
        header = f.readline().strip().lstrip("﻿").split(",")
        lines = f.readlines()
    old = "UnixTimestamp" not in header
    if not old:
        i = header.index("UnixTimestamp")
        ts = []
        for ln in lines:
            p = ln.split(",")
            try:
                ts.append(datetime.fromtimestamp(int(p[i]) / 1000, tz=CEST))
            except (ValueError, IndexError):
                continue
    else:
        i = header.index("Time")
        ts = []
        for ln in lines:
            p = ln.split(",")
            try:
                ts.append(datetime.strptime(p[i][:15], "%Y%m%d_%H%M%S")
                          .replace(tzinfo=CEST))
            except (ValueError, IndexError):
                continue
    if not ts:
        return None, None, len(lines), old
    return ts[0], ts[-1], len(lines), old


def main():
    # ---- survey entries, all participants, duplicates resolved ----
    per_p = defaultdict(list)
    with open(SSQ, encoding="utf-8-sig", errors="replace") as f:
        for row in list(csv.reader(f))[1:]:
            try:
                pid = int(row[1])
            except (ValueError, IndexError):
                continue
            if row[2] not in POST_LABELS or row[3] not in MISC_SCALE:
                continue
            per_p[pid].append((parse_survey_time(row[0]), MISC_SCALE[row[3]], row[3]))

    entries = []
    for pid, evs in per_p.items():
        evs.sort()
        # more than 3 post-drive ratings => earliest extras are practice/aborted
        extra = len(evs) - 3
        for k, (t, score, text) in enumerate(evs):
            drive = k - extra + 1 if extra > 0 else k + 1
            entries.append(dict(participant=pid, drive=drive, misc=score,
                                misc_text=text, t=t,
                                practice=int(drive <= 0)))
    entries.sort(key=lambda e: e["t"])

    # ---- sessions ----
    sessions = []
    for path in sorted(glob.glob(os.path.join(DATA, "*_SimBike.csv"))):
        name = os.path.basename(path)
        m = re.match(r"SimulationData_P(\d+)_(\d{8}_\d{6})_SimBike\.csv", name)
        start, end, n, old = session_times(path)
        sessions.append(dict(file=name, permutation=int(m.group(1)), start=start,
                             end=end, frames=n, old_schema=old,
                             duration_min=round((end - start).total_seconds() / 60, 2)
                             if start else None,
                             participant=None, drive=None, role=None))
    sessions.sort(key=lambda s: (s["start"] is None, s["start"]))

    # ---- assign ----
    prev_by_day = {}
    for e in entries:
        day = e["t"].date()
        lower = prev_by_day.get(day)
        matched = []
        for s in sessions:
            if s["participant"] is not None or s["start"] is None:
                continue
            if s["start"].date() != day or s["start"] >= e["t"]:
                continue
            if lower and s["start"] <= lower:
                continue
            if e["t"] - s["start"] > MATCH_WINDOW:
                continue
            matched.append(s)
        usable = [s for s in matched if not s["old_schema"]]
        main_file = min(usable, key=lambda s: abs(e["t"] - s["end"])) if usable else None
        for s in matched:
            s["participant"] = e["participant"]
            s["drive"] = e["drive"]
            s["role"] = ("main" if s is main_file
                         else "old-schema (excluded)" if s["old_schema"]
                         else "restart/fragment")
        e["files"] = [s["file"] for s in matched]
        e["main"] = main_file
        prev_by_day[day] = e["t"]

    # ---- write per-session ----
    with open(os.path.join(HERE, "linkage_v2.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "permutation_id", "start", "end", "duration_min",
                    "frames", "old_schema", "participant", "drive", "role"])
        for s in sessions:
            w.writerow([s["file"], s["permutation"],
                        s["start"].strftime("%Y-%m-%d %H:%M:%S") if s["start"] else "",
                        s["end"].strftime("%Y-%m-%d %H:%M:%S") if s["end"] else "",
                        s["duration_min"], s["frames"], s["old_schema"],
                        s["participant"] or "unmatched", s["drive"] or "",
                        s["role"] or ""])

    # ---- write per-drive (only drives that have telemetry) ----
    linked = [e for e in entries if e["main"] is not None]
    with open(os.path.join(HERE, "drives_v2.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["participant", "drive", "practice", "misc_score", "misc_text",
                    "main_file", "permutation_id", "duration_min", "n_files",
                    "survey_time_corrected", "gap_end_to_survey_min"])
        for e in linked:
            mf = e["main"]
            w.writerow([e["participant"], e["drive"], e["practice"], e["misc"],
                        e["misc_text"], mf["file"], mf["permutation"],
                        mf["duration_min"], len(e["files"]),
                        e["t"].strftime("%Y-%m-%d %H:%M:%S"),
                        round((e["t"] - mf["end"]).total_seconds() / 60, 1)])

    # ---- report ----
    print("Linked drives (telemetry available):")
    cur = None
    for e in linked:
        if e["participant"] != cur:
            cur = e["participant"]
            print(f"  P{cur}:")
        tag = "  [PRACTICE/ABORTED]" if e["practice"] else ""
        print(f"     drive {e['drive']}: MISC={e['misc']:>2} "
              f"scenario={e['main']['permutation']} "
              f"files={len(e['files'])} gap={round((e['t']-e['main']['end']).total_seconds()/60,1)}min{tag}")

    with_tel = sorted({e["participant"] for e in linked})
    all_surveyed = sorted(per_p)
    without = [p for p in all_surveyed if p not in with_tel]
    print(f"\nParticipants surveyed: {len(all_surveyed)}")
    print(f"Participants WITH telemetry: {len(with_tel)} -> {with_tel}")
    print(f"Participants WITHOUT telemetry: {len(without)}")
    print(f"  {without}")
    unmatched = [s for s in sessions if s["participant"] is None]
    print(f"\nUnmatched sessions: {len(unmatched)}")
    for s in unmatched:
        print(f"  {s['file']} {s['start'].strftime('%m-%d %H:%M') if s['start'] else '?'}"
              f"{'  [old schema]' if s['old_schema'] else ''}")
    n_analysable = sum(1 for e in linked if not e["practice"])
    print(f"\nAnalysable drives (excluding practice): {n_analysable}")


if __name__ == "__main__":
    main()
