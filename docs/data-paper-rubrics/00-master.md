# Data & Policy Data Paper: Master Orchestration Guide

Use this document to write a complete Data & Policy "Data Paper" from a dataset in the SDC monorepo. Follow the phases in order. Each phase references a numbered rubric file in this directory.

---

## Quick Start

When the user says: **"Write a Data & Policy Data Paper on [dataset name]"**

1. Locate the dataset directory in `~/git/sdc-monorepo/`
2. Read all documentation: `pipeline.yaml`, `measure_info.json`, `ingest.py`, `scrape.py`, `prepare.py`, any `docs/` files
3. Follow the phases below in order

---

## Phase 1: Research and Planning

### 1.1 Understand the dataset
Read all code and documentation. Record:
- Geographic scope, temporal coverage, spatial resolution
- Number of measures and what they are
- Data sources (with URLs)
- Core methodology
- Key parameters and assumptions
- Zenodo deposit ID (if exists)
- Software versions (from pyproject.toml / uv.lock)

### 1.2 Research the literature
Launch **two parallel research agents**:
- **Agent A**: Problem domain (government statistics, consequences, policy analyses). Target: 8-12 citations.
- **Agent B**: Existing datasets, prior spatial analyses, methodological papers. Target: 12-18 citations.

All citations must be from academic journals, books, or official government documents. No blogs, news, or Wikipedia.

### 1.3 Plan the article structure
Confirm which Technical Validation analyses are possible with the available data. Identify what validation analyses need to be run.

---

## Phase 2: Write Sections (parallel where possible)

Write each section following its rubric. Sections can be drafted in parallel since they are independent.

| Section | Rubric | Depends on |
|---|---|---|
| Abstract | `01-abstract.md` | All other sections (write last or update last) |
| Policy Significance | `02-policy-significance.md` | Domain understanding |
| Introduction | `03-introduction.md` | Literature research (Phase 1.2) |
| Methods | `04-methods.md` | Code reading (Phase 1.1) |
| Data Records | `05-data-records.md` | Output file inspection |
| Technical Validation | `06-technical-validation.md` | Validation analyses (must run code) |
| Usage Notes | `07-usage-notes.md` | Data Records + Technical Validation |

**Recommended execution order:**
1. Introduction + Methods (in parallel, both depend only on Phase 1)
2. Data Records (quick, depends on file inspection)
3. Technical Validation (longest, requires running analyses and generating figures)
4. Usage Notes (depends on Data Records + TV known limitations)
5. Abstract + Policy Significance (update/finalize after all sections complete)

### After each section:
- Run **citation verification agent** on new citations (see `08-references.md`)
- Run **LLM language check agent** on the section text (see `09-llm-language-check.md`)
- Fix all issues before proceeding

---

## Phase 3: Generate Figures

Technical Validation requires 4-6 figures. Install matplotlib/seaborn if needed (`uv add --dev matplotlib seaborn`). Typical figures:

1. **Distribution figure**: Histogram of key input variable (e.g., capacity, provider count)
2. **Summary statistics table**: Rendered as a figure or LaTeX table
3. **Choropleth map**: Spatial distribution of primary measure at county level
4. **Temporal scatter**: Year 1 vs Year 2 at block group level (if multi-year)
5. **Convergent validity scatter**: Computed measure vs simpler alternative
6. **Sensitivity analysis**: Parameter sensitivity curves
7. **Urban-rural boxplots**: Measure distribution by urbanicity class

All figures: 300 DPI, white background, sans-serif font, clear axis labels, no decorative elements.

---

## Phase 4: Assemble LaTeX Document

Follow `10-latex-formatting.md` exactly.

1. Copy CUP template files to article directory: `CUP-JNL-DAP.cls`, `CUP_Logo.eps`, `DAP_Logo_RGB.eps`, `orcid_logo.eps`
2. Copy figures to `article/figures/`
3. Assemble all sections into `main.tex` using the CUP Frontmatter/Backmatter structure
4. Convert all citations to natbib author-year format (`\citep{}`, `\citet{}`)
5. Format all references in CUP style, alphabetical order (see `08-references.md`)
6. Add Backmatter: Acknowledgments (with AI disclosure), Funding, Competing Interests, Data Availability, Ethical Standards, Author Contributions
7. Compile with `pdflatex` (two passes for references)

---

## Phase 5: Final Review

### 5.1 Full-article LLM language check
Dispatch `09-llm-language-check.md` agent on the complete `main.tex`. Fix all issues.

### 5.2 Full-article review
Dispatch `12-final-review.md` agent on the complete `main.tex`. Fix all BLOCKING and MINOR issues.

### 5.3 Recompile and verify
Compile twice. Verify no undefined references, no errors. Check PDF visually.

---

## Phase 6: Submission Preparation

### 6.1 Write cover letter
Follow `11-cover-letter.md`. Output as plain text (submitted via web form, not file upload).

### 6.2 Identify reviewers
Follow `13-reviewer-identification.md`. Identify 3-4 qualified reviewers with verified emails.

### 6.3 Prepare submission metadata
- Title
- Abstract (plain text, ≤ 250 words)
- Keywords (comma-delimited, 5-8)
- Cover letter text
- Competing interests declaration: "Competing interests: The author(s) declare none."
- Number of figures
- Number of tables
- Recommended reviewers (name, institution, email)
- AI use declaration: select yes, with disclosure in Acknowledgments
- Social media text (≤ 280 characters)

### 6.4 Create submission zip
```bash
zip -r submission.zip main.tex main.pdf CUP-JNL-DAP.cls CUP_Logo.eps DAP_Logo_RGB.eps orcid_logo.eps figures/*.png
```

---

## Rubric Files Index

| # | File | Contents |
|---|---|---|
| 00 | `00-master.md` | This orchestration guide |
| 01 | `01-abstract.md` | Abstract (250 words, standalone) |
| 02 | `02-policy-significance.md` | Policy Significance Statement (120 words, D&P-specific) |
| 03 | `03-introduction.md` | Introduction / Background (1,200-2,500 words, 15-30 citations) |
| 04 | `04-methods.md` | Methods (1,500-4,000 words, equations, source table, versions) |
| 05 | `05-data-records.md` | Data Records (400-1,000 words, file inventory, schema) |
| 06 | `06-technical-validation.md` | Technical Validation (1,500-4,000 words, figures, limitations) |
| 07 | `07-usage-notes.md` | Usage Notes (300-800 words, interpretation, caveats) |
| 08 | `08-references.md` | Reference management (verification protocol, CUP format) |
| 09 | `09-llm-language-check.md` | LLM language detection and substitution |
| 10 | `10-latex-formatting.md` | CUP-JNL-DAP LaTeX template specifics |
| 11 | `11-cover-letter.md` | Cover letter (plain text for web form) |
| 12 | `12-final-review.md` | Pre-submission review checklist |
| 13 | `13-reviewer-identification.md` | Peer reviewer identification protocol |

---

## Parallel Agent Strategy

To maximize efficiency, use this agent dispatch pattern:

**Phase 1 (parallel):**
- Agent A: Domain literature research
- Agent B: Existing datasets + methodology research

**Phase 2 (parallel batch 1):**
- Agent C: Draft Introduction (needs Phase 1 results)
- Agent D: Draft Methods (needs only code reading)
- Agent E: Draft Data Records (needs only file inspection)

**Phase 2 (sequential, after batch 1):**
- Agent F: Run Technical Validation analyses (needs actual data)
- Draft Technical Validation from analysis results
- Draft Usage Notes (needs TV known limitations)
- Finalize Abstract + Policy Significance

**Phase 2 verification (parallel, after each section):**
- Citation verification agent (per section)
- LLM language check agent (per section)

**Phase 4-5 (sequential):**
- Assemble LaTeX
- Full-article LLM check
- Full-article final review
- Fix issues, recompile

**Phase 6 (parallel):**
- Cover letter agent
- Reviewer identification agent

---

## Total Expected Output
- 1 LaTeX article (`main.tex`), ~8,000 words, 25-35 citations, 6 tables, 6 figures, 5 equations
- 1 compiled PDF (`main.pdf`), ~16 pages
- 1 cover letter (plain text)
- 3-4 recommended reviewers
- Submission metadata (title, abstract, keywords, competing interests, social media text)
- Submission zip file
