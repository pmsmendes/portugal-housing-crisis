# Decision Log

Analytic and engineering choices, newest first. One short entry each: what, why, alternatives rejected.

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
