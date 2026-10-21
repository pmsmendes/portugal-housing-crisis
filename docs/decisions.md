# Decision Log

Analytic and engineering choices, newest first. One short entry each: what, why, alternatives rejected.

## 2026-10-21 — INE JSON API as the primary source, NUTS 2024 vintage preferred
- **What:** pull INE series through the JSON API (`pindica.jsp`) by indicator id; take the NUTS 2024 vintage of each indicator and fall back to NUTS 2013 only for years it does not cover.
- **Why:** one API for prices, rents, valuations, income, construction, census, CPI; stable ids; municipal rows for all 308 municipalities.
- **Rejected:** scraping the INE web tables (fragile); dados.gov.pt copies (often stale or archived); splicing methodology breaks silently (see data_quality.md).

## 2026-10-21 — Project scaffold
- **Stack:** Python 3.14 + uv; logic in `src/pthousing`, thin notebooks paired with jupytext; Streamlit app.
- **Unit of analysis:** municipality × year as the main panel; national quarterly series for time-series work.
- **Scope rule:** no deep learning / NLP / complex ML unless it beats simple baselines on a stated metric.
