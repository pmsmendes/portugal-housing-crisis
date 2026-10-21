# Methodology

Definitions are implemented once in code; this file states them and points to the function.

## Affordability indicators (`src/pthousing/features/affordability.py`)
| Indicator | Definition | Function | Notes |
|---|---|---|---|
| Price-to-income (PTI) | Median dwelling price / median annual gross household income | | Years of income to buy a typical home (RQ1.5) |
| Rent-to-income (RTI) | Annual median rent / median annual household income | | |
| Mortgage burden | Annual payment on typical loan (LTV, term, rate) / income | | Assumptions in decisions.md |
| Housing vs household growth | Δ dwellings − Δ households, per 1,000 households | | Supply–demand gap (RQ2.3, RQ4.5) |

Alternative definitions for robustness (M1): _to be listed_.

## Real values (`src/pthousing/data/harmonize.py`)
- Deflator: INE CPI (national), constant euros of `BASE_YEAR` in `config.py`.
- Columns: nominal `*_eur`, real `*_eur_real`.

## Geography
- Unit of analysis: municipality (308), key `muni_code` (INE DICOFRE, 4-digit string).
- Boundary/definition changes handled through `data/external/muni_crosswalk.csv`.

## Models
| Phase | Method | Module | Spec |
|---|---|---|---|
| p2 | Spatial autocorrelation (Moran's I, LISA, Gi*) | analysis/spatial.py | weights: _tbd_ |
| p2 | Two-way FE panel regression | analysis/panel.py | _tbd_ |
| p3 | DiD / event study | analysis/causal.py | _tbd_ |
| p4 | Baselines, ETS, ARIMA, rolling-origin CV | analysis/forecasting.py | _tbd_ |
| p4 | Scenario simulation | simulation/engine.py | assumptions in config/scenarios.yaml |
