# Research Question Bank

A bank, not a checklist. Start with affordability, supply and demographics (RQ1–RQ4), then
policy and fiscal trade-offs (RQ6–RQ8); forecasting (RQ10) comes last, informed by earlier evidence.

Reference questions by ID (e.g. `RQ2.3`) in notebooks, reports and commits.
**Status:** `—` not started · `wip` in progress · `done` answered · `skip` dropped (say why in docs/decisions.md).
**Where:** notebook or report section that answers it.

## RQ1 — Housing prices and affordability (Phase 1)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ1.1 | How have residential property prices evolved over the past 30 years, nationally and by district and municipality? | wip | `p1_03`, `reports/p1_evidence.md`: national real prices and rents 1988-2025 and price-to-income 1995-2025 (BIS, OECD; 2009 seam untestable); `p1_01`: municipal prices from 2016 only, no district or municipal history before that |
| RQ1.2 | How have purchase and rental prices evolved by property type (T0, T1, T2, T3, T4+)? | partly | `p1_08`, `reports/p1_evidence.md` (kinds of home): prices by rooms are not published; new vs existing premium 24.5% (2019) to 12.3% (2025), 118 municipalities; appraised flats over villas 0.94 (2011) to 1.17 (2025), real appraisals of flats +81% against villas +43%; rents by type not available |
| RQ1.3 | How have prices and rents evolved in real (inflation-adjusted) terms? | done | `p1_01`, `reports/p1_evidence.md` (national 2009-2026, municipal prices 2016-2025, rents 2020-2024) |
| RQ1.4 | How has affordability changed relative to household income and wage growth? | done | `p1_02`: relative to income (PTI, RTI, burden, 2016-2024); `p1_03`: national price-to-income per head 1995-2025 (167 in 2025 vs 142 in 1995, 97 in 2013); wage growth: `p2_09` (national, 1995-2025): real compensation per employee +27% since 2013 against real prices +129%, price-to-wage ratio 1.8 times its 2013 low and 165 in 2025 (2015 = 100), the OECD price-to-income 167 |
| RQ1.5 | How many years of gross household income are needed to buy a typical home in each region? | done | `p1_02`: map, municipality and district tables (2024); levels depend on the income concept |
| RQ1.6 | How does the total cost of buying compare with renting (interest, down payment, taxes, maintenance, other costs)? | done | `p1_04`, `reports/p1_evidence.md` (renting or buying): 2024 owning costs 5.9% of the price a year against a 5.6% rent yield (assumed costs, observed rates); break-even price growth went from -3.9% (2016) to +1.2% (2024), driven by the mortgage rate; owning cheaper with no price gain in 41% of municipalities with a rent; deposit plus buying costs a median 2.5 years of income; rents of new leases 2020-2024 only |
| RQ1.7 | How have mortgage rates and lending conditions affected ownership affordability? | wip | `p1_01`, `p1_02`: rates and the rate effect on the burden; `p2_08`, `reports/p2_explain.md`: the 2021-2023 rate shock raised the payment 73% while real prices rose 9%, so it worsened affordability through the burden, not the price; lending conditions (LTV, term, credit standards) not covered |
| RQ1.8 | How has the gap between advertised and actual transaction prices evolved? | partly | `p1_08`, `reports/p1_evidence.md` (kinds of home): asking prices are not available; bank appraisal over transaction price fell from 1.04 to 0.94 (2016-2025, 189 municipalities with both every year), appraisals neither lead nor follow transactions by a year (correlation 0.32 same year) |

## RQ2 — Housing supply and construction (Phases 1–2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ2.1 | How many residential buildings and dwellings were built over the past 30 years? | done | `p2_05`: 1.53 million new family dwellings completed 1995-2025; 93,000 a year in 1995-2004, 42,000 in 2005-2014, 16,000 in 2015-2025; +111,000 net dwellings 2011-2021 (new construction only) |
| RQ2.2 | How have building permits, construction starts and completions evolved? | done | `p2_05`: completions peaked at 126,000 (2002), fell to 7,100 (2015), 27,300 in 2025; licences 42,000 in 2025 |
| RQ2.3 | Has supply kept pace with population growth and household formation? | done | `p2_05`: 2011-2021 dwellings +1.9%, households +2.6%, population +0.4% (balance +1.4 per 1,000 households), but households fell in 169 municipalities where dwellings still grew; 2021-2023 implied 236,000 new households against 43,300 completions |
| RQ2.4 | How has the housing stock evolved, and what share is primary, secondary and vacant? | partly | `p2_05`: 2021 usual 69.4%, secondary 18.5%, vacant 12.1% (2011: 68.1, 19.3, 12.5); rural 54% usual vs urban 81%; only census years |
| RQ2.5 | How many vacant dwellings could realistically return to residential use (location, condition, renovation cost)? | — | |
| RQ2.6 | How has new-build supply compared with demand for different property types? | — | |
| RQ2.7 | How have construction costs, land availability, planning rules and licensing times affected supply? | — | |
| RQ2.8 | What role could renovation of existing buildings play in easing the shortage? | — | |

## RQ3 — Population, immigration and housing demand (Phases 1–2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ3.1 | How has population evolved over 30 years, split into natural change vs net migration? | done | `p1_07`, `reports/p1_evidence.md` (population change): 1995-2025 +1.42 million = natural -350,000 + net migration +1.56 million + census revision +201,000; deaths above births every year since 2009 (-34,000 in 2025); net migration -108,000 in 2011-2014, +966,000 in 2022-2025 (peak 371,000, 2022); municipalities: 186 of 308 lost people on both counts in 2012-2019, 248 grew only through migrants in 2022-2023; the split is national for the thirty years, municipal for 2011-2023 only; net migration is a residual |
| RQ3.2 | How has the foreign-resident population evolved and where is it located? | done | `p1_05`, `reports/p1_evidence.md`: foreign residents with a title 390,000 (2014) to 1,044,000 (2023), 3.8% to 9.3% of residents, Brazil 35%; 45% live in 10 municipalities, 41% in the district of Lisboa; highest shares in the Algarve and Odemira; titles not the foreign-born, ends 2023 |
| RQ3.3 | What is the municipal-level relationship between population growth, immigration and prices/rents? | partly | `p2_02`: within municipalities, +1 pp of population added through foreign residents goes with +4.3% price-to-income (+3.1% with region-year effects, p < 0.001), against +1.0% (+0.45%, p = 0.10) for other population change; rents not analysed, nationalities not split |
| RQ3.4 | How has the number of households evolved relative to population, and how has household size changed? | partly | `p2_05`: households +2.6% against population +0.4% 2011-2021, persons per household 2.61 to 2.55; 2001 and ageing/single-person split not done |
| RQ3.5 | How have ageing, internal migration and single-person households affected demand? | partly | `p2_11`, `reports/p2_explain.md` (age structure): 65+ share 19.2% to 22.9% (2011-2023), the 25-44 pool 2.99 million to 2.70 (2016) to 2.88; rural interior oldest (31.7%); neither the 25-44 nor the 65+ share goes with the 2016-2023 rise in price-to-income once the foreign-resident change is in (p = 0.15, 0.59), and the 25-44 share tracks migrants (correlation 0.58); internal migration by age and single-person households not available |
| RQ3.6 | To what extent do demand changes explain regional differences in price growth? | partly | `p2_07`: demand (foreign residents, population, households) alone explains 29% of the variation in the 2016-2024 change of price-to-income, but only 0.8 points beyond district, coast and density (which explain 53%): demand differences cannot be told from the regional pattern with these data |

## RQ4 — Regional disparities (Phases 1–2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ4.1 | Which districts and municipalities had the largest price and rent increases? | done | `p1_01`: real growth tables by municipality and district (prices 2016-2025, rents 2020-2024) |
| RQ4.2 | Which regions saw the greatest affordability deterioration relative to local incomes? | done | `p1_02`: change map and tables (PTI 2016-2024) |
| RQ4.3 | Are prices rising faster in major urban centres than in surrounding municipalities? | done | `p2_01`: no significant high-low/low-high outlier in the change in price-to-income; `p2_10`, `reports/p2_explain.md`: real prices 2016-2024 +108% in the 25 municipalities of 100,000+ residents, +63% one border step away, +43% to 45% further out (price-to-income +73%, +26%, +13% to 14%); 9 and 19 log points below the centre within NUTS 3 regions; but Lisboa rose 75% against 112% in the rest of its metropolitan area, Porto 124% against 84% |
| RQ4.4 | Is there evidence of spatial spillovers between neighbouring municipalities? | done | `p2_01`: strong spatial autocorrelation (Moran's I of price-to-income 0.63 to 0.76), mostly regional; `p2_03`: with NUTS 3 × year effects no residual clustering, neighbours' drivers do not matter, and neighbours' past price-to-income (0.18) is matched by a next-year placebo (0.12): weak evidence at best |
| RQ4.5 | Which regions show the largest imbalance between supply and household growth? | done | `p2_05`: 2011-2021 shortfall in Setúbal, Lisboa, Porto (-30 to -23 per 1,000), surplus in the interior; since 2021 implied shortfall almost everywhere, largest in Faro, Beja, Lisboa, Setúbal, Leiria |
| RQ4.6 | How do trends differ coastal vs inland, urban vs rural, tourist vs non-tourist? | done | `p2_01`: LISA clusters; `p2_04`: price-to-income 2016-2024 rose 52% on the coast vs 10% inland, 72% urban vs 7% rural, 47% tourist vs 16%; density matters most, then the coast, tourism adds nothing once those and the district are controlled (proxy classes, mainland) |

## RQ5 — Tourism, foreign investment and the housing market (Phase 2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ5.1 | What is the relationship between short-term rental concentration and local prices and rents? | partly | `p2_02`: mainland rentals per 1,000 dwellings go with +1.7% price-to-income per within-SD, but ~0 within region-year (p = 0.43); registry is today's survivors, 30 island municipalities missing |
| RQ5.2 | How has foreign investment in residential property evolved, and is it associated with higher regional prices? | — | |
| RQ5.3 | How do tourist demand, seasonal occupancy and second homes affect availability of permanent housing? | partly | `p2_06`: second homes are a rural/interior stock (34% of dwellings rural vs 8% urban, 2021) that barely changed 2011-2021 (26.7% to 26.8%); a higher share goes with a smaller rise in price-to-income (-6.3% per sd within district, -3.6% with coast and density), so it marks low-demand places, not pressure; conversions after 2021 and seasonal occupancy not observable |
| RQ5.4 | Can these relationships be separated from income growth, population change and limited construction? | done | `p2_02`: rental association vanishes once region-year effects are added; separation from income, construction, population and foreign residents done; `p2_06`: second homes added; the foreign-resident association is weaker where second homes are common (-2.4 points per 10 points of share, -1.4 with region-year effects), so it is a feature of permanent-housing markets |

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
| RQ7.4 | Who benefits most from IMI/IMT cuts, and how much passes through to lower housing costs vs higher prices? | wip | `p3_02`, `p3_03`, `reports/p3_policy.md`: capitalisation of municipal IMI cuts into prices is inconclusive (pre-trend rejected, interval contains zero and full capitalisation, power 12-21x the benchmark); IMT and the incidence by income group not covered |
| RQ7.5 | How do targeted exemptions (first-time buyers, new build, renovation) compare with broad cuts? | — | |
| RQ7.6 | What is the fiscal impact of alternative property-tax reforms, including vacant-property incentives? | — | |

## RQ8 — Public expenditure and fiscal sustainability (Phase 4)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ8.1 | How much does government spend on housing programmes, rental support, subsidies, tax incentives and public housing? | — | |
| RQ8.2 | How cost-effective are existing programmes (households supported, units delivered)? | — | |
| RQ8.3 | Which expenditure could be reduced or made more efficient without harming vulnerable households or essential services? | — | |
| RQ8.4 | Which mix of spending, tax policy and investment improves affordability within fiscal constraints? | — | |
| RQ8.5 | How would alternative policies affect revenue, expenditure and budget balance over short/medium/long horizons? | wip | `p4_02`, `reports/p4_forecast.md`: direct cost of supply levers and revenue lost to IMI/IMT changes to 2035, national and order-of-magnitude; no behavioural revenue effects |
| RQ8.6 | How should resources be allocated to maximise affordability gains per euro spent? | — | |

## RQ9 — Macroeconomic and financial conditions (Phase 2)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ9.1 | How have wage growth, inflation, unemployment and GDP growth influenced prices and rents? | partly | `p2_09`, `reports/p2_explain.md`: national, annual 1995-2025; a year's real price growth moves +1.0 points per point of real wage growth and −2.1 per point rise in unemployment (R2 0.57; lagged a year: +1.0 and −2.7, still positive after adding momentum), GDP growth adds nothing in the same year and a small negative sign when lagged (−0.5), inflation nothing beyond wages; co-movement not causes, n = 30; rents not analysed |
| RQ9.2 | What is the relationship between interest rates, mortgage lending, household debt and prices? | partly | `p2_08`, `reports/p2_explain.md`: national rate changes do not time the price cycle (−1.0 points of real price growth per pp the year before, interval −3.6 to +1.7; −2.0 in 2003-2013, −0.2 since 2014; placebo as large); lending volume and household debt not covered |
| RQ9.3 | How have credit availability and lending standards affected access to ownership? | — | |
| RQ9.4 | How much of price growth is explained by fundamentals vs investment demand and expectations? | — | |
| RQ9.5 | How have economic crises and monetary-policy shifts affected affordability and construction? | partly | `p2_08`, `reports/p2_explain.md`: five episodes 2003-2026; real prices −19% in the 2008-2013 crisis then +78% as rates fell; completions 73,000 a year before the crisis, 34,000 during, 11,700 in the recovery; the 2022 rate shock hit the burden; descriptive, not causal |

## RQ10 — Forecasting and scenario analysis (Phase 4)
| ID | Question | Status | Where |
|---|---|---|---|
| RQ10.1 | How are prices, rents and affordability likely to evolve over 5–10 years under different scenarios? | wip | `p4_01`, `reports/p4_forecast.md`: national two-year forecast of real prices and the ownership cost index (ETS, validated); `p4_02`, `reports/p4_forecast.md`: 5-10 year scenarios of real prices, price-to-income and the mortgage burden (national, median municipality, first three years pinned to the forecast); rents not modelled |
| RQ10.2 | Which regions are most likely to see further affordability deterioration? | partly | `p4_03`, `reports/p4_forecast.md`: class trends validated on rolling origins (municipal rank correlation 0.41 to 0.43, top-fifth precision 40-44% vs 20% by chance); to 2026 coastal urban places worsen 14.6 points more than the median municipality and inland rural ones 5.5 less (80% intervals exclude zero), only 3 of 24 NUTS 3 regions differ clearly; relative ranking, not a level forecast; 2016-2024 is one boom regime |
| RQ10.3 | How would scenarios for population, immigration, construction, interest rates and income affect future demand? | done | `p4_02`, `reports/p4_forecast.md`: three scenarios and a one-at-a-time sensitivity; net migration moves 2035's price-to-income by 2 years across the scenarios' range, the fade of the other-demand boom by 6 |
| RQ10.4 | What is the estimated affordability impact of more construction, public housing or vacant-home renovation? | done | `p4_02`, `reports/p4_forecast.md`: 0.16 to 0.38 years of income (1% to 3% of the 2035 ratio) for 5,000 to 10,000 homes a year; modelled effects with literature and assumed parameters, not causal estimates |
| RQ10.5 | Which mix of supply-side, demand-side and fiscal policies gives the largest improvement under realistic budgets? | wip | `p4_02`, `reports/p4_forecast.md`: budget search over five levers; supply levers dominate, tax cuts raise the ratio, but the ranking of supply levers depends on assumed unit costs |
| RQ10.6 | How sensitive are projections to assumptions on growth, demographics, construction costs and policy effectiveness? | done | `p4_02`, `reports/p4_forecast.md`: tornado of the 2035 ratio and of a lever's gain, unit-cost check of the lever ranking |

## M — Methodological questions (cross-cutting)
| ID | Question | Status | Where |
|---|---|---|---|
| M1 | Which indicators best capture affordability, and how do conclusions change under alternative definitions? | done | `p1_06`, `reports/p1_evidence.md` (definitions): rankings of places agree across purchase definitions (rank correlation 0.92-1.00), differ for rents (change correlation 0.43); the share worsening is 70-87% and the median rise 17-25% by definition; no single best indicator, so results are reported for price-to-income with the others as checks |
| M2 | How can datasets with different frequencies, geographic coverage and definitions be harmonised? | — | |
| M3 | Which factors are associated with price growth, and which relationships have a credible causal identification strategy? | wip | associations: `p2_02`, `reports/p2_explain.md`; the one design tried (IMI cuts, `p3_02`) fails its pre-trend test, so no relationship has a credible causal identification yet |
| M4 | How can specific policy effects be estimated while accounting for confounders and macro trends? | — | |
| M5 | How reliable are price forecasts under rolling time-based validation vs random splits? | done | `p4_04`, `reports/p4_forecast.md` (validation schemes): one regression scored four ways; random folds overstate skill by 1 to 7 points for real prices and 2 to 25 for the ownership cost index, where at 8 quarters they show 20% skill against -5% in real time; purged leave-one-out is within 5 points of rolling origin, contiguous blocks understate (-5 to -15); one simple model, national quarterly, one regime |
| M6 | How can uncertainty in data, estimates and policy assumptions be carried into projections and cost-benefit analysis? | done | `p4_02`, `reports/p4_forecast.md`: 1,000 joint triangular draws over every behavioural parameter and over the forecast's 80% interval, common random numbers across scenarios and policies; scenario inputs are conditional, not drawn |
