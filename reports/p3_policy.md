# Phase 3 — Evaluate a policy

Write-up of findings. Figures: `reports/figures/p3/`, tables: `reports/tables/p3/`, notebooks: `notebooks/p3_policy/`.

**Status:** design planned, nothing estimated yet. The policy was chosen on 2026-10-22 from five candidates
(see [decisions](../docs/decisions.md)).

## Question

**Are cuts in the municipal IMI rate capitalised into sale prices?** Each municipality sets its urban IMI rate
(0.30% to 0.45%, 0.50% for some municipalities until 2023) every year. A permanent cut lowers the yearly tax on
a dwelling; if buyers value it, prices rise and the benefit goes to owners, not to buyers or renters (RQ7.4). The
estimate is also the behavioural parameter the phase 4 IMI lever needs. Outcomes: log real price per m² (main), the
price-to-income ratio (the affordability version; income is not affected by the rate) and, secondarily, real rent per
m² (2020 to 2024, only municipalities with at least 33 leases).

## Data (verified 2026-10-22)

Rates: Portal das Finanças, urban rate per municipality and tax year, 2012 to 2025, 308 municipalities every year
(`config/sources.yaml`, `at_imi_rates`; caveats in [data_quality](../docs/data_quality.md): 12 municipalities with
parish-specific rates in some years, island codes to match by name, year convention inferred, rates as stored today).
Prices, rents, income and the typology are already in the panel.

| Fact (mainland, 278 municipalities) | Count |
|---|---|
| Municipalities with a complete rate series 2015 to 2025 | 243 |
| Municipalities that never changed 2016 to 2025 (of which at the 0.30% floor) | 113 (98) |
| Rate cuts per year, 2016 to 2025 | 87, 47, 48, 43, 84, 39, 43, 46, 43, 30 |
| Rate increases per year, 2016 to 2025 | 0, 8, 4, 1, 0, 2, 2, 0, 0, 6 |
| Changes in 2018 to 2023 with two years before and one after observed | 303 (295 cuts) |
| of which isolated (no other change in that window) | 71 (68 cuts; 22 of at least 0.03 pp, 16 of at least 0.05 pp) |

Changes are small: the median is 0.01 pp (about 3% of the bill), the largest 0.15 pp. The prices start in 2016,
so the 87 municipalities that first cut in 2016 have no pre-period.

## Design

1. **Treatment.** A cut in the urban rate in tax year *t* (in 0.01 pp). The rate is decided in the last months of *t*
   and applies to the assessment of *t* (paid in *t*+1); INE's price is the 4th-quarter median of the last 12
   months, so the response is expected from *t*+1. Alternative alignments (response in *t*, *t*+2) are run as checks.
2. **Main estimate: stacked event study.** One stack per event year; treated units are municipalities with an isolated
   cut in *t* (no other change from *t*−2 to *t*+1); controls in the same stack are municipalities with no change in the
   window, compared within the same NUTS 3 region and year (region-year effects). Dynamic effects for *k* = −2 to +2, with
   the pre-period coefficients as the pre-trend test. A robust staggered estimator (Callaway and Sant'Anna or
   Sun and Abraham) is the check, because the two-way fixed-effects version is biased when effects differ by cohort.
3. **Second estimate: dose-response.** Log price growth on the change in the rate (and its lag) with municipality and
   region-year effects, using all changes, not only isolated ones.
4. **Controls and sensitivity.** Lagged price growth (cuts may follow booms), baseline rate (controls above the
   floor only, since 98 of the 113 never-changers are at 0.30% and cannot cut), cut size (at least 0.03 pp), dropping the
   2016 and 2020 waves (87 and 84 cuts, probably common shocks), dropping Lisboa and Porto, parish-rate
   municipalities treated as missing or at the range's midpoint.
5. **Placebos.** Future cuts (*t*+2 to *t*+3) on current price growth; rent as an outcome (it should not capitalise the tax
   if landlords do not pass it on, and is short); a cut in *t*+1 as "treatment" of *t*.

## Threats to credibility and how they are handled

- **Rates are chosen, not assigned.** Councils cut when budgets allow, after booms or before elections. Pre-trends
  and the lagged-growth control test this; a failed test means the result is reported as an adjusted association only
  (project guardrail), not a causal effect.
- **The effect is small and the outcome noisy (power).** A 0.01 pp cut on a tax base below market value, capitalised at
  3% to 5%, is worth roughly 0.1% to 0.25% of the price (assumptions: tax value 50% to 100% of price). An exploratory
  two-way fixed-effects fit with annual real price growth (standard deviation 16 pp) has a standard error of about 0.35 pp
  per 0.01 pp cut (0.35 with NUTS 3 × year effects; only the standard error was inspected). The minimum detectable
  effect is therefore about 0.7 pp per 0.01 pp cut, several times the plausible effect. The design can
  **bound** a pass-through (rule out large capitalisation) but cannot confirm a small one; results are reported with
  confidence intervals against the full-capitalisation benchmark, not as significant or not.
- **Few clean events.** 71 isolated events (22 of at least 0.03 pp); the dose-response estimate uses all 303 to 436 changes
  but is exposed to the staggered-timing bias.
- **Concurrent measures.** Family deductions (the IMI Familiar scheme), municipal short-term-rental rules and the 2020
  pandemic measures coincide with some cuts; the family-deduction flag is in the data and is a control.
- **Price measurement.** Municipal medians of the last 12 months, thin in small places; an annual log change of
  15% is common. Municipalities without a price in an event window drop out of that stack.

## Decision rules (fixed before estimating)

- Pre-trend coefficients jointly significant at 10%: report as an adjusted association, do not use causal language.
- Interval contains both zero and full capitalisation: report as inconclusive; phase 4 uses full capitalisation as the
  upper bound of the behavioural parameter with the range stated, not a point estimate.
- Interval excludes full capitalisation: phase 4 uses the interval as the cited estimate.

## Plan

1. Ingest: `sources/at.py` (fetch with dated raw snapshots, 1 request/s), `interim.py` table `at_imi_rates`
   (island name match, parish-rate flag), checks in `validate.py`, rows in the catalog; tests on a saved page.
2. Add `imi_urban_pct` and `imi_change_pp` to the municipal panel (and the family-deduction flag); tests.
3. `analysis/causal.py`: stacked event study, dose-response, pre-trend test, placebo; tests on synthetic data with a
   known effect (and a known pre-trend).
4. Notebooks `p3_01` (who cuts and when; descriptive), `p3_02` (event study and dose-response), `p3_03` (robustness,
   placebos, power); figures and tables via `save_fig` and `save_table`.
5. Fill this report (findings, limitations); hand the parameter and its range to `config/scenarios.yaml` and the
   phase 4 fiscal lever.

## Key findings

_Not started._

## Limitations

_Not started._
