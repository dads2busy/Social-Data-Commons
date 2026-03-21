# Methods: Rubric and Step-by-Step Instructions

A guide for writing the Methods section of a Scientific Data "Data Descriptor" article. Designed to be followed by an LLM or human author.

---

## Purpose of This Section

The Methods section describes, in sufficient detail for reproduction, how the dataset was created. It covers experimental design, data acquisition, and computational processing. A reader should be able to recreate the dataset from scratch using only this section and the cited source data.

It does NOT:
- Present results, analyses, or findings.
- Evaluate data quality (that belongs in Technical Validation).
- Describe what the dataset contains (that belongs in Data Records).
- Argue for the dataset's importance (that belongs in Background & Summary).

---

## Voice and Style Rules

Inherit all voice and style rules from the Background & Summary rubric (`docs/background-summary-rubric.md`), with these additions:

### Section-Specific Tone
Methods writing is precise, procedural, and sequentially organized. Use past tense for actions taken ("we scraped", "addresses were geocoded") and present tense for general descriptions of algorithms or formulas ("the Gaussian kernel assigns weights that decay with travel time").

### Key Principles
1. **Reproducibility is the standard.** Every step must be described at a level of detail that allows replication. If a parameter was chosen, state its value. If a default was applied, state the default. If an exception was handled, state the rule.
2. **Organize by pipeline step.** Use subsections that follow the data processing pipeline from raw inputs to final outputs, in order.
3. **Document all inputs explicitly.** Every input dataset must be named, versioned, and cited. Include a summary table of all input data sources.
4. **State software and versions.** Name every software tool, programming language, and library used, with version numbers.
5. **Write out equations.** Any mathematical formula used in computation must be stated explicitly, with all variables defined. Do not refer readers to source code or external packages without also stating the formula.

---

## Structural Template

The section should contain approximately 1,500 to 4,000 words organized into subsections that mirror the data pipeline. For a dataset built from administrative records, geocoding, population data, travel times, and spatial accessibility computations, the recommended structure is:

### Subsection 1: Data Sources (200-400 words + table)
**Goal:** Document all input datasets in one place.

- Include a table with columns: Source Name, Provider, Description, Geographic Scope, Temporal Coverage, Access Date, URL/DOI.
- Briefly describe each source in narrative form.
- Cite each input dataset formally using the Scientific Data data citation format.

### Subsection 2: Facility Data Collection (200-400 words)
**Goal:** Describe how provider/facility records were obtained.

- Name the source portal or database.
- Describe the scraping, download, or API method.
- State what fields were extracted (name, address, capacity, age range, etc.).
- Document any parsing, cleaning, or default imputation applied.
- State the number of records obtained per time point.

### Subsection 3: Geocoding (100-200 words)
**Goal:** Describe how addresses were converted to coordinates.

- Name the geocoding service and API endpoint.
- Describe the matching strategy (first attempt, retry logic).
- State how geocoded points were assigned to geographic units (e.g., nearest block group centroid).
- Name the distance metric used (haversine, Euclidean, network).

### Subsection 4: Population Data (100-200 words)
**Goal:** Describe the population denominator source.

- Name the survey, table, and variables used.
- State the geographic level and vintage.
- Describe how age-specific populations were constructed from the source variables.

### Subsection 5: Travel Time Computation (100-200 words)
**Goal:** Describe how travel times were obtained.

- Name the routing engine and configuration.
- State the geographic scope of the travel time matrix.
- Describe what the matrix represents (centroid-to-centroid, door-to-door, etc.).
- State the travel mode (driving, walking, transit).

### Subsection 6: Accessibility Measure Computation (400-800 words)
**Goal:** Describe the core methodology with full mathematical detail.

- Name the method and cite the original paper.
- Write out the complete mathematical formulation (all steps).
- Define every variable and parameter.
- State the parameter values chosen and justify the choice.
- Describe any implementation-specific details (normalization, edge cases, zero-population handling).

### Subsection 7: Geographic Aggregation (100-200 words)
**Goal:** Describe how block-group-level measures were aggregated to higher levels.

- Name the target geographic levels (tract, county, health district).
- State the aggregation method for each measure type (sum, mean, population-weighted mean).
- Cite the crosswalk used for non-nested geographies (e.g., county-to-health-district).

### Subsection 8: Software and Computational Environment (50-100 words)
**Goal:** State all software versions.

- Programming language and version.
- Key libraries with versions.
- Any external services with versions or access dates.

---

## Equations

### Formatting
- Number all equations sequentially: (1), (2), (3), etc.
- Define every variable immediately after the equation.
- Use consistent notation throughout the section.
- If the method has multiple steps, label them (Step 1, Step 2, Step 3).

### What Must Be Explicit
For a floating catchment area method, the following must be written out:
1. The distance-decay (kernel) function with its formula.
2. Each step of the FCA computation with summation notation.
3. The normalization step (if 3SFCA).
4. The final accessibility ratio formula.
5. The scale parameter value and its interpretation.

---

## Input Data Source Table

Every Methods section should include a table of input data sources. Required columns:

| Column | Description |
|---|---|
| Source | Short name of the dataset |
| Provider | Organization that publishes it |
| Description | What it contains (1 sentence) |
| Geographic scope | State, national, etc. |
| Temporal coverage | Years or date range |
| Resolution | Block group, county, point, etc. |
| Access date | When the data was downloaded |
| URL or DOI | How to find it |

---

## Citation Requirements

Methods sections typically require 5-10 citations:
- 1 citation per input data source (with DOI where available)
- 1-2 citations for the core methodology (e.g., Wan et al. 2012 for 3SFCA)
- 1 citation for the routing engine or geocoder if it has a published paper
- 1 citation for any crosswalk or geographic standard used

All citations must be verified using the same protocol as the Background & Summary rubric.

---

## Quality Checklist

Before finalizing, verify:

- [ ] Every input dataset is named, versioned, and cited
- [ ] An input data source table is included
- [ ] All mathematical formulas are written out with variables defined
- [ ] All parameter values are stated (not just "we used a Gaussian kernel" but "with scale s = 18 minutes")
- [ ] All software tools and libraries are named with version numbers
- [ ] The section follows the pipeline from raw inputs to final outputs, in order
- [ ] No results, analyses, or quality assessments are presented
- [ ] Sufficient detail for replication by a competent researcher
- [ ] No em dashes
- [ ] No LLM-typical phrases
- [ ] All citations verified
- [ ] Word count is 1,500 to 4,000

---

## Step-by-Step Execution Instructions (for LLM agents)

### Step 1: Map the Pipeline
Read all code files (ingest.py, scrape.py, prepare.py) and pipeline.yaml. Create a sequential list of every processing step from raw input to final output. For each step, record: inputs, outputs, parameters, and software used.

### Step 2: Gather Version Information
Check the project's dependency files (pyproject.toml, uv.lock) for exact versions of all libraries. Check the Python version. Check external service versions or access dates.

### Step 3: Extract Equations from Code
For any computational step involving formulas (distance calculations, kernel functions, accessibility ratios), translate the code into standard mathematical notation. Verify the translation is correct by tracing through the code logic.

### Step 4: Build the Input Data Source Table
For each input dataset, collect: source name, provider, description, scope, temporal coverage, resolution, access date, and URL/DOI. Format as a table.

### Step 5: Draft Each Subsection
Follow the structural template. Write in past tense for completed actions, present tense for mathematical descriptions. Include all parameter values, all equation numbers, and all variable definitions.

### Step 6: Verify Citations
Dispatch a separate verification agent for all citations.

### Step 7: Review Against Checklist
Walk through the quality checklist. Fix any violations.
