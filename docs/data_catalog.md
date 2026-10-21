# Data Catalog

Registry of every dataset. **Read this before opening any data file or source module.**
`source_id` = module `src/pthousing/data/sources/<source_id>.py` = folder `data/raw/<source_id>/`
= key in `config/sources.yaml`. Caveats go in [data_quality.md](data_quality.md).

**Status:** `candidate` (not yet checked) · `verified` (access + coverage confirmed) · `ingested` (in data/interim) · `dropped`.

## Datasets
| dataset_id | source_id | Content | Geography | Frequency | Years | Interim file | Status |
|---|---|---|---|---|---|---|---|
| ine_hpi | ine | House Price Index | National / NUTS II | Quarterly | 2009– | | candidate |
| ine_median_price_sqm | ine | Median sale value per m² (transactions) | Municipality | Quarterly | 2016– | | candidate |
| ine_median_rent_sqm | ine | Median rent per m² of new leases | Municipality | Semiannual | 2017– | | candidate |
| ine_bank_valuation | ine | Bank appraisal value by typology (T0–T4+) | Municipality / NUTS III | Monthly | 2008– | | candidate |
| ine_income | ine | Household income (IRS-based taxable income) | Municipality | Annual | 2015– | | candidate |
| ine_population | ine | Resident population estimates, natural change, migration | Municipality | Annual | 1991– | | candidate |
| ine_census | ine | Census: dwellings (primary/secondary/vacant), households, household size | Municipality / parish | 1991, 2001, 2011, 2021 | | | candidate |
| ine_construction | ine | Building permits, completions, dwellings licensed | Municipality | Monthly / Annual | 1995– | | candidate |
| ine_cpi | ine | Consumer Price Index (deflator) | National | Monthly | 1990– | | candidate |
| bp_mortgage | bportugal | Mortgage interest rates, new housing loans, household debt | National | Monthly | 2003– | | candidate |
| eurostat_hpi | eurostat | HPI and HICP for EU comparison | Country | Quarterly | 2005– | | candidate |
| at_imi_imt | at | IMI and IMT revenue and municipal IMI rates | Municipality | Annual | | | candidate |
| rnal_al | rnal | Registered short-term rentals (Alojamento Local) | Municipality / point | Snapshot | 2014– | | candidate |
| caop_boundaries | caop | Municipality boundaries (CAOP) | Municipality | Annual vintage | | | candidate |
| aima_foreigners | aima | Foreign residents (ex-SEF statistical reports) | Municipality | Annual | 2008– | | candidate |

## Lookups (`data/external/`)
| File | Content | Built by | Status |
|---|---|---|---|
| muni_crosswalk.csv | Municipality codes across boundary/code changes, district, NUTS II/III (2013 and 2024 versions) | manual + harmonize.py | — |
| muni_typology.csv | Coastal/inland, urban/rural (INE TIPAU), tourist flag + definition | manual | — |

## Processed panels (`data/processed/`)
| File | Grain | Built by | Status |
|---|---|---|---|
| panel_municipality_year.parquet | muni_code × year | build_panel.py | — |
| national_quarterly.parquet | quarter | build_panel.py | — |
