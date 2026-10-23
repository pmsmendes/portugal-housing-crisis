# Phase 4 — Forecast and simulate

Write-up of findings. Figures: `reports/figures/p4/`, tables: `reports/tables/p4/`, notebooks: `notebooks/p4_forecast/`.

**Status:** forecasting baselines and the national two-year forecast done (`p4_01`, 2026-10-23). Scenarios and the simulator
(RQ10.3 to RQ10.6, RQ8.5) are not built yet.

## Question

Which statistical forecaster should anchor the five to ten year affordability scenarios, and how wide must its intervals be?
Affordability is the outcome, so the forecast targets are the real house price index and an **ownership cost index** (real price
index × monthly payment per 100,000 EUR on a 30-year loan at the quarter's new-loan rate, 2024 = 100). The second is the quarterly
affordability indicator that exists: there is no quarterly national income, so the burden (cost over income) is formed in the simulator
from an income scenario.

## Design

- Series: national quarterly, 2009Q1 to 2026Q2 (70 quarters), on logs. Municipal series have 9 to 10 annual points (2016 to 2025), too
  short to validate a time-series model, so regional detail comes from the explanatory results of phase 2 and the simulator, not from
  municipal ETS or ARIMA.
- Methods (`analysis/forecasting.py`): naive, seasonal naive, drift, ETS (six forms, additive errors, chosen by AICc) and ARIMA(p,1,q)
  with or without drift (p, q ≤ 2, by AICc). Intervals: model-based for ETS and ARIMA, random-walk formulas for the baselines.
- Validation: rolling origin, first window 36 quarters (origins from 2017Q4), refit at every origin, horizons 1 to 8 quarters, RMSE, MASE,
  bias, coverage of the 80% and 95% intervals. Selection rule fixed before looking: lowest mean RMSE over horizons on both series.
- Checks: a 28-quarter first window, and dropping the origins of 2020 and 2021.

## Key findings

1. **ETS beats everything else on both series, and ARIMA is second.** RMSE relative to the naive forecast, mean over 1 to 8 quarters:
   real price index ETS 0.54, ARIMA 0.61, drift 0.77, seasonal naive 1.56; ownership cost index ETS 0.76, ARIMA 0.83, drift 1.00,
   seasonal naive 1.54. The ranking holds with a 28-quarter first window and without the 2020 and 2021 origins (ETS 0.50 to 0.54 and
   0.74 to 0.77). The rule picks **ETS** (additive trend with additive seasonality at the end of the sample).
2. **The naive forecast is badly biased in this period.** It under-forecasts real prices by 8.8 log points on average (ETS +0.8) because
   prices rose steadily; seasonal naive is worse than naive, so there is no usable seasonal pattern to repeat.
3. **The gain shrinks with the horizon for the cost index.** ETS beats naive by 37% one quarter ahead but by only 12% at eight (ARIMA by
   1%): credit costs move in jumps (2022 to 2023) that no trend model anticipates.
4. **Intervals are about right for prices and too narrow for the cost of ownership.** ETS 80% intervals contain 82% of price outcomes
   (95%: 96%) and 77% of cost-index outcomes (95%: 86%). The naive baseline contains 27% and 61%, so its intervals are the ones to distrust.
5. **Forecast, two years ahead (ETS, fitted on all 70 quarters).** Real price index 108 in 2026Q2 to 132 in 2028Q2 (80% range 115 to 150; the price index is INE's, 2025 = 100 nominal, deflated to
   2024 euros). Ownership cost index 108 to 127 (80% range 98 to 166; 2024 = 100). The model extends the recent trend; it knows nothing of rate or policy shocks.

## Limitations

- **One regime.** All origins (2017Q4 onward) lie in a boom: real prices fell until 2013 and rose after. A trend model wins in a boom by
  construction, and nothing here tests it on a turning point. The 2011 to 2013 downturn is inside the first window, not validated.
- **Eight quarters is the validated range.** A 20-quarter ETS forecast (tried first) extrapolates the boom to a real price index of 178 in
  2031 (80% range 91 to 348), so the five to ten year paths are scenarios, not statistical forecasts. This forecast is the starting point.
- **Short series, structural breaks.** 70 quarters with the 2011 crisis, the 2022 to 2023 rate shock and the pandemic; model selection by
  AICc on so few points is noisy.
- **National only, no income.** The ownership cost index excludes income; the municipal pattern (RQ10.2) is not forecast.
- **The index is a financing cost at constant real income**, not a burden: the level depends on the base period and on the assumed loan
  (30 years, one national rate, `MORTGAGE_TERM_YEARS`).

## Next

Scenarios and the simulator: income, rates, completions and households under optimistic, baseline and pessimistic paths; supply levers and
the IMI lever (0 to full capitalisation, see `reports/p3_policy.md`); the dashboard page. Parameters from phase 2 are adjusted
associations and enter as such.
