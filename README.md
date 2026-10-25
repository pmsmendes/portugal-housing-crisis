# Portugal's Housing Crisis

An evidence-based look at why housing affordability in Portugal has deteriorated over the past three
decades, what role supply, demographics, tourism and regional dynamics play, whether specific housing
policies have worked, and what alternative interventions could achieve — and cost.

> **Status:** all four phases are done: evidence ([report](reports/p1_evidence.md)), explanation ([report](reports/p2_explain.md)), one policy test ([report](reports/p3_policy.md)) and forecasts with a scenario simulator ([report](reports/p4_forecast.md)). The dashboard has five pages: landing, geographic map, trends, explanatory and simulator. Research questions and their status: [docs/research_questions.md](docs/research_questions.md).

![Price-to-income by municipality, 2024](reports/figures/p1/pti_map_2024.png)

## What it found
**Evidence (phase 1)**
- Real house prices have more than doubled since 2013; Portugal's nominal index rose 3.0 times against 1.7 for the EU27.
- The median municipality needs 9.5 years of income to buy a home (8.0 in 2016); the 90th percentile needs 18 (12 in 2016).
- The mortgage rate explains most of the recent jump in the burden: the median payment burden went from 28% to 45% of income, and would be 33% had rates stayed at their 2016 level.
- Pressure is concentrated in the Lisboa area and the Algarve; interior districts stayed near 5 years of income.

**Explanation (phase 2)**
- Geography accounts for most of where affordability worsened: district, coast and density explain 53% of the variation in the 2016-2024 change of price-to-income across mainland municipalities; demand, supply, tourism and second homes add under two points.
- Since 2013 real prices rose 129% against 27% for real wages; wages and falling rates account for the 2013-2021 rise, but not 2021-2025, when about 50 log points of the price rise are left over.
- That rise was not borrowed: real housing credit fell 27% from 2013 to 2024 while real prices rose 98%, and credit growth follows price growth rather than leading it.
- Building collapsed from 93,000 dwellings a year (1995-2004) to 16,000 (2015-2025); since 2021 implied new households far exceed completions.
- Foreign residents go with rising price-to-income within municipalities, mainly Brazilians and Lusophone Africans, and the pattern is largely a marker of where they settled.

**Policy (phase 3)** — cuts in the municipal property-tax rate (IMI): the effect on prices cannot be told from zero or from full capitalisation, and the design fails its pre-trend test, so the result is inconclusive, not causal.

**Forecasts and scenarios (phase 4)** — exponential smoothing beats naive baselines on rolling-origin validation; random-fold validation overstates skill. In the simulator, 5,000 to 10,000 extra homes a year lower the 2035 price-to-income ratio by only 1% to 3%.

All results are associations or conditional scenarios with stated limits (short municipal history, one national mortgage rate, assumed loan terms); each report has a limitations section.

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
| 4. Forecast and simulate | Naïve/ETS/ARIMA with rolling-origin validation, scenario simulator, regional outlook | [report](reports/p4_forecast.md) |

Interactive dashboards (Streamlit, `uv run streamlit run app/Home.py`): a **geographic** explorer (municipality map of any indicator, level or change between two years, with rankings), **trends** (national price index and rates, a municipality against all others, group medians), **explanatory** (what accounts for where affordability worsened, and the policy test) and the forecast & policy **simulator**. They read only the committed processed data and report tables.

## Data
Public Portuguese and European sources (INE, Banco de Portugal, Eurostat, BIS, OECD, Autoridade Tributária, Turismo de Portugal RNAL, DGT CAOP, AIMA). Full registry: [docs/data_catalog.md](docs/data_catalog.md).

## Reproduce
```bash
uv sync
uv run python scripts/run_pipeline.py   # downloads sources, builds interim tables and the processed panels
uv run pytest
```
Requires Python 3.14 and [uv](https://docs.astral.sh/uv/). Notebooks are [jupytext](https://jupytext.readthedocs.io/) pairs (`.py` is the source, `.ipynb` carries the rendered outputs).

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
