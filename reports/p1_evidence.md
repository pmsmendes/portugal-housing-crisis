# Phase 1 — Establish the evidence

How have prices, rents and affordability evolved, and where? Descriptive evidence only: nothing here is a causal
claim. Figures: `reports/figures/p1/`, tables: `reports/tables/p1/`, notebooks: `notebooks/p1_evidence/`
(`p1_01_prices_rents_rates`, `p1_02_affordability_indicators`, `p1_03_long_run_prices`). Definitions: [methodology](../docs/methodology.md).

## Key findings

1. **House prices have more than doubled in real terms since 2013.** Deflated with the CPI, the national index
   fell until 2013 and is now 2.6 times its low. Nominally Portugal's index is 3.0 times its 2015 level against 1.7
   for the EU27; the next highest are Ireland and Spain, at about 2.0.
2. **Prices per m² rose 68% in real terms in the median municipality between 2016 and 2025** (645 to 1,083 euros,
   constant 2024 euros). In 213 of 302 municipalities they rose more than 50%. Lisboa is at 4.4 times the median.
3. **Rents have risen as fast as prices, and faster lately.** On a fixed set of 187 municipalities, real prices and
   real rents both rose about 24% between 2020 and 2024; over the last two years rents rose 18% and prices 11%.
4. **The mortgage rate explains most of the recent jump in the burden of buying.** Rates on new loans fell to 0.6% in
   2021 and rose to 4.8%; a loan of 100,000 euros costs 73% more a month at the peak than at the trough. The median
   burden went from 28% to 45% of income (2016 to 2024); with the rate held at its 2016 level it would be 33%.
5. **Affordability worsened in three quarters of municipalities, and the gap between places widened.** The median
   municipality needs 9.5 years of income to buy (8.0 in 2016), the 90th percentile 18 (12 in 2016). Municipalities
   above 15 years went from 5% to 19% of the total; price-to-income worsened in 222 of 296 and improved in 74.
6. **The pressure is concentrated.** In 2024, 56 of 299 municipalities are above 15 years of income, 14 of the 15 in
   Faro and 10 of the 16 around Lisboa. The largest deteriorations are in Cascais (+13 years), Lagos (+12), Aljezur
   (+12), Porto (+11) and Vila do Bispo (+10); by district, Setúbal (+7.2) and Lisboa (+6.8). Interior districts such
   as Bragança and Guarda stayed near 5 years, and 70 municipalities are below 6.

7. **Over thirty years, prices are at a record and the ratio to income is the highest in the series.** After inflation,
   national house prices peaked in 2001, fell 33% to 2013 and passed that peak again in 2020; in 2025 they are 2.3 times
   the 2013 low. The OECD price-to-income index (2015 = 100) was 142 in 1995, fell to 97 in 2013 and is 167 in 2025,
   33% above its long-term average. Real rents barely moved between 1995 and 2015 and are 11% higher in 2025 than in
   2015: the rise is in the price of buying, not of renting (section *Thirty years*).

## Prices and rents

![Real vs nominal house price index](figures/p1/hpi_real_vs_nominal.png)

![Portugal against the EU and peers](figures/p1/hpi_peers.png)

![Real price per m2 across municipalities](figures/p1/price_sqm_real_fan.png)

![Real prices and rents since 2020](figures/p1/real_price_rent_index.png)

Tables: `real_growth_by_municipality.csv`, `price_sqm_real_by_district_2016_2025.csv`,
`rent_sqm_real_by_district_2020_2024.csv`.

## Thirty years

![Thirty years of national prices](figures/p1/long_run_prices.png)

Two sources extend the national view back (`p1_03`). The BIS residential property price index starts in 1988; from 2009 it
**is** INE's index (the ratio is constant to four decimals over 69 quarters), and before 2009 it is a BIS compilation of
national sources. The OECD analytical indicators add the rent index (from 1959) and the price-to-income ratio (from 1995,
nominal price over nominal disposable income per head). Real values use the project's CPI deflator, as the BIS's real
series does (the OECD's own real series deflates differently, up to 4% apart).

- **Cycles.** Real prices rose in the early 1990s, peaked in 2001 (139 on 2015 = 100), fell 33% to 2013 (93), passed the
  old peak in 2020 (149) and stood at 214 in 2025. The price-to-income index fell from 142 (1995) to 97 (2013) and then
  rose to 167: 17% above 1995 and, against the OECD's long-term average, 33% above it.
- **Prices against rents.** Real rents rose from 73 (1988) to about 95 by 1995 and stayed within 93 to 97 until 2012;
  they are 111 in 2025. The price-to-rent index is 193 (2015 = 100), 42% above its long-term average.
- **The median municipality understates the typical buyer's experience.** From 2016 to 2024 the national price-to-income
  index rose 42%, the median municipality's 19%, and municipalities weighted by their 2024 sales 49% (mean) to 53%
  (median). The national index follows transactions, which are in cities and on the coast (urban municipalities are
  32 of 271 but 46% of sales); the median municipality is a typical inland one. The two ratios use different incomes
  (per head against per tax household), so only changes are compared (`national_vs_municipal_pti.csv`).

Tables: `long_run_summary.csv`, `national_vs_municipal_pti.csv`.

## Mortgage rates

![Mortgage rates and payments](figures/p1/mortgage_rates.png)

![Mortgage burden with the rate held fixed](figures/p1/mortgage_burden_rate_effect.png)

## Affordability indicators

![Indicators over time](figures/p1/affordability_indicators_trends.png)

![Least affordable municipalities](figures/p1/pti_least_affordable_2016_2024.png)

## Where

| Price-to-income, 2024 | Change in price-to-income, 2016 to 2024 |
|---|---|
| ![PTI map](figures/p1/pti_map_2024.png) | ![PTI change map](figures/p1/pti_change_map_2016_2024.png) |

| Rent-to-income, 2024 | Mortgage burden, 2024 |
|---|---|
| ![RTI map](figures/p1/rti_map_2024.png) | ![Burden map](figures/p1/mortgage_burden_map_2024.png) |

Tables: `affordability_by_municipality_2024.csv`, `pti_by_district_2016_2024.csv`,
`pti_change_by_municipality_2016_2024.csv`.

## Limitations

- **Short municipal history.** Municipal prices exist from 2016 and rents from 2020; INE's national index starts in
  2009. The thirty-year view is national only (BIS and OECD, `p1_03`); RQ1.1 stays partly answered for municipalities.
- **The long national series has a seam in 2009.** Before it the price index is a BIS compilation whose source is not
  stated in the data; there is no overlap with another index to test the join, and the 2009 growth differs between the BIS
  (-0.9%) and the OECD (+0.2%): read the change across 2008 to 2009 with about a point of doubt. The OECD's 2025 values are
  the latest and may be revised. Price-to-income uses income per head, not per household, and starts in 1995.
- **Levels are not comparable internationally.** Income is the median per IRS tax household (single filers
  included) and a dwelling is the municipality's census mean size (the size of occupied homes, probably larger than
  what is bought or newly let). Lisboa shows 25 years of income and a burden of 119% for this reason. Compare places
  and years; the 100 m² variants and the sensitivity table in the methodology show how much the levels move
  (2024 median burden between 40% and 57% across plausible loan terms and loan-to-value ratios).
- **Rents cover a subset.** A municipal rent is published only from 33 new leases a year, so 96 of 308 municipalities
  (mostly inland) are missing in 2024; rents are those of new leases, not of existing contracts.
- **Thin markets are volatile.** The largest percentage price rises (for example Lajes do Pico, +547%) come from
  municipalities with few sales; use the tables with the sales count in the panel.
- **One national mortgage rate** (agreed rate on new floating-rate loans) applies to every municipality, and the loan
  (80% of the price over 30 years) is an assumption, not an estimate.
- **Descriptive, not causal.** The report says what changed and where, not why; that is phase 2.

## Questions answered

RQ1.3, RQ1.5, RQ4.1 and RQ4.2 are answered with the available data; RQ1.1 (national thirty years done, municipal from 2016), RQ1.4 and RQ1.7 are partly answered
(see [research_questions](../docs/research_questions.md)).
