# Overview

The Social Data Commons supports equity-informed decision-making at the local
and regional level. It began as the Social Impact Data Commons, a project of
the Social and Decision Analytics Division of the Biocomplexity Institute at
the University of Virginia, and grew out of two sponsored projects:

1. **Social Impact Data Commons to Inform Equitable Growth**, sponsored by the
   Mastercard Center for Inclusive Growth, covering the National Capital
   Region.
2. **Data Commons to Support Department of Health Strategic Plans**, sponsored
   by the Virginia Department of Health, covering the state of Virginia.

Both projects used the same community process to discover data needs, and both
share one pipeline codebase and one dashboard design.

## Objective

To make impactful, equity-informed decisions at the local and regional level,
decision-makers need data and indicators that:

- **triangulate** on their policy challenges and questions;
- are at a **geographic level** that informs their decision-making;
- come in a **geographic shape** that is useful, such as a planning corridor,
  a school attendance zone, a civic association, or a health district;
- are **validated and timely**.

Most public data stop at the county. Local questions about broadband
affordability, access to care, or food insecurity play out at the
neighborhood level, so most of the work of the commons is producing
sub-county measures and placing them in the geographies that local
stakeholders actually use.

## What a finished dataset must be

Once datasets are discovered, vetted, created, synthesized, and validated,
they must be easy to assess, access, and analyze.

| Requirement | The question it answers | How the commons meets it |
| --- | --- | --- |
| **Assessable** | Are these the right data for the policy question? | Maps, tables, charts, and full metadata for every measure on the dashboards. |
| **Accessible** | Can the data be downloaded? | Direct download from the dashboards; compressed CSV files and metadata committed to the public GitHub repository. |
| **Analyzable** | Can the data be integrated into a user's own analytic system? | One long-format schema, standardized file names, and 2020 census geographies across every dataset. |

Everything is meant to be both machine readable and human readable.

## What the commons provides

- **Two open-source dashboards**, lightweight static web applications that run
  on free hosting such as GitHub Pages. See [Dashboards](../dashboards/index.md).
- **Open data pipelines and data**, covering broadband, business climate,
  demographics, education, environment, financial well-being, food, health,
  housing, public safety, and transportation. The code that ingests raw
  sources and prepares each measure lives alongside the output files in the
  [Social-Data-Commons repository](https://github.com/dads2busy/Social-Data-Commons).
- **Open-source tools** for creating localized datasets, published on PyPI:
  [`sdc-catchment`](../packages/sdc-catchment/index.md) for spatial access and
  availability metrics, [`sdc-redistribute`](../packages/sdc-redistribute/index.md)
  for moving population data into alternate geographies, and
  [`sdc-census10to20`](../packages/sdc-census10to20/index.md) for placing older
  census data on 2020 boundaries.
- **Data stories** that apply the commons to real local issues. See
  [Data stories](../stories/index.md).

## Looking ahead

The commons is designed to be modular, sustainable, and expandable. Ongoing
work extends it into new policy areas and new geographies, creates new
policy-relevant indicators, and keeps existing datasets current as new source
data are released.

## Contact

Aaron Schroeder, Principal Investigator, [ads7fg@virginia.edu](mailto:ads7fg@virginia.edu)
