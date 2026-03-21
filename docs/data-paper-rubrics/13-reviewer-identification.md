# Reviewer Identification: Protocol

## Purpose
Identify 3-4 qualified peer reviewers to suggest during submission. Data & Policy requires a minimum of 2 recommended reviewers with name, institution, and email.

## Selection Criteria

### Must have
- Published in the same domain (e.g., childcare policy, healthcare access, environmental justice)
- No conflict of interest (not at the same institution as any author)
- Email address verifiable from a university or organizational faculty page

### Ideal reviewer profile (at least 2 of these)
- Published on the same methodology (e.g., floating catchment area, gravity model, PCA composite)
- Published on the same policy topic using spatial or quantitative data
- Published in Data & Policy or a similar data/policy journal
- Cited in the paper's reference list (they already know the field)

### Avoid
- Same institution as any author (University of Virginia)
- Co-authors of any author within the last 5 years
- PhD advisors or advisees of any author
- Anyone whose work the paper criticizes

## Search Strategy

### Step 1: Mine the reference list
Start with authors of the most methodologically or topically relevant papers cited in the manuscript. These people are already known to be active in the field.

### Step 2: Search for domain experts
Search queries to run:
- "[methodology name] [domain]" (e.g., "floating catchment area childcare")
- "[domain] spatial accessibility data" (e.g., "healthcare access spatial data")
- "[domain] open data policy" (e.g., "environmental justice open data")
- "[domain] [geographic scope]" if state-specific expertise is relevant

### Step 3: Verify each candidate
For each potential reviewer:
1. Search their university faculty page
2. Confirm current institution and department
3. Find email address (must be from official faculty page, not guessed)
4. Confirm they have published in the relevant domain within the last 5 years
5. Confirm no conflict of interest

## Output Format
For each recommended reviewer, provide:

```
Name: [Full name]
Institution: [Department, University]
Email: [verified email]
Rationale: [1-2 sentences on why they are qualified to review this specific paper]
Conflict check: [Confirm no COI]
```

## Diversity Considerations
- Aim for methodological + domain expertise mix (not all methods people, not all policy people)
- Include at least one reviewer who can assess the policy significance (important for D&P)
- Include at least one reviewer who can assess the technical methodology

## Agent Prompt Template
```
I need to find 3-4 academic researchers who would be appropriate peer
reviewers for a data paper about [TOPIC] using [METHODOLOGY]. The paper
is being submitted to Data & Policy (Cambridge University Press).

The paper cites these relevant authors: [LIST KEY AUTHORS FROM REFERENCES].

Search for each of these authors and 2-3 additional domain experts.
For each, find: full name, current institution and department, verified
email address (from university faculty page), and why they would be a
good reviewer.

Do NOT include anyone at [AUTHOR INSTITUTION]. Only report people whose
email addresses you can verify from official university websites.
```

## Submission Fields
The submission system typically requires:
- Reviewer name
- Institution
- Email address
- Reason for suggestion (optional but recommended)
