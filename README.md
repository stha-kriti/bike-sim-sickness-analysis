# Bike Simulator Sickness Analysis

Analysis code for a CAVE bicycle-simulator study looking at whether riding
behaviour, mainly handlebar steering, tracks simulator sickness as measured by
the Misery Scale (MISC) after each drive.

This repository holds the analysis only: the scripts, the figures they produce,
and the methods notes. **The study data is not included.** That covers raw
simulator telemetry, the MISC questionnaire responses and every derived
per-participant table. Participant IDs used in the notes and figures
(e.g. P62) are study pseudonyms.

## Main result

Comparing riders with each other doesn't work: about 69% of the variance in
MISC ratings is stable between-person susceptibility (ICC = 0.69). Within a
rider, an increase in steering deflection from early to late in a drive is
associated with higher post-drive sickness. In a linear mixed model the effect
is β = +0.57 (p < .001), and it survives a random-slope check. It weakens when
MISC is dichotomised and in the cohort whose sickness ratings barely moved, so
the finding is *supported but not established*. See
[`analysis/METHODS_LOG.md`](analysis/METHODS_LOG.md) for the full reasoning,
the negative results and the sensitivity checks.

## Report and slides

- [Final report (PDF)](report/ests_report_final.pdf)
- [Final presentation (PPTX)](report/ests-presentation.pptx)

## Repository layout

| Path | Contents |
|---|---|
| `ANALYSIS_PLAN.md` | Initial research questions and analysis plan |
| `ITERATION2_DESIGN.md` | Iteration 2 design (handlebar focus, group comparison) and final results summary |
| `analysis/METHODS_LOG.md` | Running log of every finding, decision and method across all three iterations |
| `analysis/01`–`05_*.py` | Iteration 1: linkage, cleaning, features, figures, statistics (June cohort) |
| `analysis/06`–`10_*.py` | Iteration 2: sickness groups, linkage v2, handlebar features, group stats |
| `analysis/11`–`19_*.py` | Iteration 3: full-dataset audit, normalisation, early-vs-late windows, mixed model, final figures |
| `analysis/hb_core.py` | Shared handlebar-metric helpers |
| `analysis/figures*/` | Figures produced by the scripts |

## Running the scripts

Python 3.12 with the packages in `requirements.txt`:

```
pip install -r requirements.txt
```

The scripts expect the (non-public) data in this layout next to `analysis/`:

```
data june/   SimulationData_P<scenario>_<timestamp>_{SimBike,DynamicObjects,StaticObjects}.csv
new data/    P<participant>D<drive>/...   (Feb–Mar sessions)
ssq/         MISC (SSQ) [BikeSim2026].csv
```

Run the scripts in numeric order. Each one writes its CSV outputs into
`analysis/`; those outputs are git-ignored.
