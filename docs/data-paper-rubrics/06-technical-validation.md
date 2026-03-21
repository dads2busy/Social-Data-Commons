# Technical Validation: Rubric and Instructions

## Purpose
Demonstrates that the dataset is trustworthy. Describes experiments, analyses, and checks supporting data quality. Answers: "How do we know this data is correct?"

It does NOT present scientific findings, argue for importance, or repeat methods.

## Voice and Style
The most self-critical section. Transparent honesty: present what went right, what went wrong, and where uncertainty remains. Quantify everything. Inherit all avoid-list rules.

## Key Principles
1. **Quantify everything.** Every quality claim needs a number.
2. **Compare against independent sources.** At least one validation must use external reference data.
3. **Disaggregate errors.** Report metrics by subgroup (region, time, category).
4. **Acknowledge limitations explicitly.** Every subsection should close with what the check does and does not demonstrate.

## Structural Template (1,500-4,000 words)

Select subsections based on pipeline steps where error could enter:

### Source Data Completeness (200-400 words)
Compare scraped/collected count against independent published total. Report field-level completeness rates. Document defaults/imputations.

### Geocoding/Spatial Accuracy (100-200 words, if applicable)
Match rate, bounding box check, positional uncertainty discussion.

### Denominator/Population Verification (100-200 words, if applicable)
Cross-check aggregated values against published totals.

### Internal Consistency (100-200 words)
Verify aggregation arithmetic (BG sums = county totals, etc.).

### Distribution of Measures (200-400 words + table + figure)
Summary statistics table (N, mean, median, SD, min, max, % zero) by measure and year. Discuss outliers. Include choropleth or histogram figure.

### Convergent Validity (200-300 words + figure)
Compare computed measure against a simpler alternative. Report Pearson and Spearman correlations. Explain divergences.

### Geographic Disaggregation (150-250 words + figure)
Break down key metrics by urban/rural or other subgroups. Report significance tests.

### Sensitivity Analysis (200-300 words + figure)
Vary key parameters. Report how output changes. Assess robustness.

### Temporal Consistency (200-400 words + figure, if multi-year)
Report magnitude of cross-year changes. Cite external evidence for plausibility. Decompose changes.

### Known Limitations (numbered list)
For each: what it is, why it exists, likely impact, whether addressable in future.

## Figures and Tables Budget
- 2-5 figures (maps, scatter plots, sensitivity curves, boxplots)
- 1-3 tables (summary statistics, validation metrics by subgroup)

## Citation Requirements
- 5-12 citations: independent reference datasets, methodology references, external evidence for temporal plausibility

## Quality Checklist
- [ ] Every pipeline step with error potential has a validation check
- [ ] At least one independent external reference
- [ ] Every quality claim quantified
- [ ] Metrics reported by subgroup
- [ ] Sensitivity to key parameters tested
- [ ] Known limitations explicitly listed
- [ ] No scientific findings presented
- [ ] 1,500-4,000 words, 5-12 citations

## Execution Steps
1. Inventory the pipeline: for each step, identify error modes.
2. Identify independent reference data sources.
3. Run validation analyses against actual data (produce real numbers).
4. Run sensitivity analysis varying key parameters.
5. Assess temporal consistency with external evidence.
6. Compile known limitations.
7. Generate figures and tables.
8. Draft each subsection.
9. Verify citations.
10. Run LLM language check.
