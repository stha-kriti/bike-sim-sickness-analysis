"""Iteration 3 step 4: mixed-effects model of the within-drive steering effect.

Spec pre-registered in METHODS_LOG.md ("Planned analysis — mixed-effects model")
BEFORE this script was written. Summary:

  outcome     MISC rating after each drive (n = 131 drives, 48 participants)
  primary     delta steering IQR (last 80 s − first 80 s), person-mean-centred:
                within_x  = x_ij − mean_i(x)   <- THE confirmatory test (beta_1)
                between_x = mean_i(x)          <- expected weak (beta_2)
  covariates  drive number (centred at 2), cohort (june = 1)
  random      intercept per participant; ICC reported from the null model
  estimation  linear mixed model, REML (statsmodels MixedLM)

  sensitivity S1 other three amplitude metrics (declared sensitivity, not extra
                 hypotheses)
              S2 random slope for drive number
              S3 ordinal robustness: GEE logit on MISC >= 2 and MISC >= 3
                 (exchangeable working correlation within participant)
              S4 Feb-Mar cohort only (homogeneous protocol)

Output: mixed_model_results.csv + console report.
"""
import os
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))

PRIMARY = "steer_iqr_deg"
AMPLITUDE = ["steer_iqr_deg", "steer_absmean_deg", "steer_sd_deg",
             "steer_p95_abs_deg"]
NICE = {"steer_iqr_deg": "delta steering IQR",
        "steer_absmean_deg": "delta average angle",
        "steer_sd_deg": "delta deviation (SD)",
        "steer_p95_abs_deg": "delta large corrections (p95)"}

rows_out = []


def record(model_name, term, est, se, p, ci, n, note=""):
    rows_out.append(dict(model=model_name, term=term, estimate=round(est, 4),
                         se=round(se, 4), p=round(p, 4),
                         ci_low=round(ci[0], 4), ci_high=round(ci[1], 4),
                         n=n, note=note))


def prepare():
    df = pd.read_csv(os.path.join(HERE, "early_late_drives.csv"))
    df = df.dropna(subset=["misc"]).copy()
    for col in AMPLITUDE:
        d = df[f"delta_{col}"]
        pm = d.groupby(df["participant"]).transform("mean")
        # z-scale by the SD of the raw delta so coefficients read
        # "MISC points per 1 SD of within-drive change"
        s = d.std(ddof=1)
        df[f"within_{col}"] = (d - pm) / s
        df[f"between_{col}"] = (pm - pm.mean()) / s
    df["drive_c"] = df["drive"] - 2
    df["june"] = (df["cohort"] == "june").astype(int)
    return df


def fit_mixed(df, formula, re_formula, name, terms):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = smf.mixedlm(formula, df, groups=df["participant"],
                        re_formula=re_formula).fit(reml=True, method="lbfgs")
    print(f"\n--- {name}  (n={int(m.nobs)} drives, "
          f"{df['participant'].nunique()} participants; "
          f"converged={m.converged}) ---")
    ci = m.conf_int()
    for t in terms:
        est, se, p = m.params[t], m.bse[t], m.pvalues[t]
        lo, hi = ci.loc[t, 0], ci.loc[t, 1]
        print(f"  {t:28s} beta={est:+.3f}  SE={se:.3f}  "
              f"95% CI [{lo:+.3f}, {hi:+.3f}]  p={p:.4f}")
        record(name, t, est, se, p, (lo, hi), int(m.nobs))
    return m


def icc(df):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        null = smf.mixedlm("misc ~ 1", df, groups=df["participant"]).fit(
            reml=True, method="lbfgs")
    var_u = float(null.cov_re.iloc[0, 0])
    var_e = float(null.scale)
    val = var_u / (var_u + var_e)
    record("null", "ICC", val, 0.0, np.nan, (np.nan, np.nan), int(null.nobs),
           f"var_participant={var_u:.3f} var_residual={var_e:.3f}")
    return val, var_u, var_e


def main():
    df = prepare()
    print("=" * 78)
    print(f"MIXED-EFFECTS MODEL — {len(df)} drives, "
          f"{df.participant.nunique()} participants")
    print(f"MISC distribution: median={df.misc.median():.0f}, "
          f"zeros={int((df.misc == 0).sum())}, >=6: {int((df.misc >= 6).sum())}")
    print("=" * 78)

    # ---------- ICC from the null model ----------
    val, vu, ve = icc(df)
    print(f"\nNull model: participant variance={vu:.3f}, residual={ve:.3f}")
    print(f"ICC = {val:.2f} -> {val*100:.0f}% of MISC variance is stable "
          f"individual susceptibility")

    # ---------- PRIMARY (pre-registered) ----------
    f_primary = (f"misc ~ within_{PRIMARY} + between_{PRIMARY} + drive_c + june")
    m1 = fit_mixed(df, f_primary, "1", "PRIMARY: delta steering IQR",
                   [f"within_{PRIMARY}", f"between_{PRIMARY}", "drive_c", "june"])

    # ---------- S1: other amplitude metrics ----------
    for col in AMPLITUDE[1:]:
        fit_mixed(df, f"misc ~ within_{col} + between_{col} + drive_c + june",
                  "1", f"S1 sensitivity: {NICE[col]}",
                  [f"within_{col}", f"between_{col}"])

    # ---------- S2: random slope for drive number ----------
    fit_mixed(df, f_primary, "1 + drive_c", "S2: + random slope on drive",
              [f"within_{PRIMARY}", f"between_{PRIMARY}", "drive_c", "june"])

    # ---------- S3: ordinal robustness via GEE logit ----------
    for cut in [2, 3]:
        df[f"sick{cut}"] = (df.misc >= cut).astype(int)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gee = smf.gee(f"sick{cut} ~ within_{PRIMARY} + between_{PRIMARY} "
                          f"+ drive_c + june",
                          groups="participant", data=df,
                          family=sm.families.Binomial(),
                          cov_struct=sm.cov_struct.Exchangeable()).fit()
        t = f"within_{PRIMARY}"
        est, se, p = gee.params[t], gee.bse[t], gee.pvalues[t]
        lo, hi = gee.conf_int().loc[t]
        orr = np.exp(est)
        print(f"\n--- S3: GEE logit, MISC >= {cut}  (n={len(df)}) ---")
        print(f"  {t:28s} beta={est:+.3f}  OR={orr:.2f} per SD  "
              f"95% CI [{np.exp(lo):.2f}, {np.exp(hi):.2f}]  p={p:.4f}")
        record(f"S3 GEE logit MISC>={cut}", t, est, se, p, (lo, hi), len(df),
               f"OR={orr:.2f}")

    # ---------- S4: Feb-Mar only ----------
    fm = df[df.cohort == "feb_mar"].copy()
    fit_mixed(fm, f"misc ~ within_{PRIMARY} + between_{PRIMARY} + drive_c",
              "1", "S4: Feb-Mar cohort only",
              [f"within_{PRIMARY}", f"between_{PRIMARY}", "drive_c"])

    pd.DataFrame(rows_out).to_csv(os.path.join(HERE, "mixed_model_results.csv"),
                                  index=False)
    print(f"\nwrote mixed_model_results.csv ({len(rows_out)} rows)")
    print("\nInterpretation key: within_* = MISC points per 1 SD of within-drive "
          "steering change,\nrelative to the rider's own average (the "
          "pre-registered confirmatory test).")


if __name__ == "__main__":
    main()
