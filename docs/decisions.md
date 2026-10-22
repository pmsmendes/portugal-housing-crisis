# Decision Log

Analytic and engineering choices, newest first. One short entry each: what, why, alternatives rejected.

## 2026-10-22 — Spillover tests as fixed-effects regressions (phase 2)
- **What:** three tests with the p2_02 model and queen weights: Moran's I of the residuals; the neighbours' drivers (SLX, `spatial_lag` of each driver); the neighbours' log price-to-income last year, against next year (a placebo that cannot be a cause), with and without the municipality's own lag. Window 2017-2022. Municipality + year and municipality + NUTS 3 × year effects.
- **Why:** `spreg` (spatial-lag / spatial-error panel models) is not installed and installing software was not asked for; these are the space-time and SLX forms that a fixed-effects regression estimates directly, and the lead placebo is a falsification test a spatial-lag model would not give.
- **Reading:** NUTS 3 × year effects absorb spillovers that spread across a whole region, so the test asks whether neighbours matter beyond the regional pattern (conservative). Own-lag coefficients carry Nickell bias with 8 years.
- **Rejected:** a lagged dependent variable as the main specification (bias, and the municipality effect already carries persistence); Arellano-Bond (too few years for a stable GMM); a spatial Durbin model through a new package.

## 2026-10-22 — Foreign residents from AIMA (via INE) in the panel
- **What:** indicator 0010247 (foreign residents with a legal residence title, by NUTS 2013 municipality and nationality, 2014-2023) is fetched through `sources/aima.py`, cleaned into `aima_foreigners` (ten named nationalities, 'other', 'total'; ISO alpha-2 codes in lower case) and added to the panel as `foreign_residents_n` (total) and `foreign_residents_pct` (of the INE resident population). Regressions use the change in foreign residents and the change in the rest of the population, both over last year's population, so the two add up to the population's growth.
- **Why:** it is the only municipal immigration measure available (the INE population series carries no migration split at this level); the additive split lets the regression compare the two parts on one scale.
- **Rejected:** the AIMA migration report PDFs for 2024-2025 (not machine readable here); using levels or shares (they mix a place's size and history with its change; the fixed effects remove most of that anyway); nationality-specific drivers (kept in the interim table for later).
- **Caveat:** the series counts titles at year end and jumps 34% in 2023, possibly partly administrative; one specification stops in 2022 (data_quality.md).

## 2026-10-22 — Fixed-effects regressions of price-to-income (phase 2)
- **What:** outcome log price-to-income; drivers change in foreign residents and change in other population (see the AIMA entry above), completions of the previous three years per 1,000 census-2011 dwellings, share aged 65+, and (mainland) registered short-term rentals per 1,000 census-2011 dwellings. Municipality + year effects; harder variant municipality + NUTS 3 × year effects; errors clustered by municipality, by NUTS 3 region as a check. 2016 to 2023.
- **Why:** price-to-income is the affordability outcome. Income is left out of the drivers because it is inside the outcome, and because it varies little within a municipality (about 1% a year against 15% for prices) and is negatively correlated with price growth across municipalities (-0.31), so a price regression returns a negative income coefficient that reflects convergence, not an effect (shown in the notebook appendix). The 2011 dwelling stock is a fixed denominator so it does not move with construction. Completions are lagged (t-3 to t-1) so they cannot react to year-t prices. Results are reported per within-municipality standard deviation so drivers are comparable.
- **Rejected:** instruments for construction (no credible instrument available here, so effects stay adjusted associations); random effects (municipality effects are correlated with the drivers); a spatial-lag model in this step (residual Moran's I is flagged instead, the spatial model is the next step).
- **Limits kept visible:** residuals stay spatially correlated in some years; second homes are not in the panel (foreign residents are, see the AIMA entry); the rental stock is survivors only.

## 2026-10-21 — Spatial weights and tests (phase 2)
- **What:** queen contiguity, row-standardised, built separately for the mainland, the Azores and Madeira so no link crosses the sea; a municipality with no land neighbour (an island with one municipality) is linked to its 2 nearest in the same territory. Robustness: 6 nearest centroids. Global Moran's I, LISA and Gi* use 999 conditional permutations, two-sided, `alpha` 0.05, fixed seed, one process (`n_jobs=1`).
- **Why:** contiguity is the standard reading of "neighbouring municipality"; per-territory blocks avoid linking Corvo to Mainland by distance; k-nearest shows how much results depend on the weights (it matters for the within-region result: Moran's I 0.20 vs 0.08).
- **Rejected:** inverse-distance weights (dense, dominated by the mainland's size); a multiple-testing correction on LISA (kept as exploratory, stated on the map); the municipality mean as the only fix for regional effects (the NUTS 3 mean is used for the within-region check, FE regressions come next).
- **Reading:** Moran's I is a pattern, not proof of spillovers; Gi* and LISA flag the same municipalities (they are closely related), so their agreement is a consistency check.

## 2026-10-21 — Phase 1 figures and maps
- **Style:** colors come from the validated reference palette of the dataviz method (blue and orange accents with colorblind separation dE 24.7, gray for context, a one-hue blue ramp for levels, a blue-red ramp with a gray midpoint for change). The red arm of the diverging ramp is built at the same OKLCH lightness and chroma as the blue arm. One axis per panel (no dual axes), emphasis form for single stories, a legend whenever two or more series, direct labels only where lines do not collide.
- **Titles are computed from the plotted data** (functions in `viz/charts.py`, tested), so a title cannot disagree with its chart.
- **Maps:** fixed class breaks per indicator (same breaks across years), the Azores and Madeira as insets, hatched fill for municipalities without a published value, counts per class in the legend. Geometry is simplified to 150 m for drawing only.
- **Notebooks** (`notebooks/p1_evidence/`) only call `src/pthousing`; analysis helpers are in `analysis/descriptive.py`. They are committed with outputs so the figures render on GitHub.
- **Comparisons across years use a fixed set of municipalities** (`balanced_sample`, `district_summary`) so that a changing sample is not read as a trend.

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
