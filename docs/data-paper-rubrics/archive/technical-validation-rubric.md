# Technical Validation: Rubric and Step-by-Step Instructions

A guide for writing the Technical Validation section of a Scientific Data "Data Descriptor" article. Designed to be followed by an LLM or human author.

---

## Purpose of This Section

Technical Validation is the section where authors demonstrate that their dataset is trustworthy. It describes experiments, analyses, and checks that support the technical quality of the data. In highly cited Data Descriptors, this section accounts for 25 to 40 percent of total word count and is the primary basis on which reviewers assess the manuscript.

The section answers one question: **How do we know this data is correct?**

It does NOT:
- Present scientific findings or interpret results.
- Argue for the dataset's importance or novelty.
- Repeat methods already described in the Methods section (it validates them, not restates them).

---

## Voice and Style Rules

Inherit all voice and style rules from the Background & Summary rubric (`docs/background-summary-rubric.md`), with these additions:

### Section-Specific Tone
Technical Validation writing is the most self-critical section of a Data Descriptor. Top papers adopt a tone of transparent honesty: they present what went right, what went wrong, and where uncertainty remains. Reviewers are looking for evidence that the authors understand the limitations of their own data.

**Good patterns from top articles:**
- "CHELSA still exhibits errors which we quantified." (CHELSA)
- "The dataset systematically undercounts small buildings below 200 square meters." (Rasterized Building Footprints)
- "Precision ranged from 98.2 to 99.5 percent, while recall varied more widely, from 36.5 to 73 percent for all building sizes." (Rasterized Building Footprints)

### Key Principles
1. **Quantify everything.** Every quality claim must have a number attached: a correlation coefficient, a percentage, a count, an error metric. "The data are accurate" is not validation. "Geocoding matched 94.3% of facility addresses on the first attempt" is.
2. **Compare against independent sources.** Internal consistency checks are necessary but not sufficient. At least one validation must use an external reference dataset that was not used in producing the data.
3. **Disaggregate errors.** Report metrics by subgroup (region, time period, category) to show where the data performs well and where it performs poorly. Aggregate metrics can mask localized problems.
4. **Acknowledge limitations explicitly.** Every validation subsection should end with a candid statement about what the check does and does not demonstrate.

---

## Structural Template

The section should contain approximately 1,500 to 4,000 words organized into 4 to 7 subsections. Each subsection validates a different component of the data pipeline or a different dimension of data quality.

### Subsection Selection

Not every dataset needs every type of validation. Select subsections based on what your data pipeline does. The rule is: **every step where error could be introduced needs a validation check.**

For a dataset built from scraped administrative records, geocoded locations, and spatial accessibility computations, the relevant validation dimensions are:

| Pipeline Step | What Could Go Wrong | Validation Approach |
|---|---|---|
| Web scraping | Missing facilities, parsing errors, stale data | Compare scraped count against an independent facility count |
| Geocoding | Failed matches, incorrect coordinates | Report match rate; spot-check against known locations |
| Age range parsing | Misinterpretation of text, default values masking errors | Report distribution of parsed values; count defaults applied |
| Population denominators | Wrong ACS vintage, misaligned geographies | Compare against published Census totals |
| Travel time matrix | OSRM routing errors, missing pairs, no-traffic assumption | Spot-check against independent routing source |
| 3SFCA computation | Implementation bugs, parameter sensitivity | Sensitivity analysis; compare against simpler measures |
| Temporal consistency | Implausible changes between time points | Compare 2021 vs. 2025 and assess plausibility |

### Recommended Subsection Order

1. **Source data completeness** (scraping coverage, geocoding success)
2. **Geocoding accuracy** (coordinate validation)
3. **Population denominator verification** (ACS cross-check)
4. **Travel time validation** (spot-check routing)
5. **Accessibility measure validation** (sensitivity analysis, comparison to simpler metrics)
6. **Temporal consistency** (cross-year comparison)
7. **Summary of known limitations** (can be a closing paragraph rather than a formal subsection)

---

## Validation Methods by Data Type

### For Scraped/Administrative Data
- **Coverage check:** Compare your facility count against an independent published total (e.g., a government annual report, a different data aggregator).
- **Completeness audit:** Report the percentage of records with complete data in each field (capacity, age range, address). Report how many required default imputation.
- **Geocoding match rate:** Report percentage matched on first attempt, percentage matched after retry, percentage unmatched. If possible, compare a random sample of geocoded coordinates against a known-good source (Google Maps, a verified address database).

### For Derived/Computed Measures
- **Sensitivity analysis:** Vary key parameters (e.g., the Gaussian decay scale in a floating catchment area model) and report how much the output changes. If the output is highly sensitive to parameter choice, this must be disclosed.
- **Convergent validity:** Compare the computed measure against a simpler, more transparent measure of the same concept. For example, compare 3SFCA ratios against simple provider-to-child ratios within fixed-radius buffers. The two measures should be correlated.
- **Face validity:** Do the results make intuitive sense? Map the output and verify that known patterns (urban vs. rural, affluent vs. disadvantaged) appear as expected. This is the weakest form of validation but still useful.

### For Multi-Temporal Data
- **Temporal plausibility:** Report the magnitude of change between time points. Are the changes plausible given known events (e.g., COVID-19 pandemic effects on child care supply)? Cite external evidence for expected trends.
- **Decompose change:** Separate changes in the numerator (provider supply) from changes in the denominator (child population) to identify what is driving observed shifts.

---

## Figures and Tables

Technical Validation is the most figure-heavy section. Budget for:
- 2 to 5 figures (maps, scatter plots, sensitivity curves, bar charts)
- 1 to 3 tables (validation metrics by subgroup, sensitivity parameters, temporal comparison)

### Figure Types That Work Well
| Figure Type | Use For |
|---|---|
| Scatter plot with 1:1 line | Comparing your measure against an independent reference |
| Choropleth map pair | Showing spatial distribution of a measure at two time points |
| Bar chart by category | Error rates or completeness rates by subgroup |
| Line chart or heatmap | Sensitivity of output to parameter variation |
| Histogram | Distribution of a measure to show reasonableness |

---

## Citation Requirements

Technical Validation typically requires fewer citations than Background & Summary (5 to 12 total), but they must include:
- The independent reference datasets used for comparison (with DOIs or official URLs)
- Methodological references for any statistical tests or validation frameworks used
- External evidence supporting temporal plausibility claims (e.g., reports on COVID-era child care closures)

All citations must be verified using the same protocol as the Background & Summary rubric.

---

## Quality Checklist

Before finalizing, verify:

- [ ] Every pipeline step where error could enter has a corresponding validation check
- [ ] At least one validation uses an independent external reference (not a data source used in production)
- [ ] Every quality claim is quantified (no unsubstantiated "the data are accurate" statements)
- [ ] Metrics are reported by subgroup, not just in aggregate
- [ ] Sensitivity to key parameters is tested and reported
- [ ] Known limitations are explicitly listed with their likely impact
- [ ] Figures have clear axis labels, legends, and captions
- [ ] No results or scientific findings are presented (only data quality assessments)
- [ ] No superlatives or promotional language
- [ ] No em dashes
- [ ] No LLM-typical phrases (see Background & Summary rubric avoid list)
- [ ] All citations verified by independent agent
- [ ] Word count is 1,500 to 4,000

---

## Step-by-Step Execution Instructions (for LLM agents)

### Step 1: Inventory the Pipeline
Read the full data pipeline code and documentation. For each processing step, record:
- What the step does
- What inputs it takes
- What outputs it produces
- What could go wrong (error modes)
- What validation is already built into the code (assertions, logging, deduplication)

### Step 2: Identify Available Reference Data
Search for independent data sources that can serve as validation benchmarks:
- Published facility counts from government reports
- Census population totals at aggregated geographies
- Alternative routing services for travel time comparison
- Prior published analyses that computed similar measures

For each potential reference, assess: Is it independent of the data used in production? Is it publicly available? Can it be cited?

### Step 3: Run Validation Analyses
Execute concrete analyses against the actual dataset. This is not speculative; this requires running code or examining real data. The analyses must produce real numbers.

For each analysis:
1. State the question being asked
2. Describe the method
3. Report the quantitative result
4. Interpret what the result means for data quality
5. Note any caveats

### Step 4: Conduct Sensitivity Analysis
For key methodological parameters:
1. Identify the parameter and its default value
2. Choose a reasonable range of alternative values
3. Recompute the output with each alternative
4. Report how much the output changes (e.g., as percent change in mean, correlation between original and perturbed output)
5. Assess whether the default choice materially affects conclusions

### Step 5: Assess Temporal Consistency
If the dataset covers multiple time points:
1. Compute summary statistics at each time point
2. Calculate the magnitude and direction of change
3. Decompose change into its components (supply change vs. demand change)
4. Assess plausibility against external evidence

### Step 6: Compile Known Limitations
Create a numbered or bulleted list of every known limitation, assumption, and source of error. For each, state:
- What the limitation is
- Why it exists (design choice or data constraint)
- What its likely impact is on users of the data
- Whether it can be addressed in future versions

### Step 7: Draft the Section
Write each subsection following the structural template. Lead each subsection with the validation question, present the method and results, and close with what the check demonstrates and what it does not.

### Step 8: Create Figures and Tables
For each key validation result, determine whether it is better communicated as:
- A figure (spatial patterns, correlations, distributions, trends)
- A table (exact metrics by subgroup)
- Inline text (single summary statistics)

Create figures with clear labels, captions, and no decorative elements.

### Step 9: Verify Citations
Dispatch a separate verification agent for all citations added in this section.

### Step 10: Review Against Checklist
Walk through the quality checklist item by item. Fix any violations before finalizing.
