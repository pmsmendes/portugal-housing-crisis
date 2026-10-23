# Phase 3 — Evaluate a policy

Write-up of findings. Figures: `reports/figures/p3/`, tables: `reports/tables/p3/`, notebooks: `notebooks/p3_policy/`.

**Status:** estimated (2026-10-23). The policy was chosen on 2026-10-22 from five candidates (see [decisions](../docs/decisions.md)).
Result: **inconclusive, and an adjusted association rather than a causal effect**; phase 4 gets an upper bound, not a point estimate
(see Key findings).

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

1. **Done:** `sources/at.py` (dated raw snapshots, 308 pages), interim table `at_imi_rates` (4,312 rows), checks in
   `validate.py`, catalog rows, tests. 2025 rates are complete (checked in `p3_01`); the meaning of the parish link is still not verified
   (handled as a sensitivity run).
2. **Done:** `imi_urban_pct`, `imi_change_pp`, `imi_parish_rates`, `imi_deduction_link` in the municipal panel, with panel checks and tests.
3. **Done:** `analysis/causal.py` (event table, stacks, stacked event study, cohort 2×2 check, dose-response, benchmark) with
   tests on synthetic data with a known effect and a known pre-trend.
4. **Done:** notebooks `p3_01` (who cuts and when), `p3_02` (event study, dose-response), `p3_03` (robustness, rent, power).
5. **Done (2026-10-23):** the bound is in the phase 4 IMI lever (`config/scenarios.yaml`, `policies.imi_reform`; the simulator runs capitalisation from none to full, `reports/p4_forecast.md`). **Open:**
   the placebo "a cut in *t*+1 as treatment of *t*" is covered by the future-cut leads of the dose-response, not run separately.

## Key findings

All effects are in % of the real price per m² per 0.01 pp of cut (a typical isolated cut is 0.02 pp). Full capitalisation of a
permanent 0.01 pp cut is **0.19%** (range 0.10% to 0.33%: assessed value 50% to 100% of the price, discount rate 3% to 5%).

1. **Municipalities that cut are not like those that do not** (`p3_01`). In the year before the cut, their real price grew 9.7%
   against 4.5% (t = 3.7); they are more urban (23% against 3%) and pricier, and start from higher rates. Cuts follow booms.
2. **Usable events are few and small.** 303 cuts in 2018 to 2023, 295 with the window observed, **68 isolated** (22 of at least 0.03 pp),
   of which 65 have prices in the whole window; 30 of those are in the 2020 wave. Median isolated cut 0.02 pp.
3. **The pre-trend test fails** (`p3_02`). Treated municipalities' prices were 1.5% per 0.01 pp lower two years before the cut than one year before
   (joint pre-trend test p = 0.02; p = 0.06 for a cut of any size). Under the decision rule the post-cut coefficients are **adjusted associations**,
   not causal effects. The cohort-by-cohort check gives the same picture (−1.2% before; binary −4.3%, significant).
4. **The post-cut effect is not pinned down.** One year after: −0.24% [−1.83, +1.35]; two years after: −0.81% [−3.54, +1.92]
   (stacked regression). The cohort check is +0.53% [−1.24, +2.76] and −0.21% [−2.08, +2.76]. Every interval contains zero and the full-capitalisation benchmark.
5. **Robustness** (`p3_03`). Across nine specifications no interval excludes either zero or full capitalisation. The pre-trend test is rejected in 7 of 9;
   it is *not* rejected when the 2020 wave is dropped (p = 0.21) or when controls are limited to municipalities above the floor (p = 0.19), but those
   estimates are the least precise (35 treated municipalities, or 157 controls). Price-to-income as the outcome gives the same result as price.
6. **Dose-response** (all rate changes, 2016 to 2025). A cut raises price growth by +0.24% this year and +0.14% last year per 0.01 pp; the sum is +0.38% (SE 0.39),
   or +0.23% (SE 0.48) controlling for last year's growth. Positive and close to the benchmark, but its interval includes zero. The placebo (cuts one and two years
   *ahead*) is of the same size (+0.45%, −0.62%; neither significant), so the estimate cannot be separated from the timing of cuts.
7. **Power.** The minimum detectable effect (2.8 standard errors) is 2.3% one year after and 3.9% two years after: **12 and 21 times** the full-capitalisation benchmark.
   The dose-response (SE 0.39) detects about 1.1%, 6 times the benchmark. The design can rule out only capitalisation far above the benchmark (the one-year interval's upper end is 1.35%, 7× the benchmark).
8. **Rent** is not usable: INE rents start in 2020, which leaves 5 treated municipalities (one-year coefficient −4.0% [−11.0, +3.0]).

**Decision rules applied:** pre-trends rejected, so no causal language. Interval contains zero and full capitalisation, so the result is *inconclusive*.
**For phase 4:** the IMI lever uses the share of a cut capitalised into prices as an assumption between 0 (no capitalisation) and 1 (full: 0.19% of the price per
0.01 pp, range 0.10% to 0.33%), run at both ends; there is no estimate to cite for the middle. Under the project rule on behavioural parameters, the simulator must say so.

## Limitations

- **Selection into treatment.** Rates are chosen after price booms, and the pre-trend test rejects. The design cannot separate the effect of the cut from mean reversion after
  the boom that preceded it.
- **Power.** Few, small, isolated cuts and noisy municipal medians (annual log change with sd 16 pp). Only effects 12 to 21 times the benchmark are detectable.
- **Common shocks.** The 2020 wave is almost half the treated sample; without it the estimates move but remain imprecise. The 2016 wave (87 cuts) has no pre-period and is not used.
- **Rates as stored today.** Later corrections overwrite history; 'year' is the inferred tax year; 12 municipalities have parish-specific rates and no single rate; the meaning of the parish link is
  unverified (a sensitivity run drops the 102 municipalities that show it in any year from 2013; the 2012 pages use another convention, 206 municipalities).
- **Timing.** The response is assumed to start the year after the rate is decided; alternative alignments are only covered through the k = 0 and k = +2 coefficients.
- **Benchmark assumptions.** Assessed value/price (0.5 to 1.0) and the discount rate (3% to 5%) are assumptions, not estimates; the assessed value of many old dwellings is far below market value, which would put the true benchmark at the low end.
- **Concurrent measures.** The family-deduction (IMI Familiar) flag is a sensitivity only (dropping units whose status changes in their window); municipal short-term-rental rules and
  pandemic measures are not controlled.
- **Mainland only.** The islands' rates use a different code scheme and have few events.
