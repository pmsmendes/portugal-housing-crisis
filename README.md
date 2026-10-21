# Portugal's Housing Crisis

An evidence-based look at why housing affordability in Portugal has deteriorated over the past three
decades, what role supply, demographics, tourism and regional dynamics play, whether specific housing
policies have worked, and what alternative interventions could achieve — and cost.

> **Status:** phase 1 (evidence) is complete: data pipeline, municipal panels, affordability indicators, maps and trend
> charts — see the [phase 1 report](reports/p1_evidence.md). Phases 2 to 4 follow.

![Price-to-income by municipality, 2024](reports/figures/p1/pti_map_2024.png)

## Questions
1. **Evidence** — How have prices, rents and affordability evolved nationally and by municipality, in real terms?
2. **Explanation** — Which factors (income, population, immigration, construction, tourism, interest rates) are most strongly associated with deteriorating affordability, and do pressures spill over between municipalities?
3. **Policy** — Did a specific housing policy measurably change affordability, and how confident can we be?
4. **Scenarios** — How might affordability evolve under different demographic, economic and policy scenarios, and at what fiscal cost?

## Approach
| Phase | Methods | Output |
|---|---|---|
| 1. Establish the evidence | Data harmonisation, inflation adjustment, affordability indicators, choropleths | [report](reports/p1_evidence.md) |
| 2. Explain the trends | Two-way fixed-effects panel regression, Moran's I / LISA / Gi*, segmentation | [report](reports/p2_explain.md) |
| 3. Evaluate a policy | Difference-in-differences / event study, pre-trend and placebo tests | [report](reports/p3_policy.md) |
| 4. Forecast and simulate | Naïve/ETS/ARIMA with rolling-origin validation, scenario simulator | [report](reports/p4_forecast.md) |

Interactive dashboards (Streamlit): geographic explorer, long-term trends, explanatory analysis, forecast & policy simulator.

## Data
Public Portuguese and European sources (INE, Banco de Portugal, Eurostat, Autoridade Tributária, Turismo de Portugal RNAL, DGT CAOP, AIMA). Full registry: [docs/data_catalog.md](docs/data_catalog.md).

## Reproduce
```bash
uv sync
uv run python scripts/run_pipeline.py
uv run streamlit run app/Home.py
```

## Repository layout
```
config/      dataset sources and scenario assumptions
data/        raw → interim → processed (raw/interim not committed)
docs/        brief, research questions, data catalog, methodology, decisions
src/pthousing/  all analysis code (data, features, analysis, simulation, viz)
notebooks/   one folder per phase, thin notebooks calling src
app/         Streamlit dashboards
reports/     phase write-ups, figures, tables
tests/       unit tests
```
