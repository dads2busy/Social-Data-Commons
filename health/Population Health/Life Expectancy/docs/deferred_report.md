# Life Expectancy — Deferred Pipeline Report

**Date:** 2026-03-03
**Status:** DEFERRED

## Qualification checklist failures

### Section 0.5 — Pipeline uses spatial analysis or ML prediction
- **FAIL:** Pipeline builds predictive models (VDH Predictions) to estimate tract-level life expectancy from health indicators
- ML workflow: collects indicator variables per tract, trains prediction model, generates year-by-year life expectancy estimates (2015-2023)

### Section 0.3 — Pipeline depends on other pipelines' outputs
- **FAIL:** Predictions rely on indicator CSVs from HOI, SVI, and other health pipelines as input features

## What exists
- `Get_Life_Expectancy_Files.R` / `.Rmd` — main pipeline
- `data/life_expectancy_predicted/` — year-by-year prediction outputs (2015-2023)
- `data/indicators_used_for_LE/` — input feature CSVs per year

## To unblock
1. Convert upstream indicator pipelines first (HOI, SVI — done)
2. Port prediction model to Python (scikit-learn or similar)
3. Validate predicted values against R model output
