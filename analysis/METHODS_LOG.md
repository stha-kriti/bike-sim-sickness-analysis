# Methods & Decisions Log — Bike Simulator Sickness Study

Parallel documentation of every finding, decision, and method, maintained alongside
the analysis. Source material for the final report and presentation slides.
Companion to `ANALYSIS_PLAN.md` (the plan) — this file records what was actually
done and why.

---

## Phase 0 — Preliminary data exploration (2026-07-23)

### Inventory
| Source | Content |
|---|---|
| `data june/` | 38 drive sessions × up to 3 files each (`SimBike`, `DynamicObjects`, `StaticObjects`), June 22–26, 2026, logged at 20 Hz |
| `ssq/MISC (SSQ) [BikeSim2026].csv` | MISC sickness survey, 176 entries, 68 participants; **only participants 61–68 are in scope** |
| Parent-study thesis (not included) | Reference only (column semantics, HMI state machine) |
| Course problem statement (not included) | Task description + column definitions |

### Finding 0.1 — Filename `P###` is the scenario, not the participant
The number in `SimulationData_P###_...` is the **PermutationId** (scenario/drive
configuration, values 177–203), confirmed by the `PermutationId` column inside the
files. No file or column carries the participant number → linkage to the survey
must be reconstructed (see Phase 1).

### Finding 0.2 — MISC scale mapping
The survey stores the Misery Scale (MISC) as text labels. Mapping to the standard
0–10 scale:

| Label | Score |
|---|---|
| Nothing | 0 |
| Uneasiness | 1 |
| Dizziness, warmth, headache, stomach awareness, sweating — vague / slight / fairly / severe | 2 / 3 / 4 / 5 |
| Nausea — slight / fairly / severe | 6 / 7 / 8 |
| Nausea — (near) retching | 9 |
| Vomiting | 10 |

Asked after each of 3 drives per participant. **No pre-drive baseline exists for
participants 61–68** (earlier participants had "Before first drive" entries).

### Finding 0.3 — Two file schemas
35 sessions use the full schema (22 columns incl. `UnixTimestamp`, `Vel*`,
`ForwardVel`, `PermutationId`, HMI states). **Three files use an older 11-column
schema** without timestamps in epoch form, velocities, or scenario ID:
`P183_20260623_152733`, `P183_20260623_153752`, `P184_20260623_155359`.
Their time ranges overlap other recordings → they came from a parallel/misconfigured
logger. **Decision: excluded from analysis** (no `ForwardVel`, unreliable provenance).

### Finding 0.4 — Clock relationships
- `UnixTimestamp` (epoch ms, UTC) ↔ `Time` column and filenames are local CEST (UTC+2). Verified: epoch 1782136284315 = 13:51:24 UTC = 15:51:24 CEST = filename `155123`.
- **The survey clock runs ~1 h ahead of the simulator clock** (survey tool timezone
  misconfiguration). Established empirically: without correction, survey entries
  trail drive ends by 15–60 min; after subtracting 1 h, 21 of 22 drives align within
  ±4 min. Applied as a constant −1 h correction to all survey timestamps.

### Finding 0.5 — Other data-quality issues (handled in Phases 1–2)
- Some files end in a truncated final row (logging cut mid-write).
- Several drives produced multiple files (restarts), incl. fragments of 0.3–0.5 min.
- `ForwardVel` is hardware-capped at 7.5 m/s (known limitation per thesis §5.1.1);
  small negative values (≈ −0.13) occur at standstill.
- Yaw angles wrap at 0°/360° → must be unwrapped before differentiating.
- The logger keeps recording the stationary bike after the ride ends (and before it
  starts) → standstill padding at both ends of every file.

### Finding 0.6 — Outcome spread across participants (from survey alone)
P61: 4→4→4 · P62: 2→6→10 (vomited drive 3) · P63: 3→5→5 · P64: 0→0→3 ·
P65: 6→0→6 · **P66: 10 after drive 1, dropped out (only dropout)** ·
P67: 1→0→0 (adapted) · P68: 8→8→9.
Consequence: with n = 8 participants, 22 drive–MISC pairs, and one dropout, the
study is **correlational/exploratory**; dropout prediction is a case study (P66),
not a statistical claim. Research question adjusted accordingly (user-confirmed).

### Scope decisions (user-confirmed 2026-07-23/24)
1. No lab notes exist — the timestamp linkage must stand on its own.
2. RQ reframed to correlational (see ANALYSIS_PLAN.md RQ1–RQ4).
3. Video/OpenFace data out of scope; telemetry (`SimBike.csv`) only.
4. `DynamicObjects`/`StaticObjects` files not needed for these RQs.

---

## Phase 1 — Participant ↔ drive ↔ MISC linkage (2026-07-23)

**Script:** `01_build_linkage.py` → `linkage_table.csv` (per file),
`drives_summary.csv` (per drive, 22 rows).

### Method (final, after two failed iterations)
A session belongs to participant X's drive N if the session **started** between
survey entry N−1 and survey entry N (both corrected by −1 h), on the same day.
Among multiple files in one drive slot (restarts), the **main recording** is the
new-schema file whose end is closest to the survey time; others are flagged
`restart/fragment`. Old-schema files can never be the main recording.

### Why start-time matching (the end-time discrepancy and its mitigation)
The intuitive rule "drive ends shortly before its survey entry" fails: the logger
records the stationary bike while the participant dismounts and fills in the
survey, so a drive's logged end can fall a few minutes **after** its own survey
entry (e.g., P61 drives 1 and 3: −3.0 and −1.2 min). Two greedy end-time matchers
were tried and rejected:
1. *End before survey, 2-min tolerance* → P61 drive 1 matched a session 39 min old.
2. *End before survey + 5 min* → drive N stole drive N+1's session (P68 chain-shifted,
   drive 3 unmatched).
Session **start** times are immune to the trailing standstill (logging starts with
the scenario), and bounding by the previous survey entry enforces monotonic order.
With this rule all 22 drives match; end-time plays no role in assignment.

### Mitigation summary for the end-time discrepancy
1. Constant −1 h survey-clock correction, calibrated empirically (Finding 0.4).
2. Assignment by session start bounded by consecutive survey entries — never by end.
3. Audit column `gap_end_to_survey_min` in `drives_summary.csv` (range −4.1 to
   +7.0 min, mostly 0.5–3) so any mismatch or clock drift is visible.
4. Phase 2 trims the standstill padding itself, so no downstream quantity depends
   on the logged end time.

### Validation
The matcher used only timestamps, yet the matched scenario IDs form perfectly
consecutive triples per participant: P61=180/181/182, P62=183/184/185,
P63=186/187/188, P64=189/190/191, P65=192/193/194, P66=195, P67=198/199/200,
P68=201/202/203. Scenario numbering and timestamps agree independently → strong
confirmation. (196–197 unused, consistent with P66 quitting early.)

### Exclusions and flags
- `P177_174107`, `P178_175430`, `P179_180033` (evening 06-22): match no surveyed
  participant (likely pilot or participant ≤ 60) → excluded.
- `P177_155123` (06-22, 15 min): falls in P61's drive-1 window but scenario 177
  doesn't fit P61's 180–182 run → kept only as non-main fragment.
- `P195_20260624_173926`: falls in P65's drive-1 window but carries P66's scenario
  (195) — likely setup/test → non-main fragment, no effect on analysis.
- Three old-schema files (Finding 0.3): excluded.

### Known limitation
Linkage rests on within-day ordering; robust to minutes of clock error, but could
not separate two surveyed participants riding interleaved within the same hour.
This does not occur in this dataset (each day's surveyed drives form clean,
non-overlapping blocks).

---

## Phase 2 — Cleaning (2026-07-24) ✅

**Script:** `02_clean_data.py` → `cleaned/P<participant>_drive<N>.csv` (22 files),
`cleaning_report.csv` (per-drive audit of every row dropped / second trimmed).

### Steps applied per drive (main recording only)
1. Numeric coercion; rows with unparseable essential fields dropped.
   **Result: 0 malformed rows** in the 22 main files (the truncated rows seen in
   Phase 0 were all in excluded old-schema files).
2. Standstill trimming: keep from the first to the last moment of *sustained*
   riding (|ForwardVel| > 0.5 m/s continuously for ≥ 1 s). Only leading/trailing
   standstill is removed — **mid-drive stops (e.g., waiting at a red bus-stop
   light) are preserved** since they are scenario behavior, not padding.
   Total trimmed: 1244 s across 22 drives; extremes: P61 drive 1 had 478 s
   (~8 min) of post-ride standstill — direct evidence for the end-time
   discrepancy handled in Phase 1; P68 drive 1 had 93 s of pre-ride idle.
3. Yaw unwrapping (`BikeYaw`, `HandlebarYaw`) across the 0°/360° boundary.
4. Derived columns: `t_s` (elapsed riding time), `steer_deflection_deg`
   = wrap±180(HandlebarYaw − BikeYaw), `accel_ms2`, `yaw_rate_dps`,
   `steer_rate_dps` (gradients over actual timestamps, not nominal rate),
   `speed_smooth_ms` / `accel_smooth_ms2` (see Finding 2.3).

### Finding 2.1 — Actual sampling rate is ~32 Hz, not the documented 20 Hz
Median frame interval is 0.028–0.033 s across all drives (docx says 20 Hz).
Sampling also jitters (p99 ≈ 0.13 s; occasional gaps up to ~0.14 s, 2–15 per
drive). **Decision:** all derivatives are computed against actual `UnixTimestamp`
differences, never an assumed rate; report should cite ~32 Hz.

### Finding 2.2 — Speed cap confirmed
Max speed is 7.53–7.56 m/s in every drive — the 7.5 m/s hardware cap from the
thesis. Mean riding speeds 4.4–7.4 m/s. Implication: high-speed behavior is
censored at the cap; speed *variability* remains informative, absolute maxima
are not.

### Finding 2.3 — Extreme deceleration events are real sim events, not errors
8 of 22 drives contain frames with |accel| up to 73 m/s²: speed collapses from
the 7.5 m/s cap over 2–3 frames while heading swings 20–30° in ~0.1 s, then
recovers gradually — the signature of collisions / hard evasive maneuvers in the
simulator physics, not sensor glitches (position stays continuous; no duplicate
or missing timestamps involved). **Decision: kept, not deleted** — erratic-riding
events are potential signal for RQ1. Cleaned files carry both raw `accel_ms2`
(events intact) and `accel_smooth_ms2` (rolling median-5 + mean-5 on speed, then
differentiated) for stable aggregate features; Phase 3 will additionally count
these events explicitly as a feature.

### Finding 2.4 — Route lengths differ by scenario
Ridden distance clusters at ~1000 m, ~1500–1800 m, and ~2500 m; durations
86–428 s. Consequence for Phase 3: features must be rate-/time-normalized
(per minute, per meter) — raw totals would just measure route length.

### Verification
All 22 cleaned files: no NaN/inf, no duplicate timestamps, monotonic time,
speed within [−0.2, 7.56] m/s. Audit trail in `cleaning_report.csv`
(rows_raw → rows_clean, trimmed seconds, gap counts, per drive).

---

## Phase 3 — Feature engineering (2026-07-24) ✅

**Script:** `03_features.py` → `features.csv` (22 rows, one per drive) and
`features_thirds.csv` (66 rows, same features per drive-third, for RQ3).

### Feature definitions (per drive)
| Feature | Definition | Rationale |
|---|---|---|
| `duration_s`, `distance_m` | riding time / path length after trimming | context; routes differ by scenario |
| `speed_mean_ms`, `speed_std_ms`, `speed_cv` | moments of `ForwardVel` | speed variability; CV normalizes for pace |
| `time_at_cap_frac` | fraction of frames > 7.4 m/s | confident, steady riding (max speed itself is censored at the 7.5 cap) |
| `time_stopped_frac`, `n_stops` | fraction < 0.5 m/s; sustained (≥1 s) mid-drive stops | hesitation / interaction with bus-stop HMI |
| `accel_rms_ms2` | RMS of smoothed accel | overall speed-modulation intensity |
| `decel_p05_ms2` | 5th percentile of smoothed accel | typical strong braking, robust to outliers |
| `hard_decel_per_min` | clusters of raw accel < −8 m/s², merged within 0.5 s, per minute | collision/evasive events (Finding 2.3), rate-normalized |
| `steer_std_deg` | std of steering deflection (handlebar − bike heading), riding frames only | steering instability |
| `steer_reversals_per_min` | direction changes of steering movement > 2° deadband, per riding minute | classic steering-reversal-rate workload metric |
| `yaw_rate_std_dps` | std of bike heading rate, riding frames only | path weaving |

Choices: stopped frames are excluded from steering stats (handlebar wiggle at
standstill is not riding behavior); all counts are per-minute
(Finding 2.4 — route lengths differ); hard-decel events counted on **raw**
accel (smoothing attenuates exactly the events being counted); thirds are split
by riding-time terciles of each drive.

### Finding 3.1 — First-look relationships (preview; formal stats in Phase 5)
Pooled Spearman with MISC (n = 22, drives within participant not independent):
steering reversals/min ρ ≈ 0.37, steering std ρ ≈ 0.29, stops ρ ≈ 0.28,
braking p05 ρ ≈ −0.28; speed features near zero. Signals are modest and
**individual differences dominate**: P62 rode erratically while escalating to
vomiting (steer_std 11.1°/10.6° in drives 1–2, ~34–38 reversals/min), but P68
reached MISC 8–9 while riding smoothly and fast (time at cap 88–97 %, zero hard
decels in drives 2–3). Consequence: Phase 5 must emphasize within-participant
change (ΔMISC vs Δfeature), not only pooled correlations; the report should
present the P62-vs-P68 contrast explicitly.

### Finding 3.2 — Habituation visible in behavior
Most participants ride markedly smoother by drive 3 (P61: reversals 15.3→3.1/min;
P63: speed_cv 0.20→0.07; P67: accel RMS 0.96→0.39): a practice effect that
parallels the MISC trajectories of the adapters (P64, P67) and must not be
mistaken for a sickness effect — drive number is a confounder for any pooled
feature–MISC relationship.

---

## Phase 4 — Visualization (2026-07-24) ✅

**Script:** `04_figures.py` → `figures/fig1…fig7` (180 dpi PNG, report/slide-ready).

### Figure set and what each one argues
| Figure | Content | Role in the story |
|---|---|---|
| fig1_misc_trajectories | MISC vs drive, small multiples per participant, severity bands shaded, vomit/dropout marked | headline figure (RQ2): the 8 individual stories |
| fig2_feature_vs_misc | 6 feature-vs-MISC scatters with Spearman ρ, P66 marked | RQ1 evidence: modest positive steering/stops signals |
| fig3_trajectory_maps | same ~1 km route top-down, path colored by speed: P64 drive 2 (MISC 0) vs P65 drive 3 (MISC 6) | intuitive RQ1 contrast: nauseous drive shows slow/stop patches |
| fig4_p62_escalation | P62 speed + steering per drive | the escalation case (2→6→10) |
| fig5_p66_dropout | P66's single drive, speed + steering | the dropout case (RQ4) |
| fig6_features_by_band | boxplots + points by MISC band (none 0–1 / mild 2–5 / nausea 6–10) | RQ1 aggregate: medians rise with band, wide overlap |
| fig7_habituation | feature vs drive, gray per-participant lines + median | the practice-effect confounder (Finding 3.2) |

### Design decisions (dataviz method, validated reference palette, light mode)
- 8 participants are shown as **small multiples, never 8 colored series** (8-series
  categorical fails the all-pairs color validation; identity via panel titles).
- Sequential blue ramp for speed on trajectory maps (light = slow, dark = fast);
  single blue for data marks; orange only as second series (steering vs speed
  panels); **status red reserved for vomit/dropout markers, always with a text
  label** — never as a series color.
- One-axis rule: speed and steering never share a dual-axis plot — separate panels.
- fig3 pair chosen so both drives ride the **same route** (verified visually) —
  speed differences aren't route artifacts.
- Render-and-inspect pass done on all 7 figures; fixed: annotation/trace overlap
  (fig5 → moved into title), arrow-label collisions (fig3 → figure-level caption),
  point clipping at axis edge (fig6 → y margins).

### Observation 4.1 (from fig4/fig5, feeds RQ3 and the report narrative)
P62's drive 3 (ended in vomiting) contains ~9 full stops — far more than their
earlier drives; P66's single drive shows increasingly unstable speed and large
steering excursions in its final third (~t > 180 s). Both are consistent with
behavior degrading as sickness builds — to be tested per-thirds in Phase 5.

---

## Phase 5 — Statistics (2026-07-24) ✅

**Script:** `05_stats.py` → `stats_summary.csv` (46 rows, long format).
All results exploratory: n = 22 drives / 8 participants, multiple features tested,
drives within participant not independent. Exact p-values reported, none survives
any multiple-comparison correction — the report must phrase everything as
"suggestive", never "significant".

### A) Pooled feature ↔ MISC (n = 22)
Strongest: steering reversals/min ρ = +0.37 (p = .09); steering std +0.29,
stops +0.28, strong-braking p05 −0.28 (all p ≈ .20). Speed/accel features ≈ 0.
Drive number itself: ρ = +0.11 (p = .61) — the habituation confounder does not
drive the pooled result.

### B) Within-participant change (14 consecutive-drive transitions) — headline
Δ(mid-drive stops) vs ΔMISC: **ρ = +0.50 (p = .07)** — when a participant stopped
more often than in their own previous drive, their sickness rose; the strongest
relationship in the study and free of stable between-person differences.
Δ(steering reversals) +0.38 (p = .18); others weak. Interpretation: sickness
tracks *deviations from one's own baseline*, consistent with Finding 3.1
(between-person comparisons are dominated by riding style — P62 vs P68).

### C) Within-drive degradation (third 3 − third 1, RQ3)
Steering activity rises over a drive generally (reversals median +3.1/min,
p = .09; steering std +1.1°, p = .08; speed CV falls −0.09, p = .06) but the
rise is **uncorrelated with MISC** (|ρ| ≤ .22) → it reads as drive progression /
route familiarity, not sickness. RQ3 answered negatively: no within-drive
behavioral signature of sickness detectable at this sample size.

### D) P66 dropout case (vs the other 7 first drives)
P66's only drive is behaviorally unremarkable: every feature within z ±0.6 of
the other first drives (largest: hard decels +0.60, accel RMS +0.58). **The
participant who vomited and quit could not have been flagged from telemetry** —
an important honest result for the "predict quitting" half of the original RQ,
and consistent with P68 (severe symptoms, smooth riding).

### Bottom line for the report
1. Suggestive positive association between steering activity / stopping and
   post-drive sickness; strongest within-participant (Δstops ρ = .50).
2. Individual riding style dominates between-person comparisons.
3. No within-drive early-warning signature; dropout not telemetry-predictable
   here. A larger sample and a pre-drive MISC baseline are the concrete
   methodological recommendations.

---

# ITERATION 2 — handlebar-focused group design (2026-08-03)

Triggered by supervisor review: sample too small, refocus from speed onto handlebar
rotation, and use a **group-comparison** design rather than continuous correlation.
Full design rationale and answers to her five questions: `../ITERATION2_DESIGN.md`.

## Finding I2.1 — The data-availability gap (the governing constraint)
Survey covers **50 participants** (IDs 1–41 Feb–Mar, 60–68 June); 44 have a
classifiable trajectory — this is the supervisor's "45". **Telemetry covers only 9**:
`data june/` holds files for 22–26 June only. The Feb–March logs for participants
1–41 are absent from the folder and from this machine (searched). The 45-participant
analysis is therefore **blocked on obtaining that archive**; scripts 06–10 are
written to scale to it with no code change.

## Finding I2.2 — Participant 60 recovered (+1 participant, +3 drives)
Iteration 1 obeyed the brief's "participants 61–68" and discarded three sessions as
unmatched. They are P60's: corrected survey times 17:49/17:58/18:06 vs session ends
17:48/17:56/18:05, and scenarios **177/178/179** — consecutive, and continuing
directly into P61's 180/181/182. Now **9 participants / 25 analysable drives**
(was 8 / 22) and **zero unmatched sessions**. P60 is also the only
"high sickness → low" case with telemetry (8→6→2).
P60 has a 4th, earlier post-drive rating (a duplicate "After first drive", MISC 0,
matching a 15-min session at 15:51): treated as a **practice/aborted run**, flagged
`practice=1` and excluded. Only P60 needs this rule.

## Finding I2.3 — "Handlebar rotation" must be a difference, not a raw angle
`HandlebarYaw` and `BikeYaw` are both absolute world headings, so raw
`HandlebarYaw` mostly encodes route direction (it sweeps 360° per corner). The
rider's input is `wrap180(HandlebarYaw − BikeYaw)`. Every metric is built on this,
which is what makes participants on different scenarios comparable. This answers
the supervisor's question 3 and is the definitional core of the iteration.

## Finding I2.4 — All eight handlebar metrics agree
vs peak MISC (n=9, per participant): mean angle +0.71, jerk +0.69, rate-SD +0.62,
p95 +0.62, **deviation (SD) +0.61**, reversals +0.59, IQR +0.59, rate-mean +0.56.
The choice between "average angle" and "deviation" (question 4) is therefore not
load-bearing; SD is used as headline per supervisor preference and literature norm.
Substantially stronger than iteration 1's speed-based features (ρ ≈ 0.05–0.37).

## Finding I2.5 — Mean speed is the single strongest correlate, and it is negative
**Mean speed vs peak MISC: ρ = −0.73, p = 0.026.** Sicker participants rode slower.
Not a contradiction of "don't focus on speed": iteration 1 tested speed
*variability* pooled per drive (useless, ρ≈0.1); mean speed *per participant* had
never been tested. Decision: handlebar remains the primary hypothesis, speed
becomes a **control variable** and a reported secondary finding. Handlebar survives
adjustment — partial ρ (controlling speed) = **+0.52** (deviation), +0.58 (mean angle).
Suppressing the speed result would be a defect; it is reported.

## Finding I2.6 — The supervisor's 3-group scheme is unbalanced; a 2-group split fixes it
Δ MISC (last − first) is strongly right-skewed: −6×1, −2×2, −1×2, 0×13, +1×11,
+2×7, +3×4, +4×2, +6×1, +8×1. So "high sickness → low" holds only **3 of 44**
participants — simulator sickness rarely recedes within a session. Schemes emitted:
`traj_group` 3/26/15 (descriptive), **`traj2` escalating 26 / non-escalating 18
(recommended for testing)**, `severity3` none 16 / mild 24 / nausea 8.

## Finding I2.7 — Handlebar deviation is a between-person marker, not a within-person tracker
Group medians (drive 1): escalating 7.54° vs non-escalating 4.51°, rank-biserial
+0.75; all 8 metrics favour the hypothesis (+0.38…+0.75). Severity gradient
monotonic: none 3.72° < mild 4.75° < nausea 5.70°. But Δmetric vs ΔMISC across
consecutive drives ≈ 0 (ρ = −0.12, n=16). So it distinguishes *who* gets sick, not
*when* — a genuine change from iteration 1's within-participant framing.
Caveat: `traj2` puts P60 in non-escalating despite peak MISC 8 (they were very sick
then improved), which is why `severity3` gives the cleaner gradient. Trajectory and
severity are different constructs and both should be reported.

## Confounds checked
- **Practice effect — real, significant, must be controlled.** Deviation falls
  d1 5.70° → d2 4.58° → d3 3.96° (ρ = −0.44, p = 0.029). Mitigation: report
  drive-1-only alongside drive-average; use drive number as covariate at full N.
- **Route geometry — ruled out.** No scenario is shared between participants, which
  looked fatal. But routes form two families (~1.2 km short loop, 1.6–3 km long
  loop); family does not affect deviation (5.00° vs 4.15°, p = 0.98), route mix is
  uncorrelated with sickness (ρ = −0.15, p = 0.70), and the deviation–MISC relation
  holds within family (short +0.49, long +0.17).
- **Power.** 4-vs-4 groups: smallest achievable Mann–Whitney p = 0.029. No test
  here can be significant after correction; **effect sizes are the deliverable**.

## Scripts and outputs
| Script | Output |
|---|---|
| `06_sickness_groups.py` | `sickness_groups.csv` — all 50 participants, 3 grouping schemes |
| `07_linkage_v2.py` | `linkage_v2.csv`, `drives_v2.csv` — participant-agnostic, P60 recovered |
| `08_handlebar_features.py` | `handlebar_drives.csv` (25), `handlebar_participants.csv` (9) |
| `09_group_stats.py` | `group_stats.csv` — 108 test results |
| `10_figures_v2.py` | `figures_v2/v1…v6` |

Iteration 1 scripts (`01`–`05`) left untouched so both iterations stay reproducible.

---

# ITERATION 3 — full dataset (2026-08-03, IN PROGRESS)

New archive supplied by the user in `new data/`: 111 folders named
`P<participant>D<drive>`, i.e. **participant identity is explicit** — no timestamp
reconstruction needed. This is the Feb–March archive that iteration 2 identified as
missing. **Total now: 48 participants, 133 drives, 44 usable for group tests.**

## Finding I3.1 — Archive contents and audit (`11_audit_new_data.py`)
39 participants (1–41, minus P24/P34 who never rode — consistent with their having
no post-drive ratings). Each folder holds: `SimulationData_P<scenario>_*_SimBike.csv`,
OpenFace head-pose (`Participant_N_*.csv`: pose_Tx/Ty/Tz, pose_Rx/Ry/Rz), and a
pre-merged `merged_RAW_*` joining the two on UnixTimestamp. **OpenFace data is now
available for 104 folders** — previously ruled out of scope, now trivially usable if
we want a head-movement analysis later.
Schema is mixed: 88 files 22-column, 21 files 19-column (older variant, no HMI state
columns). Only the six columns the handlebar analysis needs are read, so both parse
identically. Sampling 25–37 Hz (median 32.3), consistent with Finding 2.1.

## Finding I3.2 — Data problems found and their resolution
| Problem | Resolution |
|---|---|
| `P2D1` UnixTimestamp destroyed — all 11 100 rows read `1.77126E+12` (Excel round-trip truncated it to 6 sig figs) | **Recovered** by parsing the intact `Time` column (`YYYYMMDD_HHMMSS_mmm`). Only file affected (whole archive scanned). |
| `P32D1` folder empty | Genuine loss. P32 contributes drives 2–3 only. |
| `P39D2` folder empty, but `P39D2_1` / `P39D2_2` exist | Restart variants; kept the one with most moving time (`P39D2_2`), logged. |
| 13 folders where recording date ≠ survey date | Not an error: **P11/P36/P40/P41 had all ratings typed in retrospectively** (every entry within one minute on 2026-03-17); P7's third rating came a month late. MISC *values* remain usable; drive order comes from the folder name. Timestamp linkage would have failed on these — the explicit folder labels make it moot. |

**Pandas 3.0 trap worth remembering:** `pd.to_datetime(...)` may return
`datetime64[ms]`, so `.astype("int64")` yields *milliseconds*, not nanoseconds.
Dividing by 1e9 made every interval 10⁶× too small and silently discarded P2D1.
Fixed by using `(s - s.iloc[0]).dt.total_seconds()`, which is resolution-independent.

## Finding I3.3 — Scenario ID encodes participant and drive; iterations 1–2 fully validated
**`scenario == 3 × (participant − 1) + (drive − 1)`** holds for **107/107** new
folders. Applying the same formula to the June cohort — whose linkage was
reconstructed from *timestamps alone* — matches **25/25**, including the P60
recovery. The two independent methods agree completely, so the iteration-1/2 linkage
is confirmed. (It also means participant/drive could have been read straight off the
scenario ID: `participant = scenario // 3 + 1`, `drive = scenario % 3 + 1`.)

## Finding I3.4 — **The two cohorts must not be naively pooled**
All eight handlebar metrics differ significantly between cohorts (rank-biserial
−0.46 … −0.89, p ≤ 0.035; most p < 0.001), **and so does sickness**
(peak MISC median 2 vs 6, p = 0.002; nausea band 3/39 vs 5/9). Cohort is therefore
correlated with both predictor and outcome — a textbook confound.
Mechanism identified: **the protocols differ.** Feb–Mar drives run ~400 s median,
June ~167 s (2.4×). Drive duration is itself negatively related to every handlebar
metric (ρ = −0.21 … −0.34, p < 0.02): shorter drives ⇒ higher steering deviation.
**Decision: Feb–Mar (n = 39, homogeneous protocol) is the primary sample; June
(n = 9) is treated as a separate, smaller replication sample.** Pooled results are
reported only with cohort partialled out.

## Finding I3.5 — **The iteration-2 pilot did NOT replicate**
| | pilot (June, 4 v 4) | full (Feb–Mar, 22 v 14) |
|---|---|---|
| escalating vs non-escalating, all 8 metrics | rank-biserial **+0.62 … +0.75** (all positive) | **−0.05 … −0.40** (all null or *negative*) |

The group difference reversed sign. It was a small-sample artifact, exactly as the
power note in iteration 2 warned. `severity3` within Feb–Mar is also null
(H = 0.03–2.59, p = 0.27–0.99). The supervisor's 3-class trajectory scheme is null
pooled as well (H = 0.02–0.91). **Conclusion: sickness *group* membership is not
distinguishable from handlebar movement at n = 39.**

## Finding I3.6 — What actually survives
Pooled correlations looked strong (deviation +0.40, mean angle +0.48, IQR +0.50, all
surviving BH-FDR) but roughly half is the cohort effect. Within the primary cohort:

1. **Mean speed is the robust finding — and it replicates in both cohorts.**
   Feb–Mar ρ = −0.38 (p = 0.018), June ρ = −0.73 (p = 0.026), pooled ρ = −0.46
   (p = 0.001), cohort-partialled −0.42, duration-partialled (Feb–Mar) −0.48.
   **Sicker participants ride slower**, consistently across every subsample and
   control. This is the metric the supervisor asked us to de-emphasise.
2. **Steering IQR is the only handlebar metric that holds up**, and weakly:
   Feb–Mar ρ = +0.37 (p = 0.022), surviving duration control (+0.37) and speed
   control (+0.31); pooled cohort-partialled +0.36. Uncorrected — it would not
   survive FDR across eight metrics. Treat as suggestive, not established.
3. **Sickness *level* relates to behaviour; sickness *change* does not.**
   All Δ-metric vs ΔMISC correlations ≈ 0 to slightly negative, at both n = 9 and
   n = 44. Consistent across iterations.

## Scripts added
| Script | Output |
|---|---|
| `11_audit_new_data.py` | `new_data_audit.csv` — per-folder health, 111 folders |
| `12_handlebar_all.py` | `handlebar_drives_all.csv` (133), `handlebar_participants_all.csv` (48) |
| `13_group_stats_all.py` | `group_stats_all.csv` — full-N tests incl. cohort check + BH-FDR |

## Finding I3.7 — Exposure normalisation does NOT rescue pooling, and it kills both findings (`14_normalised_metrics.py`)
Recomputed every metric over matched windows: `t80` (first 80 s — keeps all 133
drives / 48 participants), `t120` (131 drives), `d500` (first 500 m).

**(a) The cohort difference is not an exposure artifact.** Under every
normalisation 7 of 8 metrics still differ significantly between cohorts
(mean |rank-biserial| 0.57 t120 / 0.57 t80 / 0.61 d500 vs 0.70 full). Only
steering IQR becomes non-significant. So the cohorts genuinely steered
differently — different equipment generation / protocol, not just unequal exposure.
Pooling remains unsafe; report cohort-partialled or Feb-Mar-primary.

**(b) Both headline findings from I3.6 collapse under normalisation.**

| within Feb-Mar, vs peak MISC | full | t80 | t120 | d500 |
|---|---|---|---|---|
| steering IQR | **+0.37*** | +0.05 | −0.12 | +0.02 |
| deviation (SD) | +0.16 | −0.06 | −0.08 | −0.07 |
| mean speed | **−0.38*** | −0.14 | −0.12 | −0.15 |

All 8 handlebar metrics fall to −0.14…+0.13 within cohort. The `traj2` group test
under `t120` is null (rank-biserial −0.21…+0.03). **The speed finding of I3.6 is
therefore also largely an exposure/cohort effect and must be downgraded.**

## Finding I3.8 — **The signal is in the within-drive CHANGE, not the level** (`15_early_vs_late.py`)
I3.7(b) had two rival explanations — (A) the full-drive effects were exposure
artifacts, or (B) sickness *accumulates*, so the first 80 s precedes symptom onset
and is the wrong window. Decisive test: three disjoint **80 s** windows per drive
(early / mid / late) **within Feb-Mar only**, where durations are already matched
(262–525 s) so exposure is constant and window length is identical by construction.
131 drives qualified (108 Feb-Mar, 23 June; two June drives too short).

**Result: (B) — timing.** Same window length, opposite outcome by position:

| Feb-Mar, per drive, vs that drive's MISC | early80 | mid80 | late80 |
|---|---|---|---|
| deviation (SD) | −0.12 | **+0.24*** | **+0.21*** |
| average angle | −0.07 | **+0.22*** | **+0.25*** |
| steering IQR | −0.02 | −0.02 | **+0.24*** |
| correction frequency | +0.03 | **+0.29*** | **+0.20*** |

Early-window metrics carry **no** sickness information (all 8 ≈ 0, none
significant); mid/late reach +0.2…+0.3. This cannot be exposure — it is position
in the drive.

**The corresponding effect, stated conservatively.** Within-drive change
(`late80 − early80`) vs that drive's rating, pooled n = 131:
IQR +0.22, average angle +0.21, p95 +0.19, deviation +0.19 — the four *amplitude*
metrics converge, raw p = .010–.028, but **p_BH = 0.057 after FDR across the eight
metrics**, i.e. just short of conventional significance. Feb-Mar alone: IQR +0.23
(p = .019, p_BH = .150). Rate/jerk metrics show nothing (+0.05…+0.13).
**Report as: consistent, coherent, marginal — not significant.**

Interpretation: sickness does not make people steer differently *in general*; it is
associated with steering amplitude **degrading over the course of a drive**. This
**reverses iteration 1's RQ3 conclusion** ("no within-drive signature"), which was
based on 22 drives and tercile splits; with 131 drives and matched windows a modest
effect appears.

Supporting: behaviour does drift within a drive overall — steering IQR +0.18
(p = .031), mean |rate| +0.25 (p = .021), speed +0.11 (p = .0008) from early to late.

## Finding I3.9 — Current status of every candidate finding
| Claim | Status |
|---|---|
| Handlebar level distinguishes sickness *groups* | **Dead.** Null at n=39 and n=44, reversed sign vs pilot (I3.5), null under normalisation (I3.7). |
| Handlebar level correlates with sickness severity | **Dead within cohort.** Survives only pooled+unnormalised, i.e. as a cohort artifact. |
| Mean speed correlates with sickness (slower = sicker) | **Downgraded.** −0.38 Feb-Mar full-drive, but −0.12…−0.15 normalised. Exposure-driven. |
| **Within-drive increase in steering amplitude tracks post-drive rating** | **Best surviving finding.** ρ ≈ +0.19…+0.22 (4 amplitude metrics, n=131), p_BH = .057. Exposure-controlled by design. Marginal. |
| Sickness *change* (Δ MISC) relates to behaviour | **Dead.** ≈ 0 at every N and window. |

Net: the honest headline is now a *modest within-drive degradation effect*, not a
between-person marker. Everything that looked stronger was confounded by cohort or
exposure.

## Finding I3.10 — Figure set rebuilt for full N (`16_figures_v3.py` → `figures_v3/`)
`figures_v2/` (9 participants) is superseded and should not be used.
| Figure | Claim it carries |
|---|---|
| `w1_cohort_problem` | duration 2.4× longer in Feb–Mar; June far sicker; duration ↔ deviation (I3.4) |
| `w2_nonreplication` | pilot effect reversed sign at full N (I3.5) |
| `w3_early_vs_late` | **key result** — heatmap: early ≈ 0, mid/late +0.2…+0.3 (I3.8) |
| `w4_withindrive_change` | the surviving finding, with the p_BH = .057 caveat stated on the figure |
| `w5_normalisation` | matched exposure collapses nearly every correlation (I3.7) |
| `w6_traces_earlylate` | physical illustration (IQR 0.86° → 8.55° in one drive); labelled as the largest case, not typical |

Refactor: `hb_core.py` now holds the canonical loader/metrics (used by scripts
14–16). `12_handlebar_all.py` keeps its inline copy so its committed outputs stay
reproducible.

## Scope decision (user, 2026-08-04)
**OpenFace head-pose data is out of scope** — will not be analysed despite being
available in 104 folders. Focus instead: **mixed-effects model** of the I3.8
within-drive effect.

## Planned analysis — mixed-effects model (spec agreed before coding)
Unit of analysis: the drive (n = 131), nested in participant (n = 48).
Outcome: MISC after the drive. Primary predictor: within-drive change in steering
amplitude (`late80 − early80`), **person-mean-centred** to split the effect into:
  - within-person: "on the drive where THIS rider's steering degraded more than
    their own average, did they report feeling worse?"  ← the hypothesis
  - between-person: riders whose steering degrades more on average vs their
    average sickness (expected weak, per I3.5/I3.7)
Fixed covariates: drive number (practice/accumulation), cohort (protocol batch).
Random effect: intercept per participant (stable susceptibility; its ICC quantifies
the "individual differences dominate" story of I3.1/Finding 3.1).
Primary endpoint declared in advance: **Δ steering IQR** (strongest and most
duration-robust amplitude metric in I3.7/I3.8); the other three amplitude metrics
are sensitivity analyses, not additional hypotheses — this addresses the
8-way FDR penalty honestly (one confirmatory test, not eight exploratory ones),
with the transparent caveat that the endpoint was chosen from the same dataset,
so this is a sharper test of the same effect, not an independent replication.
Estimation: linear mixed model (statsmodels MixedLM), REML; sensitivity:
(a) random slope for drive number, (b) mixed logistic on MISC ≥ 2/≥ 3 to respect
the ordinal, zero-heavy outcome, (c) Feb–Mar-only refit.

## Finding I3.11 — Mixed-effects model results (`17_mixed_model.py` → `mixed_model_results.csv`)
Spec followed exactly as pre-declared above. 131 drives, 48 participants.

**ICC = 0.69** (participant variance 4.59, residual 2.09): 69 % of all MISC
variance is stable individual susceptibility — the definitive number for the
"individual differences dominate" theme.

**Primary confirmatory test — PASSES:** within-person Δ steering IQR
**β = +0.57 MISC points per SD, 95 % CI [+0.26, +0.88], p = 0.0004**, adjusted for
drive number, cohort, and each rider's susceptibility. Holds with a random slope
on drive (β = +0.41, p = .021). Also estimated: drive number +0.48 MISC/drive
(p = .0005 — within-session accumulation), June cohort +2.9 MISC (p = .0002),
between-person Δ IQR +0.74 (p = .036).

**But two sensitivity checks do not support it, and one is only partly excusable:**
| Check | Result | Reading |
|---|---|---|
| S1 other amplitude metrics | absmean +0.30 (p=.07) > SD +0.18 (p=.28) > p95 +0.08 (p=.61) | clear gradient, only the declared primary is significant — endpoint was chosen from the same data, so winner's-curse risk is real and must be stated |
| S3 GEE logit MISC ≥ 2 / ≥ 3 | OR 1.17 (p=.48) / 1.34 (p=.13) | not robust to treating MISC as ordinal; the linear result leans on the upper MISC range |
| S4 Feb–Mar only | β = +0.23 (p=.28) | attenuated — but partly *range restriction*, not refutation: median within-rider MISC range is 1 point in Feb–Mar vs 2 in June, and **13/39 Feb–Mar riders gave identical ratings after all three drives** (zero within-person outcome variance → no contribution to β₁ possible). Predictor variance is also 2.5× smaller (median within-rider SD of ΔIQR 0.55 vs 1.36). |

**Verdict for the report:** the within-drive effect is *supported but not
established*. Honest phrasing: "in the pre-specified mixed model the effect is
significant (β = +0.57, p < .001) and survives a random-slope check, but it
attenuates when MISC is dichotomised and in the cohort with compressed sickness
range; the effect is carried largely by riders whose sickness actually varied
between drives." The three secondary estimates (ICC 0.69, accumulation
+0.48 MISC/drive, June +2.9 MISC) are solid and reportable in their own right.

