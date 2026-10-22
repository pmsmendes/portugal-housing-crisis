# Research Question Bank

A bank, not a checklist. Start with affordability, supply and demographics (RQ1–RQ4), then
policy and fiscal trade-offs (RQ6–RQ8); forecasting (RQ10) comes last, informed by earlier evidence.

Reference questions by ID (e.g. `RQ2.3`) in notebooks, reports and commits.
**Status:** `—` not started · `wip` in progress · `done` answered · `skip` dropped (say why in docs/decisions.md).
**Where:** notebook or report section that answers it.

## RQ1 — Housing prices and affordability (Phase 1)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ1.1 | How have residential property prices evolved over the past 30 years, nationally and by district and municipality? | wip | `p1_01`: national index from 2009, municipal prices from 2016 only; no 30-year series yet |
| RQ1.2 | How have purchase and rental prices evolved by property type (T0, T1, T2, T3, T4+)? | — | |
| RQ1.3 | How have prices and rents evolved in real (inflation-adjusted) terms? | done | `p1_01`, `reports/p1_evidence.md` (national 2009-2026, municipal prices 2016-2025, rents 2020-2024) |
| RQ1.4 | How has affordability changed relative to household income and wage growth? | wip | `p1_02`: relative to income (PTI, RTI, burden, 2016-2024); wage growth not covered |
| RQ1.5 | How many years of gross household income are needed to buy a typical home in each region? | done | `p1_02`: map, municipality and district tables (2024); levels depend on the income concept |
| RQ1.6 | How does the total cost of buying compare with renting (interest, down payment, taxes, maintenance, other costs)? | — | |
| RQ1.7 | How have mortgage rates and lending conditions affected ownership affordability? | wip | `p1_01`, `p1_02`: rates and the rate effect on the burden; lending conditions (LTV, term, credit standards) not covered |
| RQ1.8 | How has the gap between advertised and actual transaction prices evolved? | — | |

## RQ2 — Housing supply and construction (Phases 1–2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ2.1 | How many residential buildings and dwellings were built over the past 30 years? | — | |
| RQ2.2 | How have building permits, construction starts and completions evolved? | — | |
| RQ2.3 | Has supply kept pace with population growth and household formation? | — | |
| RQ2.4 | How has the housing stock evolved, and what share is primary, secondary and vacant? | — | |
| RQ2.5 | How many vacant dwellings could realistically return to residential use (location, condition, renovation cost)? | — | |
| RQ2.6 | How has new-build supply compared with demand for different property types? | — | |
| RQ2.7 | How have construction costs, land availability, planning rules and licensing times affected supply? | — | |
| RQ2.8 | What role could renovation of existing buildings play in easing the shortage? | — | |

## RQ3 — Population, immigration and housing demand (Phases 1–2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ3.1 | How has population evolved over 30 years, split into natural change vs net migration? | — | |
| RQ3.2 | How has the foreign-resident population evolved and where is it located? | — | |
| RQ3.3 | What is the municipal-level relationship between population growth, immigration and prices/rents? | partly | `p2_02`: within municipalities, +1 pp of population added through foreign residents goes with +4.3% price-to-income (+3.1% with region-year effects, p < 0.001), against +1.0% (+0.45%, p = 0.10) for other population change; rents not analysed, nationalities not split |
| RQ3.4 | How has the number of households evolved relative to population, and how has household size changed? | — | |
| RQ3.5 | How have ageing, internal migration and single-person households affected demand? | — | |
| RQ3.6 | To what extent do demand changes explain regional differences in price growth? | — | |

## RQ4 — Regional disparities (Phases 1–2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ4.1 | Which districts and municipalities had the largest price and rent increases? | done | `p1_01`: real growth tables by municipality and district (prices 2016-2025, rents 2020-2024) |
| RQ4.2 | Which regions saw the greatest affordability deterioration relative to local incomes? | done | `p1_02`: change map and tables (PTI 2016-2024) |
| RQ4.3 | Are prices rising faster in major urban centres than in surrounding municipalities? | partly | `p2_01`: no significant high-low/low-high outlier in the change in price-to-income; urban centres moved with their surroundings. Price growth itself by city/ring not yet compared |
| RQ4.4 | Is there evidence of spatial spillovers between neighbouring municipalities? | done | `p2_01`: strong spatial autocorrelation (Moran's I of price-to-income 0.63 to 0.76), mostly regional; `p2_03`: with NUTS 3 × year effects no residual clustering, neighbours' drivers do not matter, and neighbours' past price-to-income (0.18) is matched by a next-year placebo (0.12): weak evidence at best |
| RQ4.5 | Which regions show the largest imbalance between supply and household growth? | — | |
| RQ4.6 | How do trends differ coastal vs inland, urban vs rural, tourist vs non-tourist? | partly | `p2_01`: LISA clusters (Algarve, Lisboa, Setúbal, Porto high-high; interior low-low). Group comparisons not yet done |

## RQ5 — Tourism, foreign investment and the housing market (Phase 2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ5.1 | What is the relationship between short-term rental concentration and local prices and rents? | partly | `p2_02`: mainland rentals per 1,000 dwellings go with +1.7% price-to-income per within-SD, but ~0 within region-year (p = 0.43); registry is today's survivors, 30 island municipalities missing |
| RQ5.2 | How has foreign investment in residential property evolved, and is it associated with higher regional prices? | — | |
| RQ5.3 | How do tourist demand, seasonal occupancy and second homes affect availability of permanent housing? | — | |
| RQ5.4 | Can these relationships be separated from income growth, population change and limited construction? | partly | `p2_02`: rental association vanishes once region-year effects are added; separation from income, construction, population and foreign residents done; second homes still missing |

## RQ6 — Housing policies and rent regulation (Phase 3)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ6.1 | Have rent-control measures reduced rents for affected tenants, and how did they affect the wider rental market? | — | |
| RQ6.2 | What are the effects of rent ceilings on rental supply, maintenance, new construction and conversion to other uses? | — | |
| RQ6.3 | Who benefits from rent regulation, and who finds access harder as a result? | — | |
| RQ6.4 | How effective are public housing, rent subsidies and first-home purchase support? | — | |
| RQ6.5 | How do other European countries' housing policies compare, and which could transfer to Portugal? | — | |
| RQ6.6 | Which policy combination improves affordability while minimising unintended consequences? | — | |

## RQ7 — Taxation and public revenue (Phases 3–4)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ7.1 | How have IMI and IMT revenues evolved? | — | |
| RQ7.2 | How would IMI/IMT rate cuts affect central and municipal revenues under different scenarios? | — | |
| RQ7.3 | Could more transactions or construction partly offset initial revenue losses from tax cuts? | — | |
| RQ7.4 | Who benefits most from IMI/IMT cuts, and how much passes through to lower housing costs vs higher prices? | — | |
| RQ7.5 | How do targeted exemptions (first-time buyers, new build, renovation) compare with broad cuts? | — | |
| RQ7.6 | What is the fiscal impact of alternative property-tax reforms, including vacant-property incentives? | — | |

## RQ8 — Public expenditure and fiscal sustainability (Phase 4)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ8.1 | How much does government spend on housing programmes, rental support, subsidies, tax incentives and public housing? | — | |
| RQ8.2 | How cost-effective are existing programmes (households supported, units delivered)? | — | |
| RQ8.3 | Which expenditure could be reduced or made more efficient without harming vulnerable households or essential services? | — | |
| RQ8.4 | Which mix of spending, tax policy and investment improves affordability within fiscal constraints? | — | |
| RQ8.5 | How would alternative policies affect revenue, expenditure and budget balance over short/medium/long horizons? | — | |
| RQ8.6 | How should resources be allocated to maximise affordability gains per euro spent? | — | |

## RQ9 — Macroeconomic and financial conditions (Phase 2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ9.1 | How have wage growth, inflation, unemployment and GDP growth influenced prices and rents? | — | |
| RQ9.2 | What is the relationship between interest rates, mortgage lending, household debt and prices? | — | |
| RQ9.3 | How have credit availability and lending standards affected access to ownership? | — | |
| RQ9.4 | How much of price growth is explained by fundamentals vs investment demand and expectations? | — | |
| RQ9.5 | How have economic crises and monetary-policy shifts affected affordability and construction? | — | |

## RQ10 — Forecasting and scenario analysis (Phase 4)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ10.1 | How are prices, rents and affordability likely to evolve over 5–10 years under different scenarios? | — | |
| RQ10.2 | Which regions are most likely to see further affordability deterioration? | — | |
| RQ10.3 | How would scenarios for population, immigration, construction, interest rates and income affect future demand? | — | |
| RQ10.4 | What is the estimated affordability impact of more construction, public housing or vacant-home renovation? | — | |
| RQ10.5 | Which mix of supply-side, demand-side and fiscal policies gives the largest improvement under realistic budgets? | — | |
| RQ10.6 | How sensitive are projections to assumptions on growth, demographics, construction costs and policy effectiveness? | — | |

## M — Methodological questions (cross-cutting)
| ID | Question | Status | Where |
|---|---|---|---|
| M1 | Which indicators best capture affordability, and how do conclusions change under alternative definitions? | — | |
| M2 | How can datasets with different frequencies, geographic coverage and definitions be harmonised? | — | |
| M3 | Which factors are associated with price growth, and which relationships have a credible causal identification strategy? | — | |
| M4 | How can specific policy effects be estimated while accounting for confounders and macro trends? | — | |
| M5 | How reliable are price forecasts under rolling time-based validation vs random splits? | — | |
| M6 | How can uncertainty in data, estimates and policy assumptions be carried into projections and cost-benefit analysis? | — | |
