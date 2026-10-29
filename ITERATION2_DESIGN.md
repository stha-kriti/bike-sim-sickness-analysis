# Iteration 2 — Analysis Design & Answers to Supervisor's Questions

> **Status (2026-08-04):** design sections Q2–Q6 are current; the results section
> at the bottom was rewritten after the full archive arrived and now reflects the
> final analysis (including the mixed-effects model). Historical audit trail of
> how the findings evolved: `analysis/METHODS_LOG.md` § ITERATION 3. Section 0
> below (the data-availability blocker) is retained for the record but **resolved**.

Status: pipeline built and run on all available data (2026-08-03).
Scripts `06`–`09` in `analysis/`; results in `sickness_groups.csv`,
`handlebar_drives.csv`, `handlebar_participants.csv`, `group_stats.csv`.

---

## 0. The blocker, stated first

**The survey covers 50 participants. The telemetry covers 9.**

| | participants | who |
|---|---|---|
| MISC survey answered | 50 (48 with ≥1 post-drive rating) | IDs 1–41 (Feb–Mar) and 60–68 (June) |
| Classifiable trajectory (≥2 ratings) | **44** | ← this is the supervisor's "45" |
| **Simulator telemetry present** | **9** | **60–68 only (June 22–26)** |

`data june/` contains files for five days only: 22–26 June 2026. The Feb–March
sessions for participants 1–41 are **not in this folder and not anywhere on this
machine** (checked). So the handlebar analysis currently runs on 9 participants,
not 45.

**Action needed:** request the simulator log archive for the Feb–March sessions
(participants 1–41). Everything below is written so that the same scripts produce
the 45-participant result the moment those files are dropped into `data june/` —
no code changes, only a re-run.

One gain already banked: iteration 1 followed the brief's "participants 61–68" and
discarded three sessions as unmatched. They belong to **participant 60**, recovered
in this iteration → **9 participants, 25 analysable drives** (was 8 and 22), and
P60 is the *only* "high sickness → low" case with telemetry.

---

## Q2 — "What is your idea to link the driving behaviour data with the motion sickness data?"

Two separate linkage problems; both solved.

**(a) Record linkage — which telemetry file belongs to which participant.**
No file or column carries a participant ID (the `P###` in filenames is the
scenario/PermutationId). The link is reconstructed from timestamps:

1. The survey clock runs **1 hour ahead** of the simulator clock (established
   empirically, constant across all five days).
2. A session belongs to drive *N* of the participant whose survey entry *N* it
   precedes — matched on session **start** time, bounded below by survey entry
   *N−1*, same day. Start (not end) because the logger keeps recording the
   stationary bike while the rider dismounts to answer the survey, so a drive's
   logged *end* can fall minutes **after** its own rating.

**Validation without lab notes:** the matcher never sees scenario numbers, yet the
recovered scenario IDs come out as perfectly consecutive triples per participant —
P60→177/178/179, P61→180/181/182, … P68→201/202/203. Two independent orderings
agree. With P60 added there are now **zero unmatched sessions**.

**(b) Analysis linkage — how behaviour is related to sickness.**
Per the supervisor's plan, not a continuous per-frame correlation but:
per-drive handlebar metrics → averaged per participant → compared **between
sickness groups**, with within-participant change as a secondary analysis.

---

## Q3 — "What exactly do you want to get from the handlebar rotation?"

**The rider's steering input, isolated from where the route makes them point.**

This is the single most important definitional point in the iteration. The logs
give `HandlebarYaw` **and** `BikeYaw` as *absolute world headings*. `HandlebarYaw`
on its own sweeps through the full 360° on every corner — it mostly measures the
route, not the rider. The steering input is the **difference**:

```
steer_deflection = wrap180(HandlebarYaw − BikeYaw)
```

0° = bars aligned with the frame (straight ahead); ± = steering right/left
*relative to travel*. This quantity is route-independent, which is what makes it
comparable across participants who rode different scenarios.

**What we want from it, conceptually:** the magnitude and restlessness of
involuntary steering corrections — a behavioural proxy for degraded postural and
motor control, which is the mechanism by which simulator sickness would plausibly
show up in riding. A rider feeling unwell is expected to make larger and/or more
frequent corrections than a settled rider.

All metrics are computed on **moving frames only** (speed ≥ 0.5 m/s) — handlebar
wiggle while parked is not riding behaviour — and derivatives use real timestamps
(logging is ~32 Hz with jitter, not the documented 20 Hz).

---

## Q4 — "Average angle, or changing speed of the driving behaviour?"

**Both were computed. Recommendation: deviation (SD) as primary.** They agree, so
the choice is not load-bearing.

| Metric | Meaning | vs peak MISC (n=9) |
|---|---|---|
| `steer_sd_deg` | **deviation of rotation (SD)** — primary | ρ = **+0.61** |
| `steer_absmean_deg` | average rotation angle (mean abs) | ρ = **+0.71** |
| `steer_p95_abs_deg` | large corrections (95th pct) | ρ = +0.62 |
| `steer_iqr_deg` | typical spread | ρ = +0.59 |
| `steerrate_absmean_dps` | **changing speed** (mean abs rate) | ρ = +0.56 |
| `steerrate_sd_dps` | rate variability | ρ = +0.62 |
| `steer_reversals_per_min` | correction frequency | ρ = +0.59 |
| `steer_jerk_rms_dps2` | jerkiness | ρ = +0.69 |

**All eight point the same direction** (+0.56 to +0.71). That consistency is
itself the result: whichever way handlebar restlessness is quantified, more
restlessness goes with more sickness. Deviation (SD) is recommended as the
headline because it is the supervisor's stated preference, is the most standard
measure in the driving-behaviour literature, and does not depend on a threshold
or deadband choice the way reversal rate does.

---

## Q5 — "Link speed with the questionnaire, or handlebar rotation with the questionnaire?"

**Primary: handlebar rotation ↔ questionnaire.** That is the design below.

But one honest finding has to be reported, because it is the strongest single
correlation in the data:

> **Mean speed vs peak MISC: ρ = −0.73 (p = 0.026, n = 9).**
> Sicker participants rode *slower*.

This does not contradict the instruction to drop speed. What iteration 1 tested
and found useless was speed *variability* and absolute speed **pooled per drive**
(ρ ≈ 0.1). Mean speed **per participant** was never tested, and it is informative —
plausibly because feeling unwell makes riders slow down, a self-regulation effect.

Recommended handling — and this is the defensible position:

1. **Handlebar deviation is the primary hypothesis** (mechanistic: motor control).
2. **Speed is a control variable, not a competitor.** Handlebar deviation and
   speed share variance (ρ = −0.38), so the handlebar result is reported both raw
   and speed-adjusted: partial ρ (controlling mean speed) = **+0.52** for
   deviation, **+0.58** for mean angle. The handlebar signal survives.
3. **Report the speed finding as a secondary result** rather than hiding it.
   Suppressing the strongest correlate would be a defect in the write-up.

---

## Q6 / the analysis design (supervisor's plan, implemented)

### Step 1 — Group participants by how sickness evolved (`06_sickness_groups.py`)

Runs on the survey alone → covers **all 50 participants now**, independent of the
telemetry gap. Three schemes are emitted:

| Scheme | Classes | n (of 44 classifiable) |
|---|---|---|
| `traj_group` (supervisor's) | improving (Δ≤−2) / stable (\|Δ\|≤1) / worsening (Δ≥+2) | **3 / 26 / 15** |
| `traj2` (recommended) | escalating (Δ≥+1) / non-escalating (Δ≤0) | **26 / 18** |
| `severity3` | none (peak 0–1) / mild (2–5) / nausea (6–10) | **16 / 24 / 8** |

**A design problem found, and the fix.** The supervisor's category (a),
"high sickness → low", contains only **3 of 44 participants**. Simulator sickness
essentially does not recede within a session — the Δ distribution is strongly
right-skewed (−6 ×1, −2 ×2, −1 ×2, 0 ×13, +1 ×11, ≥+2 ×15). A three-group test
with n=3 in one arm cannot work even with the full archive.

Recommendation: **keep `traj_group` as descriptive reporting** (it tells the
adaptation-vs-sensitisation story) but run hypothesis tests on `traj2`
(26 vs 18) and `severity3` (16/24/8), which are properly balanced. Both are
already implemented.

### Step 2 — Quantify handlebar movement (`08_handlebar_features.py`)
Per drive and per participant, the eight metrics in Q4.

### Step 3 — Group comparison and correlation (`09_group_stats.py`)
- Mann–Whitney + rank-biserial effect size, escalating vs non-escalating
- Kruskal–Wallis across severity3
- Spearman vs peak / mean / Δ MISC
- Within-participant Δmetric vs ΔMISC
- Practice-effect confounder check

---

## Results — final, after the full archive arrived
*(This section replaces the original "what the pilot on 9 participants shows",
which reported effects that later reversed. Full audit trail:
`analysis/METHODS_LOG.md` § ITERATION 3, findings I3.1–I3.11.)*

### What the pilot claimed, and what happened to it
The 9-participant pilot showed all eight handlebar metrics higher in the
escalating group (rank-biserial +0.38 … +0.75) and correlations of +0.56 … +0.71
with peak MISC. **At full N (48 participants, 133 drives) none of this survived:**

1. **The group effect reversed sign** — escalating vs non-escalating rank-biserial
   is −0.05 … −0.40 in the Feb–March cohort (22 v 14). A 4-vs-4 comparison cannot
   support such a claim; it was a small-sample artifact (figure `w2`).
2. **The level correlations were a cohort artifact.** The two archives differ in
   protocol (drives ~400 s vs ~167 s) and in sickness (peak MISC median 2 vs 6),
   so pooling manufactured correlation. Within-cohort, and under matched-exposure
   windows, handlebar *level* vs sickness is ≈ 0 (figures `w1`, `w5`).
3. **The speed finding was downgraded for the same reason** (−0.38 full-drive →
   ≈ −0.14 exposure-matched).

### What replaced it — the signal is a within-drive change
Matched 80 s windows (early / mid / late) inside each drive, Feb–March cohort
where exposure is constant: the early window carries **no** sickness information
(all 8 metrics ≈ 0), while mid/late reach ρ ≈ +0.2 … +0.3 (figure `w3`). Motion
sickness accumulates; behaviour reflects it only once it has built up.

The corresponding per-drive quantity — **change in steering amplitude, last 80 s
minus first 80 s** — was taken to a pre-specified mixed-effects model
(drive nested in participant; drive number + cohort as covariates; primary
endpoint Δ steering IQR declared in advance):

- **Primary test: β = +0.57 MISC points per SD of within-rider change,
  95 % CI [+0.26, +0.88], p = 0.0004**; holds with a random slope (p = .021).
- **ICC = 0.69** — 69 % of all MISC variance is stable individual susceptibility.
- **Accumulation: +0.48 MISC per drive** (p = .0005); June cohort +2.9 MISC.
- **Sensitivity checks temper the claim:** the effect does not appear when MISC
  is dichotomised at the mild end (GEE OR 1.17–1.34, n.s.) and attenuates in the
  Feb–March-only refit (β = +0.23, p = .28) — partly genuine range restriction
  (13/39 Feb–March riders gave identical ratings after all three drives and so
  cannot contribute to a within-rider estimate).

**Defensible summary sentence:** in the pre-specified mixed model, within-rider
increases in steering amplitude over a drive predicted the post-drive rating
(β = +0.57 per SD, p < .001), robust to a random-slope check but attenuated when
MISC was dichotomised and in the cohort with compressed sickness range; the
effect is carried largely by riders whose sickness actually varied between
drives. Supported, not established.

### Standing methodological conclusions
- The practice effect is real (behaviour smooths across drives) and is handled as
  a covariate, no longer by subgroup reporting.
- Route geometry remains ruled out as a confound (two route families; neither
  affects the metrics nor correlates with sickness).
- **Design recommendation for the lab:** the within-person question is starved of
  data — 69 % of rating variance is frozen susceptibility and a third of riders
  never change their rating. Future studies need sickness that *moves*: longer or
  more provocative drives, susceptible participants, or mid-drive ratings.

---

## Open questions for the supervisor (updated)

1. ~~Can the Feb–March telemetry archive be provided?~~ **Resolved** — supplied in
   `new data/`, fully integrated and audited.
2. ~~Is `traj2` an acceptable substitute for the 3-class scheme?~~ **Moot** — all
   group schemes are null at full N; the analysis moved to within-drive change.
3. **Were the Feb–March and June protocols intentionally different** (~400 s vs
   ~167 s drives)? This determines whether pooled analyses are ever valid and how
   the cohort term should be interpreted.
4. **Pre-drive baseline:** 41 Feb–March participants have one (P24 = 5, P34 = 4,
   P25 = 3, P30 = 2 arrived unwell). Should baseline enter the mixed model as a
   covariate for the Feb–March cohort, accepting it is missing for June?
5. **P60's duplicate "After first drive"** is treated as a practice/aborted run
   (completed block 8→6→2 used). Confirm.
6. **Mid-drive MISC ratings in future protocols** would directly unblock the
   within-drive question — worth raising as the study's main design lesson.
