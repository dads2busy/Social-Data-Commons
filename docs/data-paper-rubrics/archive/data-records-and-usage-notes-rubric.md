# Data Records and Usage Notes: Rubric and Step-by-Step Instructions

Guides for writing the Data Records and Usage Notes sections of a Scientific Data "Data Descriptor" article. Designed to be followed by an LLM or human author.

---

# Part 1: Data Records

## Purpose

The Data Records section tells the reader exactly what the dataset contains and where to find it. It is a reference section, not a narrative. A reader should be able to locate, download, and understand the structure of every file in the dataset using only this section.

It does NOT:
- Present summary statistics or analyses (those go in the optional Data Overview).
- Describe how the data was produced (that belongs in Methods).
- Evaluate data quality (that belongs in Technical Validation).
- Describe how to use the data (that belongs in Usage Notes).

## Voice and Style

Inherit all rules from the Background & Summary rubric. Additionally:
- This is the most reference-like section. Short, declarative sentences. No narrative arc needed.
- Use tables for file inventories and column definitions.
- Be precise about file formats, compression, column names, and data types.

## Structural Template (400-1,000 words)

### Paragraph 1: Repository and Access (50-100 words)
- Name the repository where the dataset is deposited.
- State the DOI or persistent identifier.
- State the license.
- Cite the dataset using the Scientific Data data citation format.

### File Inventory Table
- One row per output file (or file group).
- Columns: Filename, Format, Size, Description, Geographic level, Temporal coverage.

### Paragraph 2: Schema Description (100-200 words)
- Describe the data format (long format, wide format, etc.).
- List all column names with their data types and meanings.
- Define any codes, abbreviations, or conventions used.

### Paragraph 3: Measure Definitions (100-300 words)
- For each variable/measure in the dataset, state:
  - The variable name as it appears in the data.
  - A plain-language description.
  - The unit of measurement.
  - The measure type (count, ratio, index, etc.).
- A table works well here.

### Paragraph 4: Scale and Coverage (50-100 words)
- State the total number of records.
- State the number of geographic units at each level.
- State the temporal coverage.
- State the geographic scope.

## Quality Checklist

- [ ] Repository named with DOI
- [ ] File inventory table with filenames, formats, and sizes
- [ ] All column names defined
- [ ] All measures defined with units
- [ ] Total record count stated
- [ ] Geographic unit counts stated per level
- [ ] No summary statistics (save for Data Overview or Technical Validation)
- [ ] Formal data citation for the deposited dataset
- [ ] No em dashes, no LLM-typical phrases

## Step-by-Step Execution (for LLM agents)

1. Read the dataset output files and record: filenames, formats, sizes, column names, data types.
2. Read measure_info.json for variable definitions.
3. Read pipeline.yaml for scope and coverage.
4. Count records, geographic units per level, and years.
5. Look up the Zenodo deposit for the DOI.
6. Draft the section following the structural template.
7. Style check and citation verify.

---

# Part 2: Usage Notes

## Purpose

The Usage Notes section provides practical guidance for users of the dataset. It helps researchers who have downloaded the data understand how to work with it, what to watch out for, and what the data is and is not suitable for.

It does NOT:
- Serve as a conclusions section.
- Contain selling points or worked case studies.
- Repeat Methods or Technical Validation content.

## Voice and Style

Inherit all rules from the Background & Summary rubric. Additionally:
- This section is addressed directly to the future user of the data.
- Practical, advisory tone. "Users should be aware that..." is appropriate.
- Short, actionable paragraphs.

## Structural Template (300-800 words)

### Paragraph 1: File Access and Software (50-100 words)
- State how to download the data.
- Recommend software for opening the file formats used.
- Note any decompression steps needed.

### Paragraph 2: Interpreting the Measures (100-200 words)
- Provide guidance on how to interpret the key measures.
- What does a high or low value mean?
- Are there reference thresholds from the literature?
- What is the expected range of values?

### Paragraph 3: Scope Limitations (50-150 words)
- Restate (briefly) the most important scope limitations that affect how the data can be used.
- What populations or facilities are excluded?
- What geographic areas are covered and not covered?

### Paragraph 4: Temporal Comparability (50-150 words)
- If multiple time points are included, note any comparability caveats.
- Different source vintages, methodology changes, or definitional shifts.

### Paragraph 5: Recommended and Inappropriate Uses (50-150 words)
- Name 2-3 appropriate use cases.
- Name 1-2 uses the data is not suitable for.

## Quality Checklist

- [ ] Software recommendations for file formats stated
- [ ] Interpretation guidance for key measures provided
- [ ] Scope limitations restated for user awareness
- [ ] Temporal comparability caveats noted
- [ ] Appropriate and inappropriate uses named
- [ ] Not a conclusions section (no selling, no case studies)
- [ ] No em dashes, no LLM-typical phrases
- [ ] Word count 300-800

## Step-by-Step Execution (for LLM agents)

1. Read the output files to understand formats and compression.
2. Read measure_info.json for variable descriptions and units.
3. Read the Technical Validation Known Limitations section for scope caveats.
4. Research interpretation guidance: are there published thresholds for child care accessibility ratios?
5. Draft the section following the structural template.
6. Style check.
