# Census 2010→2020 Standardization: Known Limitations and Data Caveats

Reusable data-paper text for any SDC dataset standardized to 2020 census geographies.
Each item is tagged with its target section so it can be dropped into a Data & Policy
paper following `docs/data-paper-rubrics/` (Technical Validation → Known Limitations, or
Usage Notes → Scope Limitations / Temporal Comparability). Section A applies to every
standardized dataset; Section B holds dataset-specific source caveats.

These reflect the state after the census10to20 data remediation (all 24 affected datasets
regenerated; merged to `main` June 2026). Figures cited below were measured on the
regenerated distribution data.

---

## A. Standardization method (applies to all standardized datasets)

### A.1 Intensive measures are replicated, not areally interpolated
*Target: Technical Validation → Known Limitations*

Counts are reallocated from 2010 to 2020 census tracts by land-area weighting, which
conserves totals. Intensive measures (percentages, rates, medians, per-household
quantities, densities, and composite indices) are not area-weighted, because a weighted
average of a rate across sub-tract fragments has no demographic interpretation. Each 2020
tract instead takes the value of the 2010 tract contributing the largest share of its land
area (its dominant parent); where a percentage's constituent counts are published, the
percentage is recomputed from the standardized counts. This treatment assumes the intensive
value is approximately uniform within the originating 2010 tract. The assumption is weakest
where a 2010 tract was split into 2020 tracts whose underlying populations differ
materially, in which case the assigned value reflects the parent tract rather than the
specific child.

### A.2 American Community Survey 5-year series begin in 2010
*Target: Usage Notes → Temporal Comparability*

The 2005–2009 ACS 5-year estimates are published on 2000-vintage census tracts, which the
2010→2020 tract relationship file cannot match. Standardizing them would discard roughly
35 to 40 percent of tract records. The 2009 estimate is therefore omitted from all
ACS-derived series, which begin with the 2006–2010 estimate (labeled 2010). Users comparing
across the full study period should note that these series start in 2010 rather than 2009.

### A.3 County totals conserve region-wide but vary slightly within counties
*Target: Technical Validation → Known Limitations*

Standardized counts conserve at the regional scale: summed 2020-boundary values divided by
summed 2010-boundary values is approximately 0.999 across measures. Individual counties can
differ by a few percent for two reasons. First, population subgroups are not distributed
uniformly within tracts that cross county lines, so area-weighted reallocation moves a small
amount of population across those lines. Second, a few Virginia jurisdictions changed
boundaries between 2010 and 2020 (for example, Bedford County, FIPS 51019, reabsorbed the
former independent city of Bedford in 2013). These per-county differences are a property of
areal interpolation and of real boundary change; they should not be read as measured change
in the underlying quantity.

---

## B. Source-data caveats (dataset-specific)

### B.1 Food Accessibility values can exceed 100 percent in a few tracts
*Target: Usage Notes → Scope Limitations (Food Accessibility paper)*

The food-access measure (share of the low-income population living more than one mile from a
supermarket, from the USDA Food Access Research Atlas, 2015 and 2019 editions) exceeds 100
percent for 13 tract-years, reaching a maximum near 151 percent. These cases occur in
Virginia independent cities, including Norfolk (FIPS 51710), Petersburg (51730), Portsmouth
(51740), and Richmond (51760), and originate in the source atlas, where the low-access
numerator and the low-income denominator are derived from different population bases. The
values are present in the published source and are carried through geographic
standardization unchanged; they are not artifacts of the 2010→2020 conversion. Depending on
the application, users may choose to cap these values at 100 percent or flag the affected
tracts.

### B.2 Virginia health-district percentages are not exactly recomputable from their counts
*Target: Usage Notes → Scope Limitations*

For Virginia, measures are additionally aggregated from counties to health districts. At the
health-district level, published percentages differ from a direct recomputation of
100 × (district numerator) ÷ (district denominator) by up to roughly 3 percentage points,
because the aggregation combines county-level rates rather than recomputing from summed
counts. Tract- and county-level percentages remain internally consistent with their counts.
Analyses that require exact count-to-percentage consistency should use the tract or county
levels rather than the health-district level.

---

## Section-placement summary

| Caveat | Applies to | Paper section |
|---|---|---|
| A.1 Intensive replication | all standardized datasets | Technical Validation → Known Limitations |
| A.2 2009 exclusion | ACS 5-year datasets (e.g. Age, Race, Gender, Veteran) | Usage Notes → Temporal Comparability |
| A.3 Per-county conservation | all count datasets | Technical Validation → Known Limitations |
| B.1 Food access > 100% | Food Accessibility | Usage Notes → Scope Limitations |
| B.2 VA health-district percentages | all VA datasets with health-district aggregation | Usage Notes → Scope Limitations |
