# Data Records: Rubric and Instructions

## Purpose
Tells the reader exactly what the dataset contains and where to find it. A reference section, not a narrative.

It does NOT present summary statistics, methods, quality assessments, or usage guidance.

## Structural Template (400-1,000 words)

### Repository and Access (50-100 words)
- Name the repository (Zenodo, Dataverse, etc.)
- State the DOI or persistent identifier
- State the license
- Cite the dataset using formal data citation format

### File Inventory Table (required)
One row per output file. Columns: Filename, Format, Size, Description.

### Schema Description (100-200 words)
- Data format (long format, wide format)
- List all column names with data types and meanings
- Define codes, abbreviations, conventions

### Measure Definitions Table (required)
One row per measure. Columns: Measure name, Unit, Type, Description.

### Scale and Coverage (50-100 words)
- Total number of records
- Number of geographic units at each level
- Temporal coverage (years)
- Geographic scope

## Quality Checklist
- [ ] Repository named with DOI
- [ ] File inventory table
- [ ] All column names defined
- [ ] All measures defined with units
- [ ] Total record count stated
- [ ] Geographic unit counts per level
- [ ] No summary statistics
- [ ] Formal data citation

## Execution Steps
1. Read output files: filenames, formats, sizes, column names, data types.
2. Read measure_info.json for variable definitions.
3. Read pipeline.yaml for scope/coverage.
4. Count records, geographic units per level, years.
5. Look up Zenodo DOI.
6. Draft following template.
