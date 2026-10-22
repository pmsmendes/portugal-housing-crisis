# Phase 2 — Explain the trends

Why did affordability deteriorate, and where? This phase moves from description to association; nothing here is a
causal claim. Figures: `reports/figures/p2/`, tables: `reports/tables/p2/`, notebooks: `notebooks/p2_explain/`
(`p2_01_spatial_autocorrelation`). Methods: [methodology](../docs/methodology.md), choices:
[decisions](../docs/decisions.md).

**Done so far:** spatial autocorrelation (RQ4.3, RQ4.4, RQ4.6 partly) and fixed-effects regressions (RQ3.3, RQ5.1,
RQ5.4 partly). **Still to do:** a spatial lag test of spillovers, immigration, segmentation, supply against demand.

## Key findings

1. **Neighbouring municipalities resemble each other, and more every year.** Moran's I of price-to-income rose from
   0.63 (2016) to 0.76 (2024) and that of the real price per m² from 0.65 to 0.75, while that of median income fell
   from 0.61 to 0.56. All are significant (permutation p ≤ 0.001) and 6-nearest-neighbour weights agree. The
   geography of prices is concentrating faster than the geography of incomes.
2. **The deterioration is clustered.** Moran's I of the change in price-to-income 2016 to 2024 is 0.72 (0.67 with
   k-nearest weights), above that of price growth (0.45) or income growth (0.53) alone.
3. **Most of it is regional.** With each NUTS 3 sub-region's mean removed, Moran's I falls to 0.20 (queen) or 0.08
   (6 nearest), still significant. The pattern is mainly coast against interior and metropolitan areas against the
   rest; only a smaller, weights-dependent part is clustering within regions.
4. **The worst-hit clusters** (45 high-high municipalities) are in the districts of Faro (13), Lisboa (11),
   Setúbal (8) and Porto (6), with three in Madeira; Lisboa, Porto, Cascais and Faro are among them. The 50
   low-low municipalities are the interior (Viseu, Guarda, Bragança, Castelo Branco).
5. **No urban islands.** No municipality is a significant high-low or low-high outlier, so the large centres moved
   with their surroundings rather than away from them (RQ4.3, for the change in price-to-income).

![Moran's I over time](figures/p2/moran_levels_by_year.png)

![LISA clusters](figures/p2/lisa_pti_change_map.png)

Tables: `moran_levels_by_year.csv`, `moran_changes.csv`, `moran_within_regions.csv`, `lisa_clusters_by_district.csv`.

## Fixed-effects regressions (`p2_02_fixed_effects_regressions`)

Outcome: log price-to-income, 2016 to 2023, 298 municipalities. Drivers: population growth, completions in the
previous three years, share aged 65+ and (mainland) short-term rentals. Municipality and year effects; a harder
variant adds NUTS 3 × year effects. All coefficients are adjusted associations.

6. **Prices, not incomes, drive where affordability worsened.** From 2016 to 2024 the median municipality's real
   price per m² rose 51% and its real income 29%, so price-to-income rose 19%. Across municipalities 92% of the
   variance of the deterioration is the price change and 9% the income change; the two are negatively correlated
   (−0.31), so income is decomposed, not used as a driver.
7. **The observed drivers explain little.** They account for 5% of the variation left after the fixed effects (0.9%
   with region-year effects). One within-municipality standard deviation of recent completions goes with +2.5% in
   price-to-income and of population growth with +1.3%.
8. **Most of it is regional.** Region-year effects roughly halve the coefficients; population growth (+0.55% of
   price-to-income per pp of growth) and completions (+0.50% per dwelling per 1,000) stay positive and significant.
   The completions sign is supply following prices, not building raising them.
9. **Short-term rentals: an association that does not survive the region.** On the mainland, 10 more registered
   units per 1,000 dwellings go with +3.2% (p < 0.001), but within region-year the coefficient is 0.07% per unit
   (p = 0.43). Ageing shows no robust association.

![Coefficients across specifications](figures/p2/fe_coefficients_pti.png)

Tables: `pti_change_decomposition.csv`, `fe_regressions_pti.csv`, `fe_regressions_price.csv`, `fe_residual_moran.csv`.

## Limitations

- **A pattern, not a mechanism.** Spatial autocorrelation does not show that price changes spill over: shared
  income, coast, labour markets and policy produce it as well. The within-region check removes only average
  regional differences. A spatial-lag panel model is the next test.
- **Short history.** Municipal prices start in 2016, so changes cover eight years.
- **Weights matter at the margin.** Contiguity treats very unequal municipalities alike; the within-region result
  drops from 0.20 to 0.08 with k-nearest weights.
- **Exploratory clusters.** LISA and Gi* use 300 tests with no multiple-testing correction; they flag the same
  municipalities because the statistics are closely related, so agreement is not independent confirmation.
- **Residual spatial dependence.** Residual Moran's I of the main regression is 0.01 to 0.41 depending on the year
  (0.41 in 2023), so errors clustered by municipality are probably too small; clustering by region (26 clusters)
  keeps the conclusions, but few clusters are a caveat of its own.
- **Missing demand drivers.** Immigration (municipal series ends in 2023, not yet ingested) and second homes are
  not in the panel; the population term mixes natural change, internal moves and immigration.
- **Rentals.** The series is the stock of units still registered today (survivors, mainland only), which understates
  the past and so overstates its growth.
- **Missing municipalities.** 12 municipalities have no price-to-income for 2016 or 2024 and are left out (hatched on
  the map); their neighbours' weights are re-standardised without them.

## Questions answered

RQ4.3, RQ4.4, RQ4.6, RQ3.3, RQ5.1 and RQ5.4 are partly answered (see [research_questions](../docs/research_questions.md)).
