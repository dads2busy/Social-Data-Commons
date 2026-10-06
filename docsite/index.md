# Social Data Commons

**Data · Applications · Tools · Methods**

The Social Data Commons provides actionable data for local decision-making by
creating new sub-county datasets and measures from publicly collectible data
sources. It covers Virginia and the National Capital Region, and was built by
the Social and Decision Analytics Division of the Biocomplexity Institute at
the University of Virginia. It was previously known as the Social Impact Data
Commons.

## What is a data commons?

A data commons is an open knowledge repository that co-locates data from a
variety of sources, builds and curates data insights, and provides tools
designed to track issues over time and geography. Ours:

- provides data, indicators, indices, case studies, and training;
- analyzes the impact of social, economic, and health trends and major events;
- enables ongoing learning from data;
- addresses local issues of concern, such as food insecurity, health equity,
  and access to broadband.

<div class="grid cards" markdown>

-   :material-view-dashboard-outline: **Dashboards**

    ---

    Explore every measure on a map, over time, by county, tract, block group,
    or local district. One dashboard for Virginia, one for the National
    Capital Region.

    [:octicons-arrow-right-24: Open the dashboards](dashboards/index.md)

-   :material-book-open-page-variant-outline: **Data stories**

    ---

    How multiple measures are triangulated to answer a real local question:
    broadband, urgent care access, minority business ownership, and food
    insecurity.

    [:octicons-arrow-right-24: Read the stories](stories/index.md)

-   :material-cogs: **How datasets are built**

    ---

    The community process that decides what to measure, and the pipeline that
    turns raw sources into standardized, documented, versioned datasets.

    [:octicons-arrow-right-24: Our approach](about/approach.md)

-   :material-language-python: **Python packages**

    ---

    The open-source tools behind the data: census geography standardization,
    value redistribution, and spatial accessibility.

    [:octicons-arrow-right-24: Packages](#packages)

</div>

## Packages

| Package | What it does | PyPI |
| --- | --- | --- |
| [`sdc-census10to20`](packages/sdc-census10to20/index.md) | Redistribute 2010–2019 census data onto 2020 boundaries. | [pypi.org](https://pypi.org/project/sdc-census10to20/) |
| [`sdc-redistribute`](packages/sdc-redistribute/index.md) | Redistribute values between geographies (area- and parcel-weighted). | [pypi.org](https://pypi.org/project/sdc-redistribute/) |
| [`sdc-catchment`](packages/sdc-catchment/index.md) | Floating catchment area spatial accessibility (2SFCA, E2SFCA, …). | [pypi.org](https://pypi.org/project/sdc-catchment/) |

```bash
# uv (recommended)
uv add sdc-census10to20

# pip
pip install sdc-census10to20
```

## Links

- Source and data: [github.com/dads2busy/Social-Data-Commons](https://github.com/dads2busy/Social-Data-Commons)
- Virginia dashboard: [dads2busy.github.io/virginia_public_health_data](https://dads2busy.github.io/virginia_public_health_data/)
- National Capital Region dashboard: [dads2busy.github.io/national_capital_region_data](https://dads2busy.github.io/national_capital_region_data/)
