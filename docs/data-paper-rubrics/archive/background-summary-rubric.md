# Background & Summary: Rubric and Step-by-Step Instructions

A guide for writing the Background & Summary section of a Scientific Data "Data Descriptor" article. Designed to be followed by an LLM or human author.

---

## Purpose of This Section

The Background & Summary is the opening narrative of a Data Descriptor. It serves three functions:

1. **Establish the problem context** that motivates the dataset's existence.
2. **Survey the landscape** of existing data resources and their limitations.
3. **Introduce the dataset** as a response to an identified gap, describing its scope and potential reuse value.

It does NOT:
- Report findings, results, or analyses.
- Make subjective claims about novelty, importance, or impact.
- Use promotional language.

---

## Voice and Style Rules

### Emulate
The tone of highly cited Data Descriptors is **measured, precise, and factual**. Sentences are declarative. Claims are supported by citations. The writing trusts the reader to draw their own conclusions about value.

**Good patterns observed in top articles:**
- "Several global climate datasets exist, but none provides monthly temporal resolution at sub-kilometer spatial scales." (TerraClimate)
- "Existing training datasets are limited by geographic coverage, spatial resolution, observation density, time span, or quality." (Global Land Cover)
- "While these data have been widely used, they do not account for orographic effects on precipitation at fine spatial scales." (CHELSA)

### Avoid

| Pattern to avoid | Why | Use instead |
|---|---|---|
| Em dashes (--) | Banned per user spec | Commas, semicolons, parentheses, or restructured sentences |
| "Novel", "unique", "first-of-its-kind", "unprecedented" | Advertising language; banned by journal | Describe what the dataset does without superlatives |
| "In recent years", "It is well known", "It is worth noting" | LLM-typical filler phrases | Delete or replace with a specific factual statement |
| "This paper presents", "We introduce" | Overused in AI-generated text | "This Data Descriptor documents..." or "The dataset described here..." |
| "Comprehensive", "robust", "cutting-edge" | Vague superlatives | Specific descriptions of what is included and how |
| "Plays a crucial role", "is of paramount importance" | Inflated hedging | State the specific consequence or dependency |
| "Furthermore", "Moreover", "Additionally" as paragraph openers | Mechanical transitions typical of LLM text | Vary sentence structure; let logical flow carry the narrative |
| "A plethora of", "a myriad of" | Overused by LLMs | "Several", "multiple", or a specific count |
| "Aims to", "seeks to" | Vague intentionality | State what the dataset does, not what it aspires to |
| "Leverages", "utilizes" | Corporate jargon | "Uses" |
| "Delve", "delves into" | Strongly associated with LLM output | "Examines", "describes", "addresses" |
| "Landscape", "ecosystem" (metaphorical) | Overused in AI text | "Existing datasets", "available resources", "prior work" |

### Sentence-Level Guidelines
- Prefer active voice with "we" for actions the authors took.
- Prefer short, direct sentences. If a sentence exceeds 35 words, consider splitting it.
- Quantify wherever possible: "4,200 licensed facilities" not "thousands of facilities."
- Define technical terms at first use.
- Use past tense for completed work ("we compiled", "the survey collected"), present tense for general truths ("childcare access varies by region").

---

## Structural Template (6 Paragraphs)

The section should contain approximately 1,200 to 2,500 words organized into 5 to 7 paragraphs following this structure:

### Paragraph 1: Problem Context (150-300 words)
**Goal:** Establish why this domain matters, grounded in factual statements with citations.

- Open with a concrete, quantifiable statement about the problem domain.
- Cite 2-4 sources establishing the societal, economic, or scientific significance.
- Do not editorialize. Let the cited facts speak.
- End with a sentence that transitions toward the data gap.

**Template:**
> [Concrete quantitative statement about the problem]. [Citation]. [Second factual statement about consequences or dependencies]. [Citation]. [Statement connecting the problem to data needs]. [Citation].

### Paragraph 2: Why Spatial Data Matters for This Domain (100-200 words)
**Goal:** Establish that the specific type of data (spatial, temporal, high-resolution, etc.) your dataset provides is needed.

- Explain why location-specific or spatially resolved data is necessary for this domain.
- Cite 1-3 methodological or policy sources.
- Connect to the geographic or temporal resolution your dataset provides.

### Paragraph 3: Existing Data Resources (200-400 words)
**Goal:** Survey what data already exists, with specific citations, and identify limitations.

- Name 3-8 specific existing datasets, surveys, or data products.
- For each, state: what it covers, at what resolution, and its key limitation.
- Organize by type (national surveys, administrative records, derived measures) or by limitation theme.
- Be factual, not dismissive. These are not bad datasets; they have different purposes or scopes.
- Use a pattern like: "[Dataset X] provides [coverage] at [resolution], but [limitation relevant to your dataset's contribution]."

### Paragraph 4: The Methodological Gap (150-250 words)
**Goal:** Identify what is missing from the existing data landscape.

- Synthesize the limitations from Paragraph 3 into a clear gap statement.
- If your dataset uses a specific methodology (e.g., floating catchment area analysis), introduce it here with citations to the methodological literature.
- Explain why this methodology is appropriate for the domain.

### Paragraph 5: Dataset Introduction (150-300 words)
**Goal:** Describe what the dataset is, what it contains, and how it was produced, at a high level.

- State the geographic scope, temporal coverage, spatial resolution, and number of measures.
- Name the primary data sources.
- Briefly describe the methodology (1-2 sentences; details go in Methods).
- Do not use promotional language. Describe, do not sell.

### Paragraph 6: Reuse Value (100-200 words)
**Goal:** Describe concrete downstream uses without making subjective claims.

- Name 2-4 specific use cases (policy analysis, equity research, program evaluation, cross-temporal comparison).
- If the dataset is already in use (e.g., in a dashboard), state this as a fact.
- Close with a sentence on the open availability of the data.

---

## Citation Requirements

### Source Types (required)
All citations must come from one of:
- Peer-reviewed academic journal articles
- Academic books or book chapters (with ISBN or DOI)
- Official government reports or data documentation (e.g., Census Bureau technical documentation, USDA reports, HHS publications)

### Source Types (prohibited)
- Blog posts, news articles, or opinion pieces
- Wikipedia
- Preprints (unless deposited on a recognized server AND no peer-reviewed version exists)
- Marketing materials, white papers from advocacy organizations (unless government-commissioned)
- URLs without institutional backing

### Citation Density
- Target: 15-30 citations across the section
- Paragraph 1 (problem context): 3-5 citations
- Paragraph 2 (why spatial data): 2-4 citations
- Paragraph 3 (existing resources): 5-10 citations (one per dataset/resource discussed)
- Paragraph 4 (methodological gap): 3-5 citations
- Paragraph 5 (dataset intro): 2-4 citations (to data sources and methods)
- Paragraph 6 (reuse value): 1-3 citations

### Citation Format
Use numbered superscripts in text, with full references in a numbered list at the end. Follow Scientific Data reference format:
```
Author(s). Title. Journal Volume, Pages (Year). DOI
```

For government documents:
```
Agency. Title. Report/Publication Number (Year). URL
```

### Citation Verification Protocol
Every citation must be verified by a separate agent before inclusion. Verification checks:
1. The paper/report exists and is findable via DOI, PubMed, or official URL.
2. The author list matches.
3. The year matches.
4. The journal/publisher matches.
5. The claim attributed to the citation is actually supported by the source.

If a citation cannot be verified, it must be flagged and either corrected or removed. Fabricated citations are unacceptable under any circumstances.

---

## Quality Checklist

Before finalizing, verify:

- [ ] Opens with a concrete, quantifiable problem statement (not a platitude)
- [ ] Cites 3+ existing datasets/resources by name with specific limitations
- [ ] Contains zero superlatives or advertising language
- [ ] Contains zero em dashes
- [ ] Contains zero LLM-typical phrases (see avoid list above)
- [ ] Every factual claim has a citation
- [ ] All citations are from journals, books, or government documents
- [ ] All citations have been independently verified
- [ ] No results, conclusions, or analyses are presented
- [ ] Dataset introduction is descriptive, not promotional
- [ ] Reuse value paragraph names specific use cases, not vague possibilities
- [ ] Total length is 1,200-2,500 words
- [ ] 15-30 citations total
- [ ] Technical terms defined at first use
- [ ] Transitions between paragraphs are logical, not mechanical

---

## Step-by-Step Execution Instructions (for LLM agents)

### Step 1: Understand the Dataset
Read all available documentation:
- `pipeline.yaml` (scope, sources, years)
- `measure_info.json` (variable definitions, provenance)
- `zenodo_description.md` (methodology overview)
- Source code (`ingest.py`, `scrape.py`) for technical details
- Any existing README or documentation

Record: geographic scope, temporal coverage, spatial resolution, number of measures, data sources, methodology name, and key assumptions.

### Step 2: Research the Problem Domain
Search for:
- Government statistics on the problem domain (e.g., federal agency reports)
- Peer-reviewed studies on societal/economic consequences
- Policy analyses connecting data availability to decision-making

Collect 4-6 citations with exact DOIs and verify each.

### Step 3: Research Existing Datasets
Search for:
- Named datasets in the same domain (search: "[domain] dataset" OR "[domain] data" in Google Scholar)
- Survey instruments and administrative data sources
- Prior studies that created similar measures

For each dataset found, record: name, coverage, resolution, what it measures, and its primary limitation relative to your dataset. Collect 5-8 citations.

### Step 4: Research the Methodology
Search for:
- The original paper describing the method (e.g., floating catchment area method)
- Applications of the method in similar domains
- Methodological reviews or comparisons

Collect 3-5 citations, starting with the seminal paper.

### Step 5: Draft the Section
Follow the 6-paragraph structural template. Write in the voice described above. Do not use any phrase from the "avoid" list. Do not use em dashes.

### Step 6: Verify All Citations
Dispatch a separate verification agent. For each citation:
1. Search for the paper by DOI or title + author
2. Confirm it exists
3. Confirm the attributed claim matches the source content
4. Flag any citation that cannot be verified

### Step 7: Revise
- Remove any unverified citations and rewrite affected sentences.
- Check the quality checklist.
- Ensure word count is within 1,200-2,500 words.
- Read the section aloud (or simulate reading) to catch awkward phrasing, mechanical transitions, or LLM-typical patterns.

### Step 8: Final Check
- Grep for em dashes and remove any found.
- Grep for words in the avoid list.
- Confirm citation count is 15-30.
- Confirm every paragraph serves its designated structural role.
