# Methods: Rubric and Instructions

## Purpose
Describes, in sufficient detail for reproduction, how the dataset was created. Covers data acquisition and computational processing. A reader should be able to recreate the dataset using only this section and the cited source data.

It does NOT present results, analyses, quality assessments, or arguments for importance.

## Voice and Style
Past tense for actions taken ("we scraped"). Present tense for algorithms ("the kernel assigns weights"). Precise, procedural, sequentially organized. Inherit all avoid-list rules from the Introduction rubric.

## Structural Template (1,500-4,000 words)

### Input Data Source Table (required)
Include a table with columns: Source, Provider, Resolution, Temporal coverage. Cite each source.

### Subsections (in pipeline order)
Organize by processing step. Typical structure:

1. **Data sources** (200-400 words + table)
2. **Data collection/acquisition** (200-400 words): How raw data was obtained (API, scraping, download). Fields extracted, parsing, defaults.
3. **Geocoding** (100-200 words, if applicable): Service used, matching strategy, assignment to geographic units.
4. **Population/denominator data** (100-200 words, if applicable): Survey, table, variables, vintage.
5. **Travel time / spatial computation** (100-200 words, if applicable): Routing engine, matrix scope, travel mode.
6. **Core measure computation** (400-800 words): Full mathematical formulation with numbered equations. Define every variable. State every parameter value. Justify parameter choices.
7. **Geographic aggregation** (100-200 words): Target levels, aggregation method per measure type.
8. **Software and computational environment** (50-100 words): Python version, all library versions, external service versions.

### Equations
- Number sequentially: (1), (2), (3)
- Define every variable immediately after
- Use consistent notation throughout
- For FCA methods: write out the kernel function, each step, normalization, and final ratio

## Citation Requirements
- 5-10 citations: 1 per input source, 1-2 for core methodology, 1 for routing engine/geocoder
- Use `\citep{}` for parenthetical citations

## Quality Checklist
- [ ] Every input dataset named, versioned, and cited
- [ ] Input data source table included
- [ ] All equations written out with variables defined
- [ ] All parameter values stated with justification
- [ ] All software versions stated
- [ ] Pipeline order from raw inputs to final outputs
- [ ] No results or quality assessments
- [ ] Sufficient detail for replication
- [ ] 1,500-4,000 words, 5-10 citations

## Execution Steps
1. Read all code files and pipeline.yaml. Map the pipeline sequentially.
2. Check pyproject.toml/uv.lock for exact library versions. Check Python version.
3. For any computational step with formulas, translate code to math notation.
4. Build the input data source table.
5. Draft each subsection following pipeline order.
6. Verify citations.
7. Run LLM language check.
