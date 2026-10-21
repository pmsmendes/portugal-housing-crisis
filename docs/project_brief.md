# Project Brief — Portugal's Housing Crisis

Original project definition (verbatim). The research question bank lives in
[research_questions.md](research_questions.md) with IDs.

## Project

Portugal's housing crisis has become one of the country's most pressing economic and social challenges.
Rising property prices and rents, declining housing affordability, demographic changes, and regional disparities have raised important questions about the underlying causes of the crisis and the effectiveness of existing public policies.

This project aims to investigate the evolution of Portugal's housing market over the past three decades using data science, statistical analysis, and predictive modeling.
By combining housing market data with demographic, economic, and construction indicators, the analysis will explore the relationships between housing supply, population growth, immigration, household income, tourism, and housing affordability across different regions of Portugal.

Beyond understanding historical trends, the project will examine the potential effects of housing policies, including rent regulation, property taxation, public housing investment, and incentives for new construction and property renovation.
Where the available data and research design allow, statistical inference and causal analysis will be used to evaluate these relationships, while scenario modeling will help explore possible future developments and policy trade-offs.

The ultimate goal is to develop an evidence-based understanding of Portugal's housing crisis, identify the factors most strongly associated with deteriorating affordability, and assess potential policy responses in terms of their expected impact, limitations, and fiscal implications.
The project will combine rigorous analytical methods with clear visualizations and interactive tools to make its findings accessible and useful for further research and informed policy discussion.

## Portfolio structure

- **Phase 1 — Establish the evidence:** Data acquisition, cleaning, exploratory analysis, affordability indicators, geographic analysis and descriptive visualizations.
- **Phase 2 — Explain the trends:** Panel regression, municipality segmentation, spatial autocorrelation and analysis of housing supply versus demand.
- **Phase 3 — Evaluate a policy:** Select one policy question, establish a credible evaluation design if possible, and quantify the limitations of the conclusions.
- **Phase 4 — Forecast and simulate:** Compare forecasting baselines, quantify uncertainty, and develop an interactive scenario analysis with transparent assumptions.

Housing affordability is the central outcome, with supply, demographics, regional variation and policy as the explanatory dimensions.
That gives the project a coherent analytical purpose instead of turning it into a collection of unrelated charts.
A strong final result would combine three things: an evidence-based explanation of why affordability has deteriorated, a defensible evaluation of at least one policy, and a scenario tool that shows the potential trade-offs of alternative interventions.

## Implementations

### 1. Data preprocessing and exploratory data analysis (Essential)
- Clean, merge and validate datasets from different Portuguese sources.
- Handle missing values, inconsistent geographic boundaries and changes in statistical definitions.
- Normalize monetary values for inflation and convert data to comparable time periods.
- Create features such as price-to-income ratios, rent-to-income ratios, housing growth and household growth.
- Document data quality limitations and potential biases.

### 2. Spatial analysis and geographic visualization (Essential)
- Choropleth maps showing prices, rents and affordability by municipality.
- Compare coastal versus inland, urban versus rural, and tourist versus non-tourist areas.
- Measure spatial clustering using Global Moran's I and identify local hotspots using Local Moran's I or Getis-Ord Gi*.
- Examine whether housing pressures spread into neighboring municipalities.

### 3. Time-series analysis and forecasting (Essential)
- Analyze long-term trends, seasonality where the data supports it, and structural breaks.
- Compare baselines such as naïve forecasts and seasonal naïve forecasts with statistical models such as ETS or ARIMA.
- Evaluate more complex models only if they improve performance.
- Use rolling-origin validation, prediction intervals and appropriate error metrics.
- Forecast affordability indicators, not just nominal house prices.

### 4. Statistical inference and explanatory modeling (High value)
- Quantify associations between prices and rents and factors such as income, population growth, immigration, new construction, tourism and interest rates.
- Fit multiple regression models with interpretable coefficients.
- Use log transformations where appropriate, robust standard errors and carefully selected controls.
- Include municipality and year effects in panel-data models to account for persistent local differences and common national shocks.
- Check multicollinearity, residual patterns and model sensitivity.

This helps distinguish simple correlations from relationships that remain after accounting for other measured factors.

### 5. Causal inference and policy evaluation (Advanced)
- Evaluate a specific housing policy using a difference-in-differences design, if a credible comparison group and suitable data exist.
- Consider event-study models to examine changes before and after a policy intervention.
- Test pre-trends and investigate spillovers, confounding factors and policy anticipation.
- If no credible identification strategy is available, present adjusted associations rather than claiming causal effects.

This is particularly valuable because the project asks whether rent regulation, tax changes and other interventions actually improve affordability.

### 6. Policy simulation and scenario analysis (Essential for this project)
- Simulate different rates of housing construction, renovation of vacant homes and public housing investment.
- Estimate the direct fiscal impact of alternative IMI and IMT reforms.
- Model optimistic, baseline and pessimistic demographic and economic scenarios.
- Compare policies by affordability improvement, estimated public cost and uncertainty.
- Explicitly distinguish direct accounting effects from behavioral responses that require additional assumptions or empirical estimates.

Do not add deep learning, NLP, or complex machine learning just to have more techniques.
For this problem, a well-designed panel regression or credible causal study may be substantially more valuable than an unnecessarily complicated predictive model.

### 7. Tables, plots and interactive visualizations
- **Geographic dashboard:** Explore municipalities using a map with filters for year, price, rent, income, affordability and housing supply.
- **Long-term trend dashboard:** Compare nominal and inflation-adjusted prices, rents, wages and price-to-income ratios over time.
- **Explanatory analysis:** Scatter plots, regression coefficient plots, correlation matrices and comparisons between municipalities with different housing-market characteristics.
- **Forecast and policy simulator:** Display forecast ranges and let users compare alternative assumptions for construction, population growth, interest rates and policy costs.
