# Article template & authoring guide

Standard structure for package documentation articles
(`docsite/packages/<pkg>/articles/<name>.md`). Python is the canonical version;
examples mirror the R-vignette scenarios as closely as the Python API allows.

## Rules

- Every code block must be **run and verified**; paste the real captured output.
- Use small inline/synthetic data — articles must be self-contained (no shipped
  or downloaded data files). Redistribute examples generate tiny GeoJSON at
  runtime via shapely.
- Read the actual function signature before writing an example; do not assume
  parameter names from the R package.

## Skeleton

````markdown
# <Article Title>

<One paragraph: what this shows and why it matters.>

## Setup

```bash
pip install <pkg>
```

```python
import ...
```

## <Worked example heading>

```python
# runnable example
```

```text
# real captured output
```

<short explanation of the result>

## See also

- [<Reference page>](../reference/<page>.md)
- [<Sibling article>](<name>.md)
````

## Article types

- **Introduction** — the core workflow, one end-to-end runnable example.
- **Method comparison** — run alternative methods on the same input; show results
  side by side; add a "when to use which".
- **Case study** — a realistic (synthetic) scenario, the computation, and an
  interpretation.

## README standard (PyPI long_description)

Each package README mirrors the Introduction: a tight "what & why", a single
runnable Quickstart (the smallest Introduction example), and a **Documentation**
section linking to the articles + reference on the umbrella site.
