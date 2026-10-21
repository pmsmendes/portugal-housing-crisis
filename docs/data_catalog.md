# Data Catalog

Registry of every dataset. **Read this before opening any data file or source module.**
`source_id` = module `src/pthousing/data/sources/<source_id>.py` = folder `data/raw/<source_id>/`
= key in `config/sources.yaml`. Caveats go in [data_quality.md](data_quality.md).

**Status:** `candidate` (not yet checked) · `verified` (access + coverage confirmed) · `ingested` (in data/interim) · `dropped`.

## Datasets
| dataset_id | source_id | Content | Geography | Frequency | Years | Interim file | Status |
|---|---|---|---|---|---|---|---|
| ine_hpi | ine | House Price Index (existing / new dwellings) | National only | Quarterly | 1Q2009–2Q2026 (0014765, base 2025) | | verified; raw fetched |
| ine_median_price_sqm | ine | Median sale value per m² (transactions), last-12-months | Municipality | Quarterly | 1Q2016–3Q2021 (0009490, method. 2018) and 4Q2019–1Q2026 (0012234, method. 2022) | | verified (two methods, splice tested); raw fetched |
| ine_median_rent_sqm | ine | Median rent per m² of new leases | Municipality | Semiannual / annual | 2020–2024 (0012598 / 0012600) | | verified (short); raw fetched |
| ine_bank_valuation | ine | Bank appraisal median €/m² by construction type | Municipality | Monthly / annual | Jan 2011–Aug 2026 (0012248) | | verified; raw fetched |
| ine_income | ine | Gross reported income per taxable person, mean and median (IRS) | Municipality | Annual | 2018–2024 (0012748/9, NUTS 2024); 2015–2021 (0009933/4, NUTS 2013) | | verified; raw fetched |
| ine_population | ine | Resident population estimates, natural change, migration | Municipality | Annual | 2011–2023 (0008273; earlier + migration todo) | | verified (partial); raw fetched |
| ine_census | ine | Census: dwellings (primary/secondary/vacant), tenure, households | Municipality / parish | 1991, 2001, 2011, 2021 | 2021 verified (0012517, 0012531); earlier codes todo | | verified (2021 only); raw fetched |
| ine_construction | ine | New family dwellings licensed and completed | Municipality | Annual (monthly licensed) | Licensed 1995–2025 (0000087, 0013235); completed 1995–2025 (0000076, 0013248) | | verified; raw fetched |
| ine_cpi | ine | Consumer Price Index (deflator) | National | Monthly / annual | 1948–2026 (0014640 / 0014642, base 2025) | | verified; raw fetched |
| bp_mortgage | bportugal | Mortgage interest rates (APRC, agreed rate, stocks), new loan volumes | National | Monthly | Jan 2003–Aug 2026 (series 12533714, 12533730, 12519759) | | verified (household debt series todo) |
| eurostat_hpi | eurostat | HPI (prc_hpi_q) and HICP (prc_hicp_aind) for EU comparison | Country | Quarterly / annual | 2005-Q1–2026-Q2 / 1996–2025 | | verified |
| at_imi_imt | at | IMI and IMT revenue and municipal IMI rates | Municipality | Annual | no official source found; third-party IMI rates 2023–2025 | | candidate (unresolved) |
| rnal_al | rnal | Registered short-term rentals (Alojamento Local), with registration date and coordinates | Point / parish / municipality | Snapshot (current registrations) | 111,937 units, `DataRegisto` | | verified (survivorship caveat) |
| caop_boundaries | caop | Municipality boundaries (CAOP 2024), 308 municipalities | Municipality | Annual vintage | 2024 | caop_municipalities.parquet | ingested |
| aima_foreigners | aima | Foreign residents with legal status (ex-SEF, via INE) | Municipality | Annual | 2014–2023 (0010247) | | verified (ends 2023) |

## Lookups (`data/external/`)
| File | Content | Built by | Status |
|---|---|---|---|
| muni_crosswalk.csv | 308 CAOP 2024 municipalities: name, district, territory, NUTS II/III codes in the 2013 and 2024 vintages (codes from INE `geocod` prefixes) | harmonize.write_crosswalk() | built; code changes before 2013 not covered |
| muni_typology.csv | Coastal/inland, urban/rural (INE TIPAU), tourist flag + definition | manual | — |

## Processed panels (`data/processed/`)
| File | Grain | Built by | Status |
|---|---|---|---|
| panel_municipality_year.parquet | muni_code × year | build_panel.py | — |
| national_quarterly.parquet | quarter | build_panel.py | — |
