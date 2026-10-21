# Decision Log

Analytic and engineering choices, newest first. One short entry each: what, why, alternatives rejected.

## 2026-10-21 — Project scaffold
- **Stack:** Python 3.14 + uv; logic in `src/pthousing`, thin notebooks paired with jupytext; Streamlit app.
- **Unit of analysis:** municipality × year as the main panel; national quarterly series for time-series work.
- **Scope rule:** no deep learning / NLP / complex ML unless it beats simple baselines on a stated metric.
