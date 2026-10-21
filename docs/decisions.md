# Decision Log

Analytic and engineering choices, newest first. One short entry each: what, why, alternatives rejected.

## 2026-10-21 — Panels, deflator and affordability indicators
- **What:** `build_panel.py` writes `panel_municipality_year` (308 × 1995–2025) and `national_quarterly` (2005Q1+); `harmonize.annual_deflator` / `quarterly_deflator` / `to_real` deflate to 2024 euros; `features/affordability.py` holds PTI, RTI, mortgage burden and the supply gap, defined in `docs/methodology.md`.
- **Dwelling size:** INE prices and rents are per m², so a dwelling is the per-m² value times the census mean useful area of the municipality (interpolated between 2011 and 2021). It describes occupied homes and biases levels upwards, hence the fixed 100 m² benchmark variants. Rejected: one invented national size without a source.
- **Annual price = 4th-quarter value** of INE's last-12-months median (no averaging of overlapping windows).
- **Mortgage payment rate = agreed rate on new floating loans** (BPstat), not the APRC (1.1–1.8 pp higher since 2015, includes fees and insurance). LTV 80% and 30 years are assumptions in `config.py`; the effect of changing them is tabulated in methodology.md (2024 median burden 40–57%).
- **Supply gap** uses all conventional dwellings against private households between the 2011 and 2021 censuses, per 1,000 households at the start; annual household counts do not exist.
- **Short-term rentals** in the panel: islands are NaN, mainland municipalities without units are 0.
- **Census size filters**: the 2011 and 2021 dwelling and household tables exceed INE's row limit, so only the totals of the dimensions we do not split by are requested (`INE_FILTERED`).

## 2026-10-21 — Interim tables and validation
- **What:** `interim.py` builds one parquet per dataset in `data/interim/` (16 tables); `validate.py` checks them with pandera schemas (types, ranges, categories, unique keys, no unexpected columns), grid checks (308 municipalities in every period), consistency checks (totals = sum of parts, source publication rules) and cross-source checks (INE vs Eurostat HPI and CPI/HICP). `scripts/run_pipeline.py` runs download, build and validate.
- **Conventions:** municipal tables keep the full grid, with suppressed cells NaN (not dropped, not zero); nominal values, unit in the column suffix; index base in the column name (`_b2025`, `_b2015`); splices made at table-build time (prices 2018 -> 2022 method; income 2013 -> 2024 vintage; construction masks pre-creation years); rents are annual only (the semi-annual series is not built).
- **Thresholds come from the data:** a check is written for what the source guarantees, not tuned to pass. Examples: completions size split must never exceed the total and, from 2003, miss under 0.1% of dwellings (measured 0.008%); a published rent needs at least 33 new leases.
- **Rejected:** dropping suppressed rows (hides the grid and the coverage), one check per file inside the builders (validation stays separate and re-runnable).

## 2026-10-21 — Rates, Eurostat and RNAL ingestion
- **What:** one JSON-stat parser (`sources/jsonstat.py`) for Eurostat and BPstat; each BPstat series stored with its metadata and the dataset response filtered to it (dataset and domain are looked up from the series id, nothing hardcoded); Eurostat queries are parameter dicts in `sources.yaml` with a peer set (ES, IT, FR, DE, IE, EU27). RNAL is downloaded in pages and kept as a dated snapshot.
- **Why:** the registry only lists live registrations, so history can only be built by keeping snapshots from now on. Business names and street addresses are not requested or stored (not needed; the project is public).
- **Validated:** Eurostat PT HPI equals INE's HPI rebased to 2015 (max diff 0.025); HICP vs CPI within 1.3%.
- **Rejected:** point-level analysis of RNAL (82% of coordinates unreliable), a hand-written HTTP client per source.

## 2026-10-21 — Municipality key and crosswalk
- **What:** the 308 CAOP 2024 municipalities (4-digit `dtmn`) are the master list; `muni_code` is the key everywhere. NUTS III/II codes per vintage in `data/external/muni_crosswalk.csv` are read from the 7-char INE `geocod` prefix of one NUTS 2013 series (0009490) and one NUTS 2024 series (0012600). INE municipality rows are kept only if their code is in the crosswalk (`keep_municipalities`); the rest is reported by `unmatched_codes`.
- **Why:** INE changes NUTS III codes between vintages (176 of 308 municipalities differ 2013 vs 2024) but the 4-digit municipality code is stable, so the prefix must never be part of a key. Deriving the codes from INE avoids typing a 308-row table by hand.
- **Islands:** CAOP geometries are reprojected to EPSG:3763 for one common CRS; this distorts island geometry, so areas come from CAOP `area_ha`, not from the geometry.
- **1990s (checked on the 1995 licensing series):** INE returns all 308 current municipalities for every year from 1995 with no extra or retired codes, but does not back-cast: Vizela and Trofa are exact zeros until 1998, Odivelas until 1999 (parents Guimarães, Santo Tirso/Maia, Loures still hold the territory). Crosswalk column `valid_from_year` (first year with data, from the first non-zero licensing year; to be confirmed against the creation laws) and `harmonize.mask_pre_creation` turn those zeros into NaN.
- **Splices:** price series — 2018 method until 3Q2019, 2022 method from 4Q2019 (median overlap ratio 1.002); income — 2013 vintage 2015–2017, 2024 vintage from 2018 (identical on the overlap).

## 2026-10-21 — INE JSON API as the primary source, NUTS 2024 vintage preferred
- **What:** pull INE series through the JSON API (`pindica.jsp`) by indicator id; take the NUTS 2024 vintage of each indicator and fall back to NUTS 2013 only for years it does not cover.
- **Why:** one API for prices, rents, valuations, income, construction, census, CPI; stable ids; municipal rows for all 308 municipalities.
- **Rejected:** scraping the INE web tables (fragile); dados.gov.pt copies (often stale or archived); splicing methodology breaks silently (see data_quality.md).

## 2026-10-21 — Project scaffold
- **Stack:** Python 3.14 + uv; logic in `src/pthousing`, thin notebooks paired with jupytext; Streamlit app.
- **Unit of analysis:** municipality × year as the main panel; national quarterly series for time-series work.
- **Scope rule:** no deep learning / NLP / complex ML unless it beats simple baselines on a stated metric.
