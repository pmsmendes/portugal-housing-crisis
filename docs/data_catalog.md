# Data Catalog

Registry of every dataset. **Read this before opening any data file or source module.**
`source_id` = module `src/pthousing/data/sources/<source_id>.py` = folder `data/raw/<source_id>/`
= key in `config/sources.yaml`. Caveats go in [data_quality.md](data_quality.md).

**Status:** `candidate` (not yet checked) · `verified` (access + coverage confirmed) · `ingested` (cleaned table in data/interim, passes `validate.py`) · `dropped`.

## Datasets
| dataset_id | source_id | Content | Geography | Frequency | Years | Interim file | Status |
|---|---|---|---|---|---|---|---|
| ine_hpi | ine | House Price Index (existing / new dwellings) | National only | Quarterly | 1Q2009–2Q2026 (0014765, base 2025) | ine_hpi.parquet | ingested |
| ine_median_price_sqm | ine | Median sale value per m² (transactions), last-12-months | Municipality | Quarterly | 1Q2016–3Q2021 (0009490, method. 2018) and 4Q2019–1Q2026 (0012234, method. 2022) | ine_median_price_sqm.parquet | ingested (two methods, splice tested) |
| ine_median_rent_sqm | ine | Median rent per m² of new leases | Municipality | Semiannual / annual | 2020–2024 (0012598 / 0012600) | ine_median_rent_sqm.parquet | ingested (short) |
| ine_bank_valuation | ine | Bank appraisal median €/m² by construction type | Municipality | Monthly / annual | Jan 2011–Aug 2026 (0012248) | ine_bank_valuation.parquet, ine_bank_valuation_annual.parquet | ingested |
| ine_income | ine | Gross reported income per taxable person, mean and median (IRS) | Municipality | Annual | 2018–2024 (0012748/9, NUTS 2024); 2015–2021 (0009933/4, NUTS 2013) | ine_income.parquet | ingested |
| ine_population | ine | Resident population estimates, natural change, migration | Municipality | Annual | 2011–2023 (0008273; earlier + migration todo) | ine_population.parquet | ingested (partial) |
| ine_census | ine | Census: dwellings (primary/secondary/vacant), tenure, households, mean dwelling area | Municipality / parish | 1991, 2001, 2011, 2021 | 2011 and 2021 stock and area (0006304, 0012502, 0006457, 0012856, 0006988, 0012518); 2021 vacancy and tenure (0012517, 0012531); 2001 and 1991 todo | ine_census.parquet, ine_census_stock.parquet | ingested (2011 and 2021) |
| ine_construction | ine | New family dwellings licensed and completed | Municipality | Annual (monthly licensed) | Licensed 1995–2025 (0000087, 0013235); completed 1995–2025 (0000076, 0013248) | ine_construction.parquet | ingested |
| ine_cpi | ine | Consumer Price Index (deflator) | National | Monthly / annual | 1948–2026 (0014640 / 0014642, base 2025) | ine_cpi.parquet, ine_cpi_monthly.parquet | ingested |
| bp_mortgage | bportugal | Mortgage interest rates (APRC, agreed rate, stocks), new loan volumes | National | Monthly | Jan 2003–Aug 2026 (series 12533714, 12533730, 12519759, 12533719); fixed-rate median from Dec 2018 (12710738) | bp_mortgage.parquet | ingested (household debt series todo) |
| eurostat_hpi | eurostat | HPI (prc_hpi_q) and HICP (prc_hicp_aind) for EU comparison | Country | Quarterly / annual | PT 2008-Q1–2026-Q2 (EU27 from 2005, IT from 2010) / PT 1996–2025 | eurostat_hpi.parquet, eurostat_hicp.parquet | ingested |
| at_imi_rates | at | Municipal urban IMI rate per tax year (Portal das Finanças "Taxas do Município"), with a flag for parish-specific rates | Municipality | Annual | 2012–2025 (308 municipalities every year; portal offers 1989–2026) | at_imi_rates.parquet | ingested (raw HTML snapshot kept; parish-link and 2025 caveats in data_quality) |
| at_imi_imt | at | IMI and IMT revenue | Municipality | Annual | no official source found | | candidate (unresolved) |
| rnal_al | rnal | Registered short-term rentals (Alojamento Local), with registration date and coordinates | Point / parish / municipality | Snapshot (current registrations) | 111,937 registered units on 2026-10-21 (mainland only), `DataRegisto` | rnal_al.parquet | ingested (mainland only, survivorship caveat) |
| caop_boundaries | caop | Municipality boundaries (CAOP 2024), 308 municipalities | Municipality | Annual vintage | 2024 | caop_municipalities.parquet | ingested |
| bis_spp | bis | BIS residential property price index, nominal and real (CPI-deflated), index 2010=100 and y/y % | National | Quarterly | 1988-Q1–2026-Q1 (WS_SPP, key Q.PT..); equals INE's index exactly from 2009 | bis_spp.parquet | ingested (pre-2009 source not stated; join untestable) |
| oecd_house_prices | oecd | OECD analytical house price indicators: nominal and real house price index, rent prices, price-to-rent and price-to-income (2015=100) and the ratios against their long-term average | National | Annual | HPI and price-to-rent 1988–2025; price-to-income 1995–2025; rent prices 1959–2025 (DSD_AN_HOUSE_PRICES) | oecd_house_prices.parquet | ingested (own real series not used: different deflator) |
| aima_foreigners | aima | Foreign residents with a legal residence title on 31 December (ex-SEF, via INE), by nationality | Municipality | Annual | 2014–2023 (0010247, NUTS 2013) | aima_foreigners.parquet | ingested (ends 2023) |

## Interim tables (`data/interim/`, built by `interim.py`, checked by `validate.py`)
Full 308-municipality grid for municipal tables; suppressed cells are NaN, never zero. Values are nominal.

| File | Grain (key) | Value columns |
|---|---|---|
| ine_median_price_sqm | muni_code × period_start × category (total / new / existing) | price_sqm_eur, sales_12m_n; `method` 2018 until 3Q2019, 2022 after |
| ine_median_rent_sqm | muni_code × year (2020–2024) | rent_sqm_eur, new_leases_n |
| ine_income | muni_code × year (2015–2024) | income_mean_eur, income_median_eur; `vintage` 2013 / 2024 |
| ine_construction | muni_code × year × size (total, br_0_1, br_2, br_3, br_4plus) | licensed_n, completed_n (1995–2025; NaN before Vizela / Trofa / Odivelas existed) |
| ine_bank_valuation | muni_code × period_start (month) × type (total / flats / villas) | valuation_sqm_eur |
| ine_bank_valuation_annual | muni_code × year × type | valuation_sqm_eur |
| ine_census | muni_code (census_year 2021) | vacant_dwellings_pct, occupied_dwellings_n, owner_occupied_n, rented_n, other_tenure_n |
| ine_population | muni_code × year × sex × age_group (totals included) | population_n |
| aima_foreigners | muni_code × year (2014–2023) × nationality (br, cn, cv, gb, gw, md, ro, st, ua, ao, other, total) | foreign_residents_n (total = sum of the others) |
| ine_cpi / ine_cpi_monthly | year / period_start | cpi_index_b2025 (2025 = 100) |
| ine_hpi | period_start × category | hpi_index_b2025 (2025 = 100), national |
| bp_mortgage | date (month end) | mortgage_aprc_new_pct, mortgage_rate_new_lt1y_pct, mortgage_rate_stock_gt5y_pct, mortgage_new_lt1y_volume_eur_m, mortgage_rate_new_fixed_p50_pct |
| eurostat_hpi | geo × period_start | hpi_index_b2015 (PT, ES, IT, FR, DE, IE, EU27) |
| eurostat_hicp | geo × year | hicp_index_b2015 (PT, EU27) |
| bis_spp | period_start (quarter) | hpi_nominal_b2010, hpi_real_b2010 (2010 = 100) |
| oecd_house_prices | year (1959–2025) | hpi_nominal_b2015, hpi_real_b2015, rent_index_b2015, price_to_rent_b2015, price_to_income_b2015, price_to_rent_std, price_to_income_std (the last two: 100 = long-term average) |
| rnal_al | rnal_n (one row per registered unit) | registered, opened, modality, guests_n, muni_code, parish_code, geo_reliability, lon, lat (mainland snapshot) |
| ine_census_stock | muni_code × census_year (2011, 2021) | dwellings_n, dwellings_usual_n, dwellings_secondary_n, dwellings_vacant_n, households_n, dwelling_area_sqm |
| at_imi_rates | muni_code × year (2012–2025, tax year) | imi_urban_pct (NaN where no single rate, 83 of 4,312), imi_rustic_pct (always 0.8), parish_rates, deduction_link |
| caop_municipalities | muni_code | names, district, NUTS 2024 names, area_ha, parishes_n, geometry (EPSG:3763) |

## Lookups (`data/external/`)
| File | Content | Built by | Status |
|---|---|---|---|
| muni_crosswalk.csv | 308 CAOP 2024 municipalities: name, district, territory, NUTS II/III codes in the 2013 and 2024 vintages (codes from INE `geocod` prefixes) | harmonize.write_crosswalk() | built; code changes before 2013 not covered |
| muni_typology.csv | 308 municipalities: coast / estuary / inland (CAOP shoreline segments), urban / intermediate / rural (2021 residents per km²: ≥ 500, 100 to 500, < 100; a proxy, not the INE TIPAU), tourist / other / unknown (≥ 25 registered short-term rentals per 1,000 dwellings; mainland only), second-home share 2021 | typology.build() (run by scripts/run_pipeline.py) | built |

## Processed panels (`data/processed/`)
| File | Grain | Built by | Status |
|---|---|---|---|
| panel_municipality_year.parquet | muni_code × year (308 × 1995–2025, 60 columns; includes `foreign_residents_n` 2014–2023 and `foreign_residents_pct`, and from the IMI rates `imi_urban_pct`, `imi_change_pp`, `imi_parish_rates`, `imi_deduction_link` for 2012–2025) | build_panel.py | built, validated |
| national_quarterly.parquet | quarter (2005Q1–2026Q2, 25 columns) | build_panel.py | built, validated |
| national_annual_long.parquet | year (1988–2025, 10 columns): BIS annual price index rebased to 2015, real index (project CPI), CPI, OECD rent, price-to-rent and price-to-income | build_panel.py | built, validated |
| municipalities.geojson | 308 CAOP 2024 outlines (`muni_code`, `muni_name`), simplified to 400 m, 4-decimal coordinates, ~380 kB; only for the dashboard map | maps.export_web_geometry() (run by scripts/run_pipeline.py) | built |
