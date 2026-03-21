# Introduction (Background & Summary): Rubric and Instructions

## Purpose
The opening narrative section. In Data & Policy, this is titled "Introduction" (not "Background & Summary" as in Scientific Data). It establishes the problem context, surveys existing data resources, identifies the gap, introduces the dataset, and describes reuse value.

It does NOT:
- Report findings, results, or analyses
- Make subjective claims about novelty, importance, or impact
- Use promotional language

## Voice and Style Rules

### Emulate
Measured, precise, factual. Sentences are declarative. Claims supported by citations. The writing trusts the reader to draw conclusions about value.

### Avoid (hard rules)

| Pattern | Use instead |
|---|---|
| Em dashes (---) | Commas, semicolons, parentheses, or restructured sentences |
| "Novel", "unique", "first-of-its-kind", "unprecedented" | Describe what the dataset does without superlatives |
| "In recent years", "It is well known", "It is worth noting" | Delete or replace with specific factual statement |
| "This paper presents", "We introduce" | "This data paper documents..." or "The dataset described here..." |
| "Comprehensive", "robust", "cutting-edge" | Specific descriptions |
| "Plays a crucial role", "is of paramount importance" | State the specific consequence |
| "Furthermore", "Moreover", "Additionally" as paragraph openers | Vary sentence structure |
| "A plethora of", "a myriad of" | "Several", "multiple", or a specific count |
| "Aims to", "seeks to" | State what the dataset does |
| "Leverages", "utilizes" | "Uses" |
| "Delve", "delves into" | "Examines", "describes", "addresses" |
| "Landscape", "ecosystem" (metaphorical) | "Existing datasets", "available resources" |

### Sentence-Level Guidelines
- Active voice with "we" for author actions
- Short, direct sentences (split if over 35 words)
- Quantify wherever possible
- Define technical terms at first use
- Past tense for completed work, present tense for general truths

## Structural Template (6 Paragraphs, 1,200-2,500 words)

### Paragraph 1: Policy Context (150-300 words)
Open with a policy data gap statement, then ground in concrete, quantifiable facts with citations. Lead with why policymakers need this data. End transitioning toward the data gap.
- 4-6 citations

### Paragraph 2: Why Spatial/Granular Data Matters (100-200 words)
Explain why the specific type of data (spatial, temporal, high-resolution) is needed. Name existing surveys and their limitations (resolution, scope). Connect to your dataset's resolution.
- 2-4 citations

### Paragraph 3: Existing Data Resources (200-400 words)
Survey 5-8 specific existing datasets, studies, or data products. For each: what it covers, at what resolution, and its key limitation. Use `\citet{}` for author-prominent citations. Be factual, not dismissive.
- 5-10 citations

### Paragraph 4: The Methodological Gap (150-250 words)
Synthesize limitations from Paragraph 3 into a clear gap statement. Introduce the methodology (e.g., floating catchment area) with citations. Explain why it is appropriate for this domain.
- 3-5 citations

### Paragraph 5: Dataset Introduction (150-300 words)
Geographic scope, temporal coverage, spatial resolution, number of measures. Name primary data sources. Briefly describe methodology (1-2 sentences). Describe, do not sell.
- 2-4 citations

### Paragraph 6: Reuse Value (100-200 words)
Name 2-4 specific use cases. If the dataset is in use (dashboard, agency), state as fact. Mention open availability, code availability, reproducibility.
- 1-3 citations

## Citation Requirements
- All from academic journals, books, or official government documents
- No blog posts, news articles, Wikipedia, or advocacy white papers
- Target: 15-30 citations across the section
- Use `\citep{}` for parenthetical and `\citet{}` for author-prominent

## Quality Checklist
- [ ] Opens with a policy-relevant statement (not a platitude)
- [ ] Cites 3+ existing datasets/resources by name with specific limitations
- [ ] Zero superlatives or advertising language
- [ ] Zero em dashes
- [ ] Zero LLM-typical phrases
- [ ] Every factual claim has a citation
- [ ] All citations verified by independent agent
- [ ] No results, conclusions, or analyses
- [ ] Dataset intro is descriptive, not promotional
- [ ] 1,200-2,500 words, 15-30 citations

## Execution Steps
1. Read all dataset documentation (pipeline.yaml, measure_info.json, code).
2. Research the problem domain: government statistics, consequences, policy analyses (4-6 citations).
3. Research existing datasets in the same domain (5-8 citations).
4. Research the methodology (3-5 citations).
5. Draft following the 6-paragraph template.
6. Verify all citations via separate agent.
7. Run LLM language check.
8. Verify word count 1,200-2,500 and citation count 15-30.
