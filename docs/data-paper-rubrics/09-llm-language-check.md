# LLM Language Detection and Substitution: Protocol

## Purpose
Ensure the finished article contains no phrases, patterns, or structural tells commonly associated with LLM-generated text.

## When to Run
1. After drafting each section (before combining)
2. After combining all sections into the final document (full-article sweep)
3. Before final submission

## Execution
Dispatch a **separate agent** with the file path. The agent reads the entire document and checks every sentence against the rules below.

## Banned Phrases (exact match, case-insensitive)

### Category 1: Known LLM filler phrases
- "in recent years"
- "it is well known" / "it is widely known"
- "it is worth noting" / "it is important to note"
- "this paper presents" / "this study presents"
- "we introduce" / "we present" (use "This data paper documents...")
- "in conclusion" / "to summarize"

### Category 2: Vague superlatives and promotional language
- "comprehensive" (as vague superlative, not describing specific scope)
- "robust" (not in statistical context)
- "cutting-edge" / "state-of-the-art"
- "novel" / "unique" / "first-of-its-kind" / "unprecedented"
- "groundbreaking"
- "plays a crucial/vital/key role"
- "is of paramount/great importance"

### Category 3: LLM-typical vocabulary
- "leverages" / "utilizes" (use "uses")
- "delve" / "delves" / "delving"
- "landscape" / "ecosystem" (metaphorical)
- "a plethora of" / "a myriad of"
- "multifaceted" / "nuanced" / "pivotal"
- "foster" / "fosters" / "bolster" / "bolsters"
- "navigate" / "navigating" (metaphorical)
- "realm" / "embark" / "intricate"
- "harness" / "harnessing"
- "shed light on" / "pave the way"
- "a testament to" / "tapestry"
- "underscore" / "underscores"

### Category 4: Mechanical transitions
- "Furthermore," / "Moreover," / "Additionally," as paragraph or sentence openers
- "aims to" / "seeks to" / "strives to"

### Category 5: Formatting
- Em dashes ("---") in narrative prose (en-dashes "--" for number ranges are fine)

## Structural Patterns to Flag
- Sentences beginning with "This" + generic noun ("This approach", "This methodology")
- Excessive use of "importantly" or "notably"
- Paragraphs ending by restating what was just said
- "By [gerund], [result]" constructions
- Lists introduced with "several key" or "a number of"
- Sentences structured as "It is [adjective] to [verb]"

## Tone Indicators to Flag
- Sentences that "sell" the work rather than describe it
- Performative hedging ("it should be noted that")
- Promotional adjectives applied to the authors' own work
- Vague intensifiers ("significant" not in statistical sense, "substantial" without quantification)

## Substitution Guidelines

| Found | Replace with |
|---|---|
| "significant [noun]" (non-statistical) | Quantify: "a 34% decline in..." |
| "substantial" (unquantified) | Either quantify or delete |
| "comprehensive" (vague) | Describe specific scope |
| "leverages" / "utilizes" | "uses" |
| "Furthermore," opener | Delete or restructure |
| "aims to" / "seeks to" | State what it does |
| "full reproducibility" | "reproducibility" |
| "landscape" (metaphorical) | "existing datasets" / "available resources" |

## Agent Prompt Template
```
You are an LLM-DETECTION SPECIALIST. Read the file at [PATH] and scan
EVERY sentence for indicators that the text was written by an LLM.
Check all phrases in Categories 1-5, all structural patterns, and all
tone indicators listed in the protocol. For EACH issue found, report:
the exact phrase, the line number, the category, and a suggested fix.
Be exhaustive.
```

## Severity Ratings
- **Must fix**: Categories 1, 2, 5 (banned phrases, superlatives, em dashes)
- **Should fix**: Categories 3, 4 (LLM vocabulary, mechanical transitions)
- **Review**: Structural patterns and tone indicators (use judgment)
