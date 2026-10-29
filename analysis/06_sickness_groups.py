"""Iteration 2, step 1: classify each participant's sickness trajectory.

Implements the supervisor's grouping idea: instead of correlating a continuous
sickness score against continuous behaviour, group participants by HOW their
sickness evolved across drives, then compare handlebar behaviour between groups.

Runs on the survey alone, so it covers every participant who answered — not just
the ones with telemetry.

Three grouping schemes are emitted (the analysis uses `traj_group` as primary):

  traj_group   (supervisor's explicit ask, 3 classes)
    improving  delta <= -2   "high sickness to low"
    worsening  delta >= +2   "no sickness to increasing sickness"
    stable     |delta| <= 1
    NOTE: `improving` is nearly empty (n=3 of 44) because simulator sickness
    rarely recedes within a session — the delta distribution is right-skewed.
    Reported, but under-powered for a group test.

  traj2        (2 classes, better balanced — recommended for hypothesis testing)
    escalating      delta >= +1   (n=26)
    non_escalating  delta <= 0    (n=18)

  severity2 / severity3  (based on peak MISC, well balanced)
    severity2: reactive (peak >= 2) vs non_reactive (peak <= 1)
    severity3: none (0-1) / mild (2-5) / nausea (6-10)   -> 16 / 24 / 8

Output: sickness_groups.csv (one row per participant)
"""
import csv
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SSQ = os.path.join(os.path.dirname(HERE), "ssq", "MISC (SSQ) [BikeSim2026].csv")

SURVEY_CLOCK_OFFSET = timedelta(hours=1)  # survey clock runs ahead (Phase 0, Finding 0.4)

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
POST_LABELS = ["After first drive", "After second drive", "After third drive"]
BASELINE = "Before first drive"


def parse_time(s):
    s = re.sub(r"\s+(OESZ|OEZ)$", "", s.strip())
    return datetime.strptime(s, "%Y/%m/%d %I:%M:%S %p") - SURVEY_CLOCK_OFFSET


def classify_traj(scores):
    """scores: list of post-drive MISC in drive order (>=2 values)."""
    delta = scores[-1] - scores[0]
    if delta <= -2:
        return "improving", delta
    if delta >= 2:
        return "worsening", delta
    return "stable", delta


def main():
    # ---- read, keeping every entry with its corrected timestamp ----
    entries = defaultdict(list)  # pid -> [(time, label, score)]
    unmapped = set()
    with open(SSQ, encoding="utf-8-sig", errors="replace") as f:
        for row in list(csv.reader(f))[1:]:
            try:
                pid = int(row[1])
            except (ValueError, IndexError):
                continue
            if row[3] not in MISC_SCALE:
                unmapped.add(row[3])
                continue
            entries[pid].append((parse_time(row[0]), row[2], MISC_SCALE[row[3]]))
    if unmapped:
        print("WARNING unmapped MISC labels:", unmapped)

    rows = []
    for pid in sorted(entries):
        ev = sorted(entries[pid])
        baseline = next((s for _, lab, s in ev if lab == BASELINE), None)
        posts = [(t, lab, s) for t, lab, s in ev if lab in POST_LABELS]

        # Duplicate labels mean a repeated/aborted block (only P60 in this data):
        # keep the LAST contiguous block, i.e. for each label its latest entry,
        # which is the completed run. Documented in METHODS_LOG.
        note = ""
        by_label = {}
        for t, lab, s in posts:
            if lab in by_label:
                note = "duplicate label(s) — kept latest block"
            by_label[lab] = (t, s)
        ordered = [by_label[lab] for lab in POST_LABELS if lab in by_label]
        scores = [s for _, s in ordered]
        n = len(scores)

        rec = dict(
            participant=pid,
            session_date=ev[0][0].strftime("%Y-%m-%d"),
            n_post_ratings=n,
            baseline_misc="" if baseline is None else baseline,
            misc_d1=scores[0] if n >= 1 else "",
            misc_d2=scores[1] if n >= 2 else "",
            misc_d3=scores[2] if n >= 3 else "",
            misc_first=scores[0] if n >= 1 else "",
            misc_last=scores[-1] if n >= 1 else "",
            misc_peak=max(scores) if n >= 1 else "",
            misc_mean=round(sum(scores) / n, 2) if n >= 1 else "",
            note=note,
        )
        if n >= 2:
            grp, delta = classify_traj(scores)
            rec.update(
                traj_group=grp,
                misc_delta=delta,
                traj2="escalating" if delta >= 1 else "non_escalating",
            )
        else:
            rec.update(traj_group="unclassifiable", misc_delta="",
                       traj2="unclassifiable")
        if n >= 1:
            peak = max(scores)
            rec["severity2"] = "reactive" if peak >= 2 else "non_reactive"
            rec["severity3"] = (
                "nausea" if peak >= 6 else "mild" if peak >= 2 else "none"
            )
        else:
            rec["severity2"] = rec["severity3"] = "unclassifiable"
        # dropout = fewer than 3 ratings AND a severe final rating
        rec["dropout"] = int(n < 3 and (max(scores) >= 8 if scores else False))
        rows.append(rec)

    cols = ["participant", "session_date", "n_post_ratings", "baseline_misc",
            "misc_d1", "misc_d2", "misc_d3", "misc_first", "misc_last",
            "misc_peak", "misc_mean", "misc_delta", "traj_group", "traj2",
            "severity2", "severity3", "dropout", "note"]
    out = os.path.join(HERE, "sickness_groups.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ---- report ----
    print(f"{len(rows)} participants classified -> sickness_groups.csv\n")
    print("Trajectory groups (primary scheme):")
    tally = defaultdict(list)
    for r in rows:
        tally[r["traj_group"]].append(r["participant"])
    for g in ["improving", "worsening", "stable", "unclassifiable"]:
        if g in tally:
            ids = tally[g]
            print(f"  {g:16s} n={len(ids):2d}  {ids}")
    print("\nTrajectory 2-class (recommended for testing — better balanced):")
    t2 = defaultdict(int)
    for r in rows:
        t2[r["traj2"]] += 1
    for g in ["escalating", "non_escalating", "unclassifiable"]:
        if g in t2:
            print(f"  {g:16s} n={t2[g]}")
    print("\nSeverity (3-class, by peak MISC):")
    t3 = defaultdict(int)
    for r in rows:
        t3[r["severity3"]] += 1
    for g in ["none", "mild", "nausea", "unclassifiable"]:
        if g in t3:
            print(f"  {g:16s} n={t3[g]}")
    print("\nDropouts (incomplete + severe):",
          [r["participant"] for r in rows if r["dropout"]])
    print("\nParticipants with telemetry available (June 60-68):")
    for r in rows:
        if 60 <= r["participant"] <= 68:
            print(f"  P{r['participant']}  {r['misc_d1']}->{r['misc_d2']}->{r['misc_d3']}"
                  f"  delta={r['misc_delta']}  {r['traj_group']}"
                  + (f"   [{r['note']}]" if r["note"] else ""))


if __name__ == "__main__":
    main()
