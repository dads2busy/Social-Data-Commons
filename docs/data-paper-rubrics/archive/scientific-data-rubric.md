# Data Descriptor Rubric for Scientific Data (Nature)

A scoring and writing guide based on the journal's official submission guidelines and patterns observed in highly-cited Data Descriptor articles (TerraClimate, CHELSA, Global Aridity Index v3, ISARIC-COVID-19, Global Land Cover Training Dataset, Rasterized Building Footprints).

---

## Key Principle

Data Descriptors describe **what a dataset is, how it was made, and how good it is**. They do NOT report findings, test hypotheses, or draw conclusions. The narrative arc is:

> Need exists → We built this → Here's what it contains → Here's how we verified quality → Here's how to use it

---

## Section-by-Section Rubric

### 1. Title (max 110 characters incl. whitespace)

| Criterion | Pass | Fail |
|---|---|---|
| Length ≤ 110 characters | Yes | No |
| No colons or parentheses | Yes | No |
| No acronyms (except DNA, RNA, etc.) | Yes | No |
| No advertising words ("novel", "first", "comprehensive", "AI-ready", "open") | Yes | No |
| No dataset brand names or self-constructed acronyms | Yes | No |
| Only first word + proper nouns capitalized | Yes | No |
| Describes the data, not a finding | Yes | No |

**Good examples from top articles:**
- "TerraClimate, a high-resolution global dataset of monthly climate and climatic water balance from 1958-2015"
- "A global land cover training dataset from 1984 to 2020"
- "A rasterized building footprint dataset for the United States"

**Pattern:** `[A/An] [descriptor] dataset [of/for] [subject] [scope/timeframe]`

---

### 2. Abstract (max 170 words, no sub-headings)

| Criterion | Pass | Fail |
|---|---|---|
| ≤ 170 words | Yes | No |
| Describes what the data IS and how it may be used | Yes | No |
| No scientific claims or findings | Yes | No |
| No URLs or download instructions | Yes | No |
| No sub-headings | Yes | No |

---

### 3. Background & Summary (typical: 800–2,500 words)

| Criterion | Score (0–3) | Notes |
|---|---|---|
| **Gap identification**: Clearly states what need the dataset fills | 0–3 | Best papers open with a concrete problem statement |
| **Landscape review**: Cites existing datasets and their limitations | 0–3 | Top papers cite 5–15 related datasets/products |
| **Motivation**: Explains why the dataset was created | 0–3 | Should be clear and specific, not vague |
| **Reuse value**: Describes potential downstream uses | 0–3 | At least 2–3 concrete use cases |
| **No subjective claims**: Avoids "novel", "unique", "superior", "first" | 0–3 | Measured, factual language only |
| **No results or conclusions** | 0–3 | Purely descriptive and motivational |

**Scoring:** 0 = missing, 1 = present but weak, 2 = adequate, 3 = exemplary

**Target: ≥ 15/18**

---

### 4. Methods (typical: 1,200–4,500 words, no word limit)

| Criterion | Score (0–3) | Notes |
|---|---|---|
| **Reproducibility**: Sufficient detail for someone to recreate the dataset | 0–3 | The core requirement — could a competent researcher replicate this? |
| **Input data documented**: All source data described with versions, access dates, search terms | 0–3 | Top papers include a table of all input sources |
| **Processing pipeline clear**: Step-by-step description of all transformations | 0–3 | Subsections per major step; flowchart figures help |
| **Equations/algorithms provided**: Mathematical or computational steps explicitly stated | 0–3 | Required when methodology involves computation |
| **Software/tools identified**: Languages, libraries, versions named | 0–3 | e.g., "Python 3.9, pandas 1.4.2, geopandas 0.11" |
| **Data citations**: Input datasets with DOIs cited in formal data citation format | 0–3 | Use `https://doi.org/...` format |
| **No results or analysis**: Focus solely on documenting how data was produced | 0–3 | Methods ≠ Results |

**Target: ≥ 18/21**

**Common subsection patterns:**
- Data collection / acquisition
- Data sources (with table)
- Processing / transformation pipeline
- Quality control procedures
- Harmonization / standardization

---

### 5. Data Records (typical: 400–1,500 words)

| Criterion | Score (0–3) | Notes |
|---|---|---|
| **Repository identified**: Names the repository where data is hosted | 0–3 | Must be a recognized repository (figshare, Zenodo, Dryad, domain-specific) |
| **File inventory**: Lists all files, formats, and folder structure | 0–3 | Table format preferred |
| **Variable definitions**: Column headings, field names, units explained | 0–3 | Anything non-obvious to a user must be defined |
| **Scale communicated**: Number of records, spatial/temporal extent, file sizes | 0–3 | Concrete numbers, not vague descriptions |
| **Data citation**: Each dataset cited with DOI in formal format | 0–3 | Required |
| **No summary statistics**: Descriptive stats go in Data Overview, not here | 0–3 | This section = what's in the box, not what the box tells you |

**Target: ≥ 15/18**

---

### 6. Data Overview (optional, max 1–2 figures/tables + 1 paragraph)

| Criterion | Pass | Fail |
|---|---|---|
| Limited to 1–2 figures/tables | Yes | No |
| Single paragraph of text | Yes | No |
| Only descriptive/summary statistics | Yes | No |
| No interpretation or analysis | Yes | No |

**Note:** More analysis shared = less incentive for others to download and cite the dataset. Use sparingly.

---

### 7. Technical Validation (typical: 300–4,500 words — often the LONGEST section)

This is the most critical section. In highly-cited papers, it accounts for 25–40% of total word count.

| Criterion | Score (0–3) | Notes |
|---|---|---|
| **Independent validation**: Tested against external reference datasets or ground truth | 0–3 | Not just internal consistency checks |
| **Quantitative metrics**: Reports specific error metrics (R², RMSE, MAE, precision, recall, etc.) | 0–3 | Numbers, not just qualitative claims |
| **Comparison to alternatives**: Benchmarks against competing/existing datasets | 0–3 | Top papers compare against 3–6 alternatives |
| **Spatial/temporal/categorical breakdown**: Error analysis across subgroups | 0–3 | Not just aggregate metrics |
| **Limitations acknowledged**: Explicitly states where the dataset performs poorly | 0–3 | Every top paper does this — honesty builds trust |
| **Supporting figures/tables**: Visual evidence of data quality | 0–3 | Scatter plots, maps, confusion matrices, etc. |

**Target: ≥ 15/18**

**Validation approaches by data type:**

| Data Type | Typical Validation Approach |
|---|---|
| Geospatial/climate | Compare against independent station networks; report correlations, MAE, bias |
| Survey/observational | Describe QA processes, edit checks, data governance procedures |
| Derived/computed | Cross-validation, precision/recall, confusion matrices, ablation studies |
| Compiled/aggregated | Source verification, completeness analysis, consistency checks across sources |

---

### 8. Usage Notes (optional, typical: 150–1,200 words)

| Criterion | Score (0–3) | Notes |
|---|---|---|
| **Practical access guidance**: How to download and work with the data | 0–3 | Software recommendations, file handling tips |
| **Known caveats**: Limitations users should be aware of | 0–3 | e.g., "not suitable for X", "resolution insufficient for Y" |
| **Appropriate use cases**: Guidance on what the data is/isn't suitable for | 0–3 | Helps users avoid misuse |
| **Not a conclusions section**: No selling points or worked case studies | 0–3 | Practical, not promotional |

**Target: ≥ 9/12**

---

### 9. Code Availability (required, even if no custom code)

| Criterion | Pass | Fail |
|---|---|---|
| Statement present | Yes | No |
| Repository URL provided (if applicable) | Yes | No |
| Language, version, dependencies noted | Yes | No |
| If no custom code, explicitly states so | Yes | No |

---

### 10. Data Availability (required)

| Criterion | Pass | Fail |
|---|---|---|
| Repository name and URL | Yes | No |
| Accession numbers / DOIs | Yes | No |
| Repeats key info from Data Records (for indexing) | Yes | No |
| Data deposited in recognized repository | Yes | No |

---

### 11. References & Data Citations

| Criterion | Pass | Fail |
|---|---|---|
| All datasets cited with formal data citation format | Yes | No |
| Format: authors, title, repository, DOI URL, year | Yes | No |
| DOIs as `https://doi.org/...` | Yes | No |
| Numbered sequentially with superscripts | Yes | No |

---

### 12. Remaining Required Sections

| Section | Required | Notes |
|---|---|---|
| Author Contributions | Yes | Brief description per author |
| Competing Interests | Yes | Positive or negative declaration |
| Funding | Yes | Organizations + grant numbers; state if unfunded |
| Acknowledgements | Optional | No funding info, no thanks to editors |
| Ethics Statement | If applicable | Sub-heading within Methods for human/animal data |

---

## Figures & Tables Limits

| Element | Guideline |
|---|---|
| Figures | Recommended ≤ 8 |
| Tables | Recommended ≤ 10 |
| Figure legends | ≤ 350 words each |
| Supplementary Info | Single PDF, ≤ 10 MB, discouraged unless >10 pages of content |
| Oversize tables | Submit as .xlsx or .csv |

---

## Overall Manuscript Checklist

### Before First Submission (single PDF with embedded figures)

- [ ] Title ≤ 110 chars, no colons/parentheses/acronyms/advertising
- [ ] Abstract ≤ 170 words, no claims or URLs
- [ ] All required sections present with correct headings
- [ ] No results, discussion, analysis, or conclusions anywhere
- [ ] No subjective claims about novelty/impact/importance
- [ ] Data accessible via anonymous download URL
- [ ] All input datasets cited with formal data citation format
- [ ] Code availability statement present
- [ ] Technical Validation includes independent/quantitative quality checks
- [ ] Limitations explicitly acknowledged
- [ ] Author Contributions, Competing Interests, Funding sections complete

### Before Revised Submission

- [ ] Data deposited in formal recognized repository with DOI
- [ ] Machine-readable manuscript (.docx or .tex, no PDF)
- [ ] Clean copy — no tracked changes
- [ ] Figures uploaded as separate files
- [ ] Response document addresses ALL reviewer/editor comments
- [ ] Oversize tables as .xlsx/.csv

---

## Writing Style Guide

| Do | Don't |
|---|---|
| Use measured, factual language | Use superlatives or advertising language |
| Be quantitatively precise ("3,230 stations", "0.5° resolution") | Be vague ("many stations", "high resolution") |
| Acknowledge limitations transparently | Oversell or hide weaknesses |
| Compare against existing alternatives | Ignore prior work |
| Write for scientists from diverse backgrounds | Use unexplained jargon |
| Define abbreviations at first use | Use abbreviation lists |
| Use "we" + active voice for methods | Use unnecessarily passive constructions |
| Focus on reproducibility | Assume reader expertise |

---

## Typical Length Benchmarks (from highly-cited articles)

| Section | Words |
|---|---|
| Abstract | 100–170 |
| Background & Summary | 800–2,500 |
| Methods | 1,200–4,500 |
| Data Records | 400–1,500 |
| Data Overview | 0–200 |
| Technical Validation | 300–4,500 |
| Usage Notes | 150–1,200 |
| **Total** | **5,000–12,000** |

Most successful papers fall in the **7,000–11,000 word** range.

---

## Review Criteria (what editors/reviewers assess)

Scientific Data does NOT assess perceived significance or impact. Acceptance is based on:

1. **Technical soundness** — Are the methods correct and appropriate?
2. **Community standards** — Is the data shared in appropriate formats and repositories?
3. **Completeness** — Is the description sufficient for reuse?
4. **Usefulness** — Would at least one other research group find this data useful?

All technically sound papers are accepted. The bar is rigor and transparency, not novelty.
