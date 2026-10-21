# Methodology

Definitions are implemented once in code; this file states them and points to the function.

## Affordability indicators (`src/pthousing/features/affordability.py`)
| Indicator | Definition | Function | Notes |
|---|---|---|---|
| Price-to-income (PTI) | Median sale price per m² × dwelling area / median annual gross income per tax household | `price_to_income` | Years of income to buy a typical home (RQ1.5). Panel column `pti_years` |
| Rent-to-income (RTI) | Median monthly rent per m² of new leases × dwelling area × 12 / median annual income, in % | `rent_to_income_pct` | Panel column `rti_pct`; 2020–2024 only (rents are published from 33 new leases) |
| Mortgage burden | Yearly payments on a loan of `MORTGAGE_LTV` (80%) × dwelling price, `MORTGAGE_TERM_YEARS` (30), at the year's average contract rate on new housing loans / median annual income, in % | `mortgage_burden_pct`, `mortgage_payment_monthly` | Panel column `mortgage_burden_pct`. Fixed-payment (annuity) loan, one national rate for all municipalities |
| Housing vs household growth | (Δ conventional dwellings − Δ private households) per 1,000 households at the start, census 2011 → 2021 | `supply_gap_per_1000` | Panel column `supply_gap_2011_2021_per_1000` (one value per municipality) (RQ2.3, RQ4.5) |

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

### Alternative definitions for robustness (M1)
`pti_years_100sqm`, `pti_years_mean_income` (mean instead of median income, for the 3% of municipality-years where the median is missing and as a check), `rti_pct_100sqm`, `mortgage_burden_pct_100sqm`; other LTV, term and rate choices through the function arguments.

## Real values (`src/pthousing/data/harmonize.py`)
- Deflator: INE CPI, all items, national (annual `annual_deflator`, quarterly `quarterly_deflator`), constant euros of `BASE_YEAR` (2024) in `config.py`. Factor = CPI(base) / CPI(period); `to_real` applies it.
- Columns: nominal `*_eur`, real `*_eur_real`; the factor is stored as `deflator_to_base_year`. Quarterly factors use the mean of the quarter's three monthly indices and the mean of the 12 months of the base year.
- Index columns keep their own base (`_b2025`, `_b2015`); real indices are nominal × deflator (e.g. `hpi_total_real_b2025`).

## Panels (`src/pthousing/data/build_panel.py`, files in `data/processed/`)
| Panel | Grain | Content |
|---|---|---|
| `panel_municipality_year` | 308 municipalities × 1995–2025 | Prices (existing / new / total), rents, bank valuations, income, licensed and completed dwellings, population and 65+ share, census 2011/2021 stock columns, short-term rental units (mainland), mortgage rates, real values, indicators |
| `national_quarterly` | quarter, 2005Q1 onwards | INE HPI (total / new / existing), Eurostat HPI for Portugal, peers and EU27, CPI and deflator, real HPI, mortgage rates and volume, monthly payment on a 100,000 EUR loan |

Missing means "not published / not covered", never zero: prices from 2016, rents 2020–2024, income 2015–2024, population 2011–2023, short-term rentals NaN for the island municipalities.

## Geography
- Unit of analysis: municipality (308), key `muni_code` (INE DICOFRE, 4-digit string).
- Boundary/definition changes handled through `data/external/muni_crosswalk.csv` (NUTS vintages, `valid_from_year` for Vizela, Trofa and Odivelas).

## Models
| Phase | Method | Module | Spec |
|---|---|---|---|
| p2 | Spatial autocorrelation (Moran's I, LISA, Gi*) | analysis/spatial.py | queen contiguity per territory, row-standardised; k=6 nearest as check; 999 permutations, alpha 0.05 (see decisions.md) |
| p2 | Two-way FE panel regression | analysis/panel.py | _tbd_ |
| p3 | DiD / event study | analysis/causal.py | _tbd_ |
| p4 | Baselines, ETS, ARIMA, rolling-origin CV | analysis/forecasting.py | _tbd_ |
| p4 | Scenario simulation | simulation/engine.py | assumptions in config/scenarios.yaml |
