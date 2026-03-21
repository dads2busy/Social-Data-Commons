# Final Pre-Submission Review: Checklist

## Purpose
Run this checklist after the complete article is assembled, compiled, and before uploading to the submission system. Dispatch as a **separate agent** with the compiled .tex file.

## Format Requirements
- [ ] Uses CUP-JNL-DAP document class
- [ ] `\articletype{DATA PAPER}`
- [ ] Title present and reasonable length
- [ ] Abstract present and ≤ 250 words
- [ ] Policy Significance Statement present and ≤ 120 words
- [ ] Keywords present
- [ ] All required sections present: Introduction, Methods, Data Records, Technical Validation, Usage Notes
- [ ] Backmatter complete: Acknowledgments, Funding, Competing Interests, Data Availability, Ethical Standards, Author Contributions
- [ ] ≤ 8 figures
- [ ] ≤ 10 tables
- [ ] All figure/table references resolve (no "??")
- [ ] All `\cite` keys resolve to `\bibitem` entries
- [ ] No orphaned `\bibitem` entries (every reference cited at least once)
- [ ] References in alphabetical order
- [ ] LaTeX compiles without errors

## Content Requirements
- [ ] No results, discussion, analysis, or conclusions anywhere
- [ ] No subjective claims about novelty, impact, or importance
- [ ] Every factual claim has a citation
- [ ] All measures defined with units
- [ ] All parameter values stated
- [ ] All software versions stated
- [ ] At least one independent validation against external data
- [ ] Known limitations listed
- [ ] Data DOI and code URL both present

## Internal Consistency
- [ ] Numbers match between text and tables
- [ ] Geographic unit counts consistent across sections
- [ ] Measure names consistent across sections
- [ ] Year ranges consistent
- [ ] Facility/record counts consistent

## Style
- [ ] Zero em dashes in narrative prose
- [ ] Zero LLM-typical phrases (run 09-llm-language-check protocol)
- [ ] Zero banned words from the avoid list
- [ ] All citations verified by independent agent

## Submission Metadata
Prepare the following for the web form:
- [ ] Title
- [ ] Abstract (plain text, ≤ 250 words)
- [ ] Keywords (comma-delimited, 5-8)
- [ ] Cover letter (plain text)
- [ ] Competing interests declaration
- [ ] Number of figures
- [ ] Number of tables
- [ ] 2+ recommended reviewers with name, institution, email
- [ ] AI use declaration (if applicable)
- [ ] Social media text (≤ 280 characters)

## Agent Prompt Template
```
You are a FINAL REVIEW AGENT conducting a pre-submission review of a
Data & Policy data paper. Read the complete LaTeX source at [PATH] and
check EVERY item in the checklist. For each issue found, rate it as
BLOCKING (would cause rejection), MINOR (flagged in review but fixable),
or COSMETIC (worth fixing but unlikely to affect acceptance). Be thorough.
```
