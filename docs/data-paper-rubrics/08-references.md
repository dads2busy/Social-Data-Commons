# References: Rubric and Instructions

## Purpose
Manage citations across the entire paper. Ensure all references are real, correctly formatted, and verified by an independent agent.

## Allowed Source Types
- Peer-reviewed journal articles
- Academic books or book chapters (with ISBN or DOI)
- Official government reports or data documentation
- Recognized preprints (only if no peer-reviewed version exists)

## Prohibited Source Types
- Blog posts, news articles, opinion pieces
- Wikipedia
- Marketing materials, advocacy white papers (unless government-commissioned)
- URLs without institutional backing

## CUP Data & Policy Reference Format (natbib author-year)

### In-text citations
- Parenthetical: `\citep{key}` renders as (Author, Year)
- Author-prominent: `\citet{key}` renders as Author (Year)
- Multiple: `\citep{key1,key2}` renders as (Author1, Year; Author2, Year)

### Bibliography entries
```latex
\bibitem[Author(s), Year]{key}
\textbf{Author1 AB, Author2 CD and Author3 EF} (Year) Title. \textit{Journal} \textit{Volume}(Issue), Pages.
```

Rules:
- Author names: bold, initials without periods, "and" before last author (no ampersand)
- Year in parentheses after author block
- Journal name in italics (full name, not abbreviated)
- Volume in italics, issue in parentheses
- No DOIs in the bibliography (CUP style)
- Government reports: `\textbf{Agency Name} (Year) Title.`
- URLs: `Available at \url{...}`
- Books: `\textbf{Author} (Year) \textit{Title}. Publisher.`

### Alphabetical ordering
References must be in **alphabetical order** by first author surname (CUP requirement). Not in order of first citation.

## Verification Protocol
Every citation must be verified by a **separate agent** before inclusion. The verification agent must:
1. Search for the paper by DOI or title + first author
2. Confirm it exists
3. Confirm author list matches
4. Confirm year matches
5. Confirm journal/publisher matches
6. Confirm volume/pages match (if applicable)
7. Flag any citation that cannot be verified

If a citation cannot be verified, it must be removed and the affected sentence rewritten.

## Deduplication
When combining references from multiple sections, deduplicate by citation key. Each reference appears once in the bibliography. Assign consistent keys across sections before merging.

## Quality Checklist
- [ ] All in-text citations resolve to bibliography entries
- [ ] No bibliography entries without in-text citations
- [ ] No news articles, blogs, or Wikipedia
- [ ] All entries verified by independent agent
- [ ] Alphabetical order by first author surname
- [ ] CUP author-year format throughout
- [ ] Full journal names (not abbreviated)
