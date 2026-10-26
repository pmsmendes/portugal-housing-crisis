# Methodology

Definitions are implemented once in code; this file states them and points to the function.

## Affordability indicators (`src/pthousing/features/affordability.py`)
| Indicator | Definition | Function | Notes |
|---|---|---|---|
| Price-to-income (PTI) | Median sale price per m² × dwelling area / median annual gross income per tax household | `price_to_income` | Years of income to buy a typical home (RQ1.5). Panel column `pti_years` |
| Rent-to-income (RTI) | Median monthly rent per m² of new leases × dwelling area × 12 / median annual income, in % | `rent_to_income_pct` | Panel column `rti_pct`; 2020–2024 only (rents are published from 33 new leases) |
| Mortgage burden | Yearly payments on a loan of `MORTGAGE_LTV` (80%) × dwelling price, `MORTGAGE_TERM_YEARS` (30), at the year's average contract rate on new housing loans / median annual income, in % | `mortgage_burden_pct`, `mortgage_payment_monthly` | Panel column `mortgage_burden_pct`. Fixed-payment (annuity) loan, one national rate for all municipalities |
| Ownership cost index | Real house price index × monthly payment per 100,000 EUR of a 30-year annuity at the quarter's average contract rate, rebased to 100 over a base year | `ownership_cost_index` | National quarterly (`national_quarterly`); the income-neutral affordability indicator forecast in p4 (no quarterly national income exists; the simulator divides by an income scenario) |
| Housing vs household growth | (Δ conventional dwellings − Δ private households) per 1,000 households at the start, census 2011 → 2021 | `supply_gap_per_1000` | Panel column `supply_gap_2011_2021_per_1000` (one value per municipality) (RQ2.3, RQ4.5) |
| Implied housing gap | (completions − new households) per 1,000 households at the start, 2021 → 2023; new households = Δ population / persons per household in 2021 (population estimate / census households) | `implied_gap_per_1000`, `analysis/supply.py` | Proxy for the years after the last census (RQ2.3, RQ4.5): completions are new family dwellings only, households are implied, not counted |
| Rent yield | 12 × median monthly rent per m² of new leases / median sale price per m², in % | `gross_rent_yield_pct` (`features/rent_vs_buy.py`) | 2020–2024 (RQ1.6) |
| Cost of owning | % of the price per year, before price gains: `LTV × mortgage rate` + `(1 − LTV) × OPPORTUNITY_RATE_PCT` + `IMI_TAXABLE_SHARE × municipal IMI rate` + `MAINTENANCE_PCT` + `BUYING_COSTS_PCT / HOLDING_YEARS` | `owner_cost_components`, `owner_cost_rate_pct` | User cost of housing. Interest only, since principal repaid is saving. Columns added by `add_indicators` (not stored in the panel) |
| Break-even appreciation | Cost of owning − rent yield (percentage points of yearly nominal price growth) | `breakeven_appreciation_pct` | Negative: owning is cheaper even if prices fall; above `EXPECTED_APPRECIATION_PCT` (2%, flat real prices): renting is cheaper |
| Owner cash bill / rent | (annuity payments on the loan + IMI + upkeep) / rent, yearly | `owner_cash_cost_pct` | Includes principal, so above 1 can mean saving, not cost |
| Upfront cash | `PTI × ((1 − LTV) + BUYING_COSTS_PCT / 100)`, years of income | `upfront_cash_years` | Deposit plus buying costs |

### Inputs and conventions
- **Price and rent are per m²**: INE publishes no total dwelling price, so a dwelling is the per-m² value times an area. The area is the municipality's census mean useful area of dwellings of usual residence (`dwelling_area_sqm`, linearly interpolated between 2011 and 2021, flat outside). That is the size of *occupied* homes, probably larger than what is typically bought or newly let, so levels are biased upwards; the `_100sqm` columns use a fixed `BENCHMARK_AREA_SQM` (100 m²) to compare municipalities on one dwelling.
- **Timing**: INE's price is a last-12-months median, so the panel takes the 4th-quarter value as the calendar-year median. Rents are annual medians of new leases.
- **Income**: gross reported income per tax household from the IRS (median, `income_median_eur`). Single-person filers are included, so it is lower than the income of the household that buys a home. Ratios are therefore high (Lisboa 2024: PTI 25) and **not comparable with international price-to-income figures**; read them as comparisons between municipalities and over time.
- **Mortgage rate**: the annualised agreed rate on new floating-rate housing loans (initial fixation up to one year, Banco de Portugal), annual mean of full years, available from 2003. The APRC is 1.1–1.8 pp higher since 2015 because it includes fees and insurance, so it is not used for payments; it is kept as `mortgage_aprc_new_pct`.
- **No behavioural content**: the indicators are accounting ratios of same-year nominal values; no deflation is needed.

### Sensitivity of the mortgage burden (2024, median over the 303 municipalities with a price)
| Assumption | Median burden |
|---|---|
| Base: LTV 80%, 30 years, agreed rate 4.36% | 45.3% |
| LTV 70% / 90% | 39.6% / 50.9% |
| Term 40 / 20 years | 40.0% / 56.8% |
| APRC (5.98%) instead of the agreed rate | 54.3% |
| 100 m² benchmark dwelling | 36.9% |
| Same prices and incomes with the 2021 rate (2.5%) | 27.8% |

### Assumptions of the rent-vs-buy comparison (`config.py`; assumptions, not estimates)
| Parameter | Value | Why / range tried |
|---|---|---|
| `OPPORTUNITY_RATE_PCT` | 3% | Return forgone on the deposit; no deposit-rate series in the project. 0% to 5% |
| `MAINTENANCE_PCT` | 1% of the price | Common rule of thumb (1-2%). 0.5% to 2% |
| `BUYING_COSTS_PCT` | 6% | IMT, stamp duty, notary and registry on a typical purchase; not computed from the IMT brackets. 3% to 9% |
| `HOLDING_YEARS` | 10 | Spreads the buying costs; selling costs ignored. 5 to 20 |
| `IMI_TAXABLE_SHARE` | 0.6 | Taxable value (VPT) as a share of the market price; VPT is not in the data. 0.3 to 1.0 |
| Mortgage rate | observed | Agreed rate on new floating-rate loans, as in the mortgage burden |

Municipalities without one urban IMI rate (parish rates) take the year's mean rate (8 of 308 in 2024). The 2024 median break-even moves between -0.3 and +1.3 pp across these ranges (`rent_vs_buy_sensitivity_2024.csv`). The national long series divides a scale by the OECD price-to-rent index; the scale makes it match the lease-weighted municipal yield over 2020-2024 (`calibrate_yield_scale`).

### Alternative definitions for robustness (M1)
The comparison of these definitions across municipalities is in `reports/p1_evidence.md` (`p1_06`, `descriptive.compare_definitions`): rankings agree (rank correlation 0.92-1.00) except rents (change 0.43), and the median rise 2016-2024 is 17-25% by definition.
`pti_years_100sqm`, `pti_years_mean_income` (mean instead of median income, for the 3% of municipality-years where the median is missing and as a check), `rti_pct_100sqm`, `mortgage_burden_pct_100sqm`; other LTV, term and rate choices through the function arguments.

## Real values (`src/pthousing/data/harmonize.py`)
- Deflator: INE CPI, all items, national (annual `annual_deflator`, quarterly `quarterly_deflator`), constant euros of `BASE_YEAR` (2024) in `config.py`. Factor = CPI(base) / CPI(period); `to_real` applies it.
- Columns: nominal `*_eur`, real `*_eur_real`; the factor is stored as `deflator_to_base_year`. Quarterly factors use the mean of the quarter's three monthly indices and the mean of the 12 months of the base year.
- Index columns keep their own base (`_b2025`, `_b2015`); real indices are nominal × deflator (e.g. `hpi_total_real_b2025`).

## Harmonising sources (M2)
Sources differ in frequency, geography and definition. The rules, each applied at table-build time and tested:

**Frequency** (never interpolate; convert by the rule that fits the quantity)
- Prices: municipal prices are quarterly last-12-month medians; the annual value is the fourth quarter (the calendar-year median) (`build_panel._annual_prices`). The BIS quarterly index enters the long national series as an annual mean rebased to 2015.
- Rates: monthly rates are averaged over the three months of a quarter or the twelve of a year (`macro.quarterly_frame`, `macro.annual_rates`, `build_panel`).
- Deflator: a quarter's factor uses the mean of its three monthly CPI indices over the mean of the twelve months of the base year (`harmonize.quarterly_deflator`).
- Stocks and ratios (loans, household debt): values at the quarter-end month (`interim.build_bp_household_debt`); a quarter missing its last month is dropped.
- Annual-only series (wages, unemployment, GDP growth) are analysed annually (`macro.annual_frame`); they are not spread over quarters.

**Geography**
- One key, `muni_code` (INE DICOFRE), and CAOP 2024 boundaries; municipal tables keep the full 308 grid with suppressed cells NaN, never zero.
- `data/external/muni_crosswalk.csv` carries NUTS II and III codes in the 2013 and 2024 vintages (read from INE `geocod` prefixes), so tables in either vintage join; municipalities created after 1995 (Vizela, Trofa, Odivelas) are masked before their creation year (`harmonize.mask_pre_creation`).
- National series (BIS, OECD, Eurostat, BPstat) are joined to municipal panels by year or quarter, never allocated to municipalities, except the national mortgage rate that enters municipal burdens as one rate.

**Definitions and vintages**
- Where two methods or vintages overlap, they are spliced at the table build after a test of the overlap: municipal prices (2018 method to 3Q2019, 2022 method from 4Q2019, median overlap ratio 1.002) and income (2013 vintage 2015-2017, 2024 vintage from 2018, identical on the overlap).
- Where nothing overlaps, they are not spliced: the BIS price index equals INE's exactly from 2009 but no overlap exists before it, so the 2009 seam is marked on charts and not re-chained (`docs/decisions.md`).
- One deflator everywhere (INE CPI, base year in `config.py`); the OECD's own real series differs by up to 4% and is not used. One definition per rate indicator (APRC for new borrowing, the stock rate for the burden on existing borrowers).
- Cross-source checks in `validate.cross_checks` compare what two sources both publish (Eurostat against INE house prices, CPI against HICP).

## Panels (`src/pthousing/data/build_panel.py`, files in `data/processed/`)
| Panel | Grain | Content |
|---|---|---|
| `panel_municipality_year` | 308 municipalities × 1995–2025 | Prices (existing / new / total), rents, bank valuations, income, licensed and completed dwellings, population and 65+ share, census 2011/2021 stock columns, short-term rental units (mainland), mortgage rates, real values, indicators |
| `national_quarterly` | quarter, 2005Q1 onwards | INE HPI (total / new / existing), Eurostat HPI for Portugal, peers and EU27, CPI and deflator, real HPI, mortgage rates and volume, monthly payment on a 100,000 EUR loan |

Missing means "not published / not covered", never zero: prices from 2016, rents 2020–2024, income 2015–2024, population 2011–2023, short-term rentals NaN for the island municipalities.

## Geography
- Unit of analysis: municipality (308), key `muni_code` (INE DICOFRE, 4-digit string).
- Typology (`data/external/muni_typology.csv`, `data/typology.py`): coast / estuary / inland from CAOP shoreline segments; urban / intermediate / rural from 2021 residents per km² (500 and 100); tourist from registered short-term rentals per 1,000 dwellings (25, mainland). Proxies, not INE classes.
- Boundary/definition changes handled through `data/external/muni_crosswalk.csv` (NUTS vintages, `valid_from_year` for Vizela, Trofa and Odivelas).

## Models
| Phase | Method | Module | Spec |
|---|---|---|---|
| p2 | Spatial autocorrelation (Moran's I, LISA, Gi*) | analysis/spatial.py | queen contiguity per territory, row-standardised; k=6 nearest as check; 999 permutations, alpha 0.05 (see decisions.md) |
| p2 | Segmentation: group medians, adjusted group differences (HC3), foreign-resident interactions | analysis/descriptive.py + analysis/panel.py | mainland; log change in price-to-income on coast, density, tourist dummies, with district effects and starting level (see decisions.md) |
| p2 | Spillover tests: residual Moran's I, SLX, neighbours' lagged vs lead price-to-income | analysis/panel.py + analysis/spatial.py | same FE model as below plus `spatial_lag` terms, queen weights, 2017-2022 (see decisions.md) |
| p2 | Two-way FE panel regression | analysis/panel.py | log price-to-income on foreign-resident change, other population change, completions (3 y, lagged), share 65+, rentals; municipality + year (or NUTS 3 × year) effects; clustered errors; 2016-2023 (see decisions.md) |
| p2 | Census count against completions, rolled dwelling stock | analysis/stock_reconciliation.py | net change of the census count of dwellings against the completions of the years in between, per decade (2002-2011, 2012-2021; calendar years against March censuses), summed over groups before the ratios are rebuilt; the stock is rolled from the 2021 count along national completions, each decade at its own retention (net addition over completions) so that it meets every census, with a band between the two decades' retentions before 2001 and after 2021 (see decisions.md) |
| p2 | Cross-section of rent changes of new leases | analysis/rents.py + analysis/panel.py (`supply.associations`) | log change of the real rent per m2 2020-2024 on the foreign-resident change (2020-2023), population change, completions 2021-2024, short-term rentals per 1,000 dwellings and the starting rent; mainland, district effects with and without coast and density classes, HC3 errors; the same specification on the real price change as a comparison; reading rule fixed before running (see decisions.md) |
| p3 | Stacked event study, cohort 2×2 check, dose-response | analysis/causal.py | isolated cuts of the municipal IMI rate 2018-2023, NUTS 3 × year comparison, pre-trend test fixed before estimating (see decisions.md, reports/p3_policy.md) |
| p4 | Baselines, ETS, ARIMA, rolling-origin validation | analysis/forecasting.py | national quarterly log real HPI and ownership cost index; naive, seasonal naive, drift, ETS (6 forms) and ARIMA(p,1,q) (p,q ≤ 2, ±drift) chosen by AICc; 36-quarter first window, horizons 1-8 (see decisions.md) |
| p4 | Scenario simulation | simulation/{supply,fiscal,engine}.py | annual national stock-flow model 2025-2035: population and household size give households; completions and levers give usable dwellings; balance pressure, income growth, mortgage rate and a fading other-demand drift (pinned to the ETS forecast for 2028) give real price growth; price-to-income and mortgage burden of the median municipality move with the national paths; low/mid/high parameter ranges with 1,000 triangular draws; assumptions in config/scenarios.yaml (see decisions.md, reports/p4_forecast.md) |
