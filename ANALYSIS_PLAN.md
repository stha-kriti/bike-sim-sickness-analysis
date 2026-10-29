# Bike Simulator Study — Data Analysis Plan

**Course:** Experimental Study of Testbeds and Simulators
**Data:** CAVE bike-simulator study, participants 61–68 (June 22–26, 2026)

## Research questions

- **RQ1 (primary):** Do riding-behavior features (speed variability, acceleration/braking intensity, steering activity) relate to the post-drive MISC sickness score?
- **RQ2:** How does MISC evolve across the three drives per participant (accumulation vs. habituation)?
- **RQ3:** Within a drive, does riding behavior degrade over time in drives that ended with high MISC?
- **RQ4 (case study):** How does the one dropout (P66, vomited after drive 1) compare to other participants' first drives?

Note: with 8 participants, ~22 drive–MISC pairs, and a single dropout, this is a
correlational/exploratory study. Predictive modeling of dropout is not feasible and
should not be claimed.

## Key facts established during data exploration

- The `P###` in `data june` filenames is the **PermutationId (scenario)**, not the participant ID.
- **Linkage between survey and telemetry is possible via timestamps**, but the survey
  (Google Forms) timestamps run **~1 hour ahead** of the simulator clocks. After
  subtracting 1 hour, each "After Nth drive" entry lands 1–3 minutes after a drive's
  end time (verified for participants 62–68; e.g., P68: drives end 15:25/15:35/15:40,
  corrected survey times 15:31/15:36/15:41).
- Simulator `UnixTimestamp` is UTC milliseconds; filenames and `Time` column are local (CEST, UTC+2).
- **MISC scale mapping** (survey text → 0–10):
  Nothing = 0; Uneasiness = 1; Dizziness/warmth/headache/stomach awareness/sweating
  vague/slight/fairly/severe = 2/3/4/5; Nausea slight/fairly/severe = 6/7/8;
  Nausea (near) retching = 9; Vomiting = 10.
- Notable outcomes: P62 escalated 2→6→10; P68 went 8→8→9; P66 scored 10 after drive 1
  and quit; P64 and P67 stayed low/recovered.

## Known data-quality issues

1. Three files use an **old schema** (no `UnixTimestamp`, `Vel*`, `ForwardVel`,
   `PermutationId`, HMI columns): `P183_20260623_152733`, `P183_20260623_153752`,
   `P184_20260623_155359`. Exclude (they also match no survey entry).
2. Some files end with a **truncated final row** — drop unparseable rows.
3. **Restarts/fragments:** several drives span multiple files, incl. fragments of
   0.3–0.5 min. Rule: keep the longest file per drive slot; document the decision.
4. No "Before first drive" MISC baseline exists for participants 61–68.
5. `ForwardVel` is hardware-capped at 7.5 m/s; angles wrap at 0°/360° (unwrap before
   differentiating); logging rate is 20 Hz.
6. Several June 22 sessions match no surveyed participant (pilot or participant ≤60) —
   flag and exclude after confirming against lab notes.

## Phases

### Phase 1 — Linkage table ✅ DONE (see `analysis/`)
Built by `analysis/01_build_linkage.py` → `analysis/linkage_table.csv` (per session
file) and `analysis/drives_summary.csv` (per participant-drive, 22 rows).

Matching rule that survived testing: a session belongs to drive N if it **started**
between survey entry N−1 and N (corrected by −1 h), same day. Matching on session
*end* fails because the logger keeps recording standstill while the participant
dismounts and fills in the survey, so a drive's logged end can fall a few minutes
after its own survey entry. Among multiple files per drive (restarts), the main
recording is the new-schema file whose end is closest to the survey time.

**Validation:** the resulting scenario IDs are perfectly consecutive triples per
participant (P61=180/181/182, P62=183/184/185, … P68=201/202/203) even though the
matcher only used timestamps — strong independent confirmation of the linkage.
All end-to-survey gaps are within −4/+7 min (mostly 0.5–3 min).

Flags: (a) sessions P177_174107/P178/P179 (evening of 06-22) match no surveyed
participant → excluded; (b) `P195_20260624_173926` falls in P65's drive-1 window
but carries P66's scenario ID (195) — likely a setup/test run; it is only a
non-main fragment, so it does not affect the analysis; (c) the three old-schema
files fall in P62's drive-1 window (parallel/misconfigured logger) → excluded.

### Phase 2 — Cleaning ✅ DONE (`analysis/02_clean_data.py`; see `analysis/METHODS_LOG.md` Phase 2)
- Use `SimBike.csv` only (Dynamic/StaticObjects not needed for these RQs — state why).
- Exclude old-schema files and fragments < 1 min; keep longest file per drive.
- Drop truncated/malformed rows; trim standstill at start/end of each drive.
- Unwrap `BikeYaw`/`HandlebarYaw`; compute steering deflection =
  wrap(HandlebarYaw − BikeYaw, ±180°).
- Convert MISC text to numeric 0–10.

### Phase 3 — Feature engineering ✅ DONE (`analysis/03_features.py`; see `analysis/METHODS_LOG.md` Phase 3)
Duration, distance, mean/max/std of `ForwardVel`, acceleration RMS, hard-deceleration
count, steering-reversal rate (/min), steering-angle std, yaw-rate variance.
Also compute per drive-third for RQ3.

### Phase 4 — Visualization ✅ DONE (`analysis/04_figures.py` → `analysis/figures/`; see `analysis/METHODS_LOG.md` Phase 4)
- MISC trajectory per participant across drives (headline figure, RQ2).
- Feature vs. MISC scatter plots (RQ1).
- Top-down trajectory maps (`PosX`/`PosZ`) colored by speed: low- vs. high-MISC drive.
- Time-series panels for the P62 escalation and P66 dropout stories.
- Feature distributions by MISC band: none (0–1), mild (2–5), nausea (6–10).

### Phase 5 — Statistics ✅ DONE (`analysis/05_stats.py` → `analysis/stats_summary.csv`; see `analysis/METHODS_LOG.md` Phase 5)
Spearman correlations feature ↔ MISC (report cautiously; drives within a participant
are not independent); within-participant ΔMISC vs. Δfeature; P66 vs. other first
drives (descriptive). Explicitly state sample-size limits.

### Phase 6 — Deliverables
Cleaned tidy dataset (linkage table + per-drive features), analysis notebook, figure
set, and a methods note documenting all cleaning decisions — especially the +1 h
clock correction.

## Decisions (confirmed 2026-07-23)
- No lab notes available — the timestamp linkage stands on its own, backed by the
  scenario-ID continuity validation above.
- Research question adjusted to the correlational framing (RQ1–RQ4); no predictive
  claims about dropout.
- Video/OpenFace data is out of scope — telemetry-only analysis.
