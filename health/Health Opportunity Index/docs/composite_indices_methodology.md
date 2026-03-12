# VDH Health Opportunity Index: Composite Profile Derivation Methodology

**Date:** 2026-03-12
**Author:** Reverse-engineered from VDH source data files

## Overview

The Virginia Department of Health (VDH) publishes the Health Opportunity Index (HOI) as a composite measure of health opportunity across Virginia's census tracts. The HOI comprises 4 intermediate "profile" scores derived from 14 sub-indicators, which are then combined into an overall Composite Index.

This document describes the **actual formulaic approach** for producing the 4 composite profile indices, determined by numerical analysis of VDH's published data files.

## VDH's Published Methodology

From VDH's HOI methodology page (`apps.vdh.virginia.gov/omhhe/hoi/methodology`):

> "Z-scores were calculated for each indicator for each Census Tract in Virginia. These scores are weighted and combined using Principal Component Analysis into a single HOI score."

> "County-level results are calculated as population-weighted averages of each indicator, combined using Principal Component weights."

The HOI explains approximately 60% of the variation in Disability Free Life Expectancy across Virginia's Census Tracts.

## The 4 Profiles and Their Thematic Sub-Indicators

VDH describes each profile as thematically associated with a subset of the 14 indicators:

| Profile | VDH Name | Thematic Sub-Indicators |
|---|---|---|
| `community_environment_indicator` | Built Environment Profile | Air Quality, Population Churning, Population Density, Walkability |
| `economic_opportunity_indicator` | Economic Profile | Employment Accessibility, Income Inequality, Job Participation |
| `wellness_disparity_indicator` | Social Impact Profile | Access to Care, Segregation |
| `consumer_opportunity_indicator` | Consumer Profile | Affordability, Education, Food Accessibility, Material Deprivation |

**Important:** These groupings describe which indicators load *most heavily* on each profile. The actual computation uses **all 14 indicators** for every profile (see weight matrix below).

## Source Data Files

Analysis is based on two VDH Excel files in `data/original/`:

- **`HOI V3 14 Variables_For UVA.xlsx`** — 14 raw indicators for 2,168 VA census tracts (2020 data)
  - Sheet "14 variables": columns CT2, FIPS, Geographic Area Name, Tpop, then 14 indicator columns
- **`hoi_indexes_quintile_2022.xlsx`** — 4 profile scores + composite index for the same tracts
  - Sheet "HOI V3": columns CT, Built Environment Profile SI, Economic Profile SI, Social Impact Profile SI, Consumer Profile SI, Composite Index Standardized, Composite in Quintiles

## Proven Properties of the Profile SI Values

Through numerical analysis of the 2,168 common tracts:

1. **Each Profile SI is an EXACT linear combination of the 14 indicators** — max absolute error ~10⁻¹⁵ (machine precision) when regressed against all 14 normalized indicators.

2. **The 4 profiles are perfectly orthogonal** — pairwise correlations are 0 to machine precision. This is a hallmark of PCA-derived components.

3. **Each Profile SI ranges exactly [0, 1]** — consistent with min-max scaling of PCA scores.

4. **The weight matrix satisfies `W^T @ Cov(X) @ W = diagonal`** — confirming orthogonal projections under the covariance inner product. This property results from PCA followed by an orthogonal rotation, then min-max scaling.

5. **The Composite Index is a near-exact weighted sum of the 4 profiles** (max error ~0.0005, likely due to rounding).

## The Exact Algorithm

```
Step 1: Collect 14 raw indicators at census tract level
Step 2: Min-max normalize each indicator to [0,1] across all VA tracts
Step 3: Invert indicators 7-14 (Segregation through Mobility) so higher = better
Step 4: Apply the weight matrix below (derived from PCA + orthogonal rotation)
Step 5: Each profile score already falls in [0,1] due to the linear mapping
Step 6: Compute Composite Index as weighted sum of 4 profiles
Step 7: Cut Composite into quintiles for display labels
```

## The 14 Input Indicators

Listed in column order from the source Excel file. Indicators marked with `*` are inverted (1 - normalized_value) so that higher values indicate better health opportunity.

| Index | Column Name | Indicator | Inverted? |
|---|---|---|---|
| 0 | `**Accees to Care` | Access to Care | No |
| 1 | `Education` | Average Years of Schooling | No |
| 2 | `Employment Access` | Employment Accessibility | No |
| 3 | `Labor Force Participation` | Job Participation Rate | No |
| 4 | `Population Density` | Population-Weighted Density | No |
| 5 | `Walkability` | Walkability Index | No |
| 6 | `**Spatial Segregation` | Spatial Segregation | Yes* |
| 7 | `Income Inequality` | Gini Index | Yes* |
| 8 | `Affordability*` | Affordability Index | Yes* |
| 9 | `Environmental*` | Environmental Hazard Index | Yes* |
| 10 | `Food Access*` | Food Access Percentage | Yes* |
| 11 | `Townsend*` | Material Deprivation (Townsend) | Yes* |
| 12 | `Incarceration*` | Incarceration Rate per 100k | Yes* |
| 13 | `Mobility*` | Population Churning (% Moving) | Yes* |

## Exact Weight Matrix

Each Profile SI value is computed as:

```
Profile_SI = intercept + w₁*X₁ + w₂*X₂ + ... + w₁₄*X₁₄
```

where X₁ through X₁₄ are the min-max normalized (and inverted where applicable) indicator values.

| Indicator | Built Environment | Economic | Social Impact | Consumer |
|---|---|---|---|---|
| **(Intercept)** | 0.501075 | 0.212378 | -0.186243 | 0.193488 |
| Access to Care | 0.126959 | -0.569812 | **0.877328** | -0.369157 |
| Education | 0.186815 | 0.026156 | 0.183904 | 0.076218 |
| Employment Access | 0.197667 | 0.040961 | 0.062257 | -0.116375 |
| Labor Force Part. | -0.054056 | **0.308118** | -0.085525 | -0.000987 |
| Population Density | 0.117221 | 0.153745 | 0.030498 | **-0.382302** |
| Walkability | **0.273904** | -0.059131 | -0.044121 | 0.149943 |
| Segregation | -0.227893 | 0.029868 | 0.182972 | -0.220734 |
| Income Inequality | **-0.318781** | **0.422138** | -0.129801 | 0.083492 |
| Affordability | -0.008530 | 0.099447 | -0.100766 | **-0.217298** |
| Environmental | **-0.221318** | -0.069300 | 0.005989 | 0.125674 |
| Food Access | **0.312486** | 0.027708 | 0.022635 | **0.274875** |
| Material Deprivation | -0.052431 | 0.066343 | 0.093376 | **0.273215** |
| Incarceration | -0.021854 | 0.149189 | 0.141892 | 0.085672 |
| Mobility/Churning | 0.090131 | 0.043833 | -0.119968 | **0.468253** |

Bold values indicate the largest-magnitude weights for each profile.

## Composite Index Formula

The overall HOI Composite Index Standardized is a weighted sum of the 4 profile scores:

```
Composite = -1.112348
  + 0.557569 × Built Environment Profile SI
  + 0.741344 × Economic Profile SI
  + 0.895643 × Social Impact Profile SI
  + 0.561597 × Consumer Profile SI
```

Max error vs. published values: ~0.0005 (likely due to intermediate rounding).

## Quintile Assignment

The Composite Index Standardized ranges [0, 1] and is cut into 5 quintiles:

| Label | Range | Count |
|---|---|---|
| Very Low Opportunity | 0.000 – 0.518 | 434 |
| Low Opportunity | 0.518 – 0.594 | 434 |
| Moderate Opportunity | 0.594 – 0.665 | 434 |
| High Opportunity | 0.665 – 0.749 | 433 |
| Very High Opportunity | 0.749 – 1.000 | 433 |

## Dominant Indicators per Profile

While all 14 indicators contribute to every profile, the largest contributors (|weight| > 0.15) are:

**Built Environment Profile SI:**
- Income Inequality (-0.319), Food Access (+0.312), Walkability (+0.274), Segregation (-0.228), Environmental (-0.221), Employment Access (+0.198), Education (+0.187)

**Economic Profile SI:**
- Access to Care (-0.570), Income Inequality (+0.422), Labor Force Participation (+0.308), Population Density (+0.154)

**Social Impact Profile SI:**
- Access to Care (+0.877), Education (+0.184), Segregation (+0.183)

**Consumer Profile SI:**
- Mobility/Churning (+0.468), Population Density (-0.382), Access to Care (-0.369), Food Access (+0.275), Material Deprivation (+0.273), Segregation (-0.221), Affordability (-0.217)

## How the Repo's Legacy Code Approximates This

The `Composite Indices/code/Prepare_Composite_Indices_Files.Rmd` script uses OLS linear regression to approximate these profiles for years other than 2020:

1. Train 4 separate OLS models on 2020 data: Profile_SI ~ 14 normalized indicators
2. Predict profile scores for other years (2015-2019, 2021) using that year's indicator values
3. Scale predictions to [0,1] and bin into quintiles

This works because the Profile SI values are exact linear functions of the 14 indicators. For 2020, OLS perfectly recovers the weights. For other years, the approximation introduces error because the min-max normalization parameters differ.

**Known limitation:** The legacy code uses 2020 incarceration data for all years (noted in comments: "use 2020 incarceration? -> slightly better results with 2020 incarceration").

## Reproducibility Notes

- The PCA weights file referenced in the code (`HOI V3_4 Components_PCA weights.xlsx`) is not in the repository — it was on a developer's local machine.
- The exact orthogonal rotation method used by VDH (likely varimax or similar) is not documented.
- However, the exact weight matrix above is sufficient to reproduce all Profile SI values with machine-precision accuracy from the normalized indicator data.
- VDH has published HOI data for 2017 and 2020. The 2017 data uses text quintile labels (Very Low/Low/Average/High/Very High) without continuous scores.
