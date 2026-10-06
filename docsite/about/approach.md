# Our approach

Two things shape every dataset in the commons: a community process that
decides what is worth measuring, and a standard pipeline that turns raw
sources into data people can use. This page covers both.

## Community Learning through Data-Driven Discovery

<figure class="sdc-float sdc-float--right sdc-float--wide" markdown="0">
--8<-- "docsite/assets/cld3-wheel.svg"
<figcaption>The CLD3 process. Outer wheel: continuous interaction across stakeholders. Middle wheel: the data-driven learning cycle. Centre: the data science framework.</figcaption>
</figure>

The commons is built using the Community Learning through Data-Driven
Discovery (CLD3) framework developed by the Social and Decision Analytics
Division. The key innovation in CLD3 is, as its name suggests, community-based
research: the community participates in asking and answering the questions
that drive information gathering and provide insights relevant to program or
policy decisions. The process liberates, integrates, and makes data available
to local stakeholders, including government, Cooperative Extension
professionals, researchers, and citizens, enabling them to bring local data
insights to their most pressing challenges.

CLD3 goes beyond the organizing aspects of traditional collective action
programs and helps communities build capacity for data-informed decision
making. It is drawn as a set of nested wheels:

<ul class="sdc-swatch-list" markdown="0">
  <li><i style="--swatch:var(--sdc-wheel-outer)"></i><b>Outer wheel:</b> continuous interaction and communication across stakeholders.</li>
  <li><i style="--swatch:#2fa48e"></i><b>Middle wheel:</b> the data-driven learning process: discover, integrate, act, measure and evaluate, redirect.</li>
  <li><i style="--swatch:#7fd1b9"></i><b>Frontier between the wheels:</b> active collaboration between all partners.</li>
  <li><i class="sdc-swatch--hollow"></i><b>Inner circle:</b> a rigorous research framework to guide the data science.</li>
</ul>

Our initial grounding in specific local issues was developed in partnership
with community stakeholders in Arlington and Fairfax Counties, Virginia. The
first issues were equity of access to broadband, equity and stability of
access to staple foods, and transforming racial equity data into meaningful
geographies. Each became a [data story](../stories/index.md).

### Data science framework

<figure class="sdc-float sdc-float--left" markdown="0">
<img src="../img/data-science-framework.png" alt="The data science framework: problem identification, data discovery, data ingestion and governance, data wrangling, fitness-for-use, and statistical modeling and analyses, with communication and dissemination and ethics review alongside every step" width="690" height="410" loading="lazy">
<figcaption>The Data Science Framework, as drawn by the Social and Decision Analytics Division.</figcaption>
</figure>

At the heart of CLD3 is a data science framework that gives a comprehensive,
rigorous, and disciplined approach to problem solving. It covers identifying
data sources, preparing them for use, and assessing the value of those
sources for the intended use. The framework is described in a linear
fashion, but in practice it loops: a finding in one step routinely sends the
work back to an earlier one.

Further reading:

- Keller, S. A., Shipp, S. S., Schroeder, A. D., & Korkmaz, G. (2020).
  Doing Data Science: A Framework and Case Study. *Harvard Data Science
  Review*, 2(1).
- Keller, S., Nusser, S., Shipp, S., & Woteki, C. (2018). Helping Communities
  Use Data to Make Better Decisions. *Issues in Science and Technology*,
  Spring, 83–89.
- Keller, S., Shipp, S., Korkmaz, G., Molfino, E., Goldstein, J., Lancaster,
  V., Pires, B., Higdon, D., Chen, D., & Schroeder, A. (2018). Harnessing the
  power of data to support community-based research. *WIREs Computational
  Statistics*. doi:10.1002/wics.1426
- Keller, S. A., Lancaster, V., & Shipp, S. (2017). Building Capacity for
  Data Driven Governance: Creating a New Foundation for Democracy.
  *Statistics and Public Policy*, 4, 1–11.

## How datasets are built

Once a question has been grounded with stakeholders and the data discovery is
done, each measure becomes a pipeline in the
[Social-Data-Commons repository](https://github.com/dads2busy/Social-Data-Commons).
Every pipeline follows the same six steps and produces the same shape of
output, which is what lets a dashboard, an analyst, or another pipeline use
any dataset without special handling.

<ol class="sdc-steps" markdown="0">
  <li style="--swatch:#cff0e5">
    <h3>Declare the source</h3>
    <p>Each topic has a <code>pipeline.yaml</code> that records where the data come from, which variables are pulled, which years, and which coverage area. Sources include the Census Bureau's American Community Survey, CDC WONDER and PLACES, the Centers for Medicare &amp; Medicaid Services, the National Plan and Provider Enumeration System, the Virginia Department of Health, the Environmental Protection Agency, the U.S. Department of Agriculture, Ookla open speed-test data, and others. Nothing about a source is hardcoded in the pipeline code.</p>
  </li>
  <li style="--swatch:#7fd1b9">
    <h3>Ingest into one schema</h3>
    <p>An ingest step fetches the source and transforms it into a long-format table with one row per geographic unit, year, and measure. Output files are compressed CSVs whose names encode coverage, geographic levels, source, years, and topic, so a file is self-describing before it is opened: <code>va_hdcttrbg_census_acs_2017_2024_household_broadband.csv.xz</code> covers Virginia at health district, county, tract, and block group levels, from the ACS, for 2017 through 2024.</p>
  </li>
  <li style="--swatch:#2fa48e">
    <h3>Standardize geographies</h3>
    <p>Census boundaries changed between the 2010 and 2020 censuses, which makes naive time series across that break misleading. Every dataset is placed on 2020 boundaries. Values collected on 2010 boundaries are redistributed with <a href="../../packages/sdc-census10to20/">sdc-census10to20</a>, and measures carry a <code>_geo20</code> suffix, with a <code>_geo10</code> variant preserved for comparison. <a href="../../packages/sdc-redistribute/">sdc-redistribute</a> moves estimates into local shapes such as civic associations and planning districts; <a href="../../packages/sdc-catchment/">sdc-catchment</a> turns facility locations and drive times into population-aware access scores.</p>
  </li>
  <li style="--swatch:#1f6f8b">
    <h3>Prepare for the dashboards</h3>
    <p>A prepare step aggregates block-group and tract values up to county and health district, then reshapes the result into one wide file per geographic level for each dashboard. The two dashboards share one data format, so a measure added for Virginia is available in the same shape for the National Capital Region.</p>
  </li>
  <li style="--swatch:#1d4f7a">
    <h3>Describe every measure</h3>
    <p>Each pipeline ships a <code>measure_info.json</code> with, for every measure, a short and long description, the source and its citation, units, and provenance. This is what the dashboards show in their information panels, and it is what makes a dataset assessable before it is downloaded.</p>
  </li>
  <li style="--swatch:#14233a">
    <h3>Validate and version</h3>
    <p>New or converted pipelines are compared against reference output and the comparison is written up in a validation report in the repository. Datasets are versioned semantically, and releases are archived to Zenodo so that any version can be cited with a DOI.</p>
  </li>
</ol>

### The schema every file shares

| Column | Meaning |
| --- | --- |
| `geoid` | Census FIPS code of the geography (block group, tract, county, or health district) |
| `year` | The year the value describes |
| `measure` | The measure name |
| `value` | The estimate |
| `moe` | Margin of error, when the source publishes one |
| `data_method` | How the value was produced: `observed`, `modeled`, `simulated`, `scaled`, `interpolated`, or `extrapolated` |

### What is covered

<div class="sdc-domains" markdown="0">
  <div style="--swatch:#7fd1b9"><b>Broadband</b> household adoption, Ookla download and upload speeds, price as a share of income</div>
  <div style="--swatch:#2fa48e"><b>Business climate</b> business counts, entry and exit, minority ownership, by industry</div>
  <div style="--swatch:#1f6f8b"><b>Demographics</b> population, age, gender, race and ethnicity, language, veterans, geographic mobility, segregation</div>
  <div style="--swatch:#1d4f7a"><b>Education</b> reading proficiency, years of schooling, postsecondary attainment, school funding, child care cost and access</div>
  <div style="--swatch:#7fd1b9"><b>Environment</b> environmental hazard index</div>
  <div style="--swatch:#2fa48e"><b>Financial well-being</b> household and personal income, poverty, employment, employment access, income inequality, ALICE, material deprivation</div>
  <div style="--swatch:#1f6f8b"><b>Food</b> food access, food cost, food and nutrition assistance, food security</div>
  <div style="--swatch:#1d4f7a"><b>Health</b> Health Opportunity Index, access to care, health care services and cost, prenatal care adequacy, reproductive and women's health, mental health, substance use, insurance, social vulnerability</div>
  <div style="--swatch:#7fd1b9"><b>Housing</b> housing cost, cost-burdened households, evictions</div>
  <div style="--swatch:#2fa48e"><b>Public safety</b> incarceration</div>
  <div style="--swatch:#1f6f8b"><b>Transportation</b> transportation cost, walkability, safety, commuting characteristics</div>
</div>

The full list of measures, with the geographies and years each one covers, is
on the [data inventory](../inventory/index.md).
