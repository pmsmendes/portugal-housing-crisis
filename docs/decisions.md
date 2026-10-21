# Decision Log

Analytic and engineering choices, newest first. One short entry each: what, why, alternatives rejected.

## 2026-10-21 — Municipality key and crosswalk
- **What:** the 308 CAOP 2024 municipalities (4-digit `dtmn`) are the master list; `muni_code` is the key everywhere. NUTS III/II codes per vintage in `data/external/muni_crosswalk.csv` are read from the 7-char INE `geocod` prefix of one NUTS 2013 series (0009490) and one NUTS 2024 series (0012600). INE municipality rows are kept only if their code is in the crosswalk (`keep_municipalities`); the rest is reported by `unmatched_codes`.
- **Why:** INE changes NUTS III codes between vintages (176 of 308 municipalities differ 2013 vs 2024) but the 4-digit municipality code is stable, so the prefix must never be part of a key. Deriving the codes from INE avoids typing a 308-row table by hand.
- **Islands:** CAOP geometries are reprojected to EPSG:3763 for one common CRS; this distorts island geometry, so areas come from CAOP `area_ha`, not from the geometry.
- **Open:** municipalities created or re-coded in the 1990s are not handled; check INE series that start in 1995 (licensing, completions) before building the long panel.

## 2026-10-21 — INE JSON API as the primary source, NUTS 2024 vintage preferred
- **What:** pull INE series through the JSON API (`pindica.jsp`) by indicator id; take the NUTS 2024 vintage of each indicator and fall back to NUTS 2013 only for years it does not cover.
- **Why:** one API for prices, rents, valuations, income, construction, census, CPI; stable ids; municipal rows for all 308 municipalities.
- **Rejected:** scraping the INE web tables (fragile); dados.gov.pt copies (often stale or archived); splicing methodology breaks silently (see data_quality.md).

## 2026-10-21 — Project scaffold
- **Stack:** Python 3.14 + uv; logic in `src/pthousing`, thin notebooks paired with jupytext; Streamlit app.
- **Unit of analysis:** municipality × year as the main panel; national quarterly series for time-series work.
- **Scope rule:** no deep learning / NLP / complex ML unless it beats simple baselines on a stated metric.
