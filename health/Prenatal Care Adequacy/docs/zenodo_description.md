## Overview
Adequacy of prenatal care utilization using the Kotelchuck Index (APNCU). Classifies births into four categories (inadequate, intermediate, adequate, adequate plus) based on when prenatal care began and the ratio of actual to expected prenatal visits given gestational age.
2014-2020: Exact computation from NCHS Natality microdata (individual birth records, all VA counties, no suppression). 2021-2024: Projected from 2020 baseline using year-over-year changes in % 1st trimester care from CDC WONDER Natality Expanded (D149) County × Trimester queries. This dataset is produced by the **Social Data Commons** at the University of Virginia as part of the **Prenatal Care Adequacy** data pipeline.

## Provenance
Prenatal care adequacy is measured using the Adequacy of Prenatal Care Utilization (APNCU) index, also known as the Kotelchuck Index (Kotelchuck, M., 1994). Birth records are queried from CDC WONDER Natality Expanded (D149) by county, month, and number of prenatal visits. The index classifies each birth into four categories based on the month prenatal care began and the ratio of observed to expected visits (expected visits defined by ACOG guidelines). This pipeline assumes 39-week gestational age when computing expected visits, as WONDER does not report gestational age in cross-tabulations.

Prenatal care adequacy is measured using the Adequacy of Prenatal Care Utilization (APNCU) index, also known as the Kotelchuck Index (Kotelchuck, M., 1994). Birth records are queried from CDC WONDER Natality Expanded (D149) by county, month, and number of prenatal visits. The index classifies each birth into four categories based on the month prenatal care began and the ratio of observed to expected visits. This pipeline assumes 39-week gestational age when computing expected visits.

Prenatal care adequacy counts from CDC WONDER Natality Expanded (D149) classified using the Kotelchuck Index (Kotelchuck, M., 1994). This pipeline assumes 39-week gestational age when computing expected visits.

## Coverage
- **Temporal coverage:** 2014–2024 (annual)
- **Geographic levels:** County
- **Coverage areas:** National Capital Region (DC metro), Virginia (statewide)

## Methodology
Proportion of births where the mother received more than the recommended number of prenatal visits, beginning in the first four months of pregnancy (110% or more of expected visits). High adequate-plus rates may reflect intensive monitoring of high-risk pregnancies or provider practice patterns. The Kotelchuck Index classifies prenatal care utilization into four tiers based on timing of first visit and proportion of recommended visits received.

Proportion of births where the mother received adequate prenatal care — starting in the first four months and completing 80-109% of recommended visits. This is the target level of prenatal care utilization. Counties with high adequate rates have maternal health systems that successfully engage pregnant women early and maintain recommended visit schedules through delivery.

Proportion of births where the mother began prenatal care in the first four months but completed only 50-79% of recommended visits. Intermediate utilization often reflects barriers that prevent women from maintaining their visit schedule — transportation difficulties, work constraints, or gaps in insurance coverage — even when they initiate care early.

Proportion of births where the mother received inadequate prenatal care — either starting after the fourth month of pregnancy, receiving fewer than 50% of recommended visits, or having no prenatal care at all. High inadequate rates signal systemic barriers to maternal health services such as provider shortages, lack of insurance, or geographic isolation. Inadequate prenatal care is associated with higher rates of preterm birth, low birth weight, and maternal complications.

Count of births where the mother received more than the recommended number of prenatal visits (110%+ of expected), beginning in the first four months of pregnancy. High adequate-plus counts may reflect intensive monitoring of high-risk pregnancies or provider practice patterns that schedule more visits than guidelines recommend. This count helps size the volume of births in each care utilization category.

Count of births where the mother received adequate prenatal care — starting in the first four months and completing 80-109% of recommended visits. This is the target level of care utilization, and the count provides the raw number of births meeting this standard within each county and year.

Count of births where the mother began prenatal care in the first four months but completed only 50-79% of recommended visits. Intermediate counts identify births where care initiation was timely but follow-through was incomplete, often reflecting barriers like transportation, work constraints, or insurance gaps.

Count of births where the mother received inadequate prenatal care — either starting after the fourth month, receiving fewer than 50% of recommended visits, or having no prenatal care at all. High counts of inadequate care signal systemic barriers to maternal health services and help quantify the population needing targeted outreach.

## Source Tables
- [CDC WONDER Natality Expanded (D149)](https://wonder.cdc.gov/natality-expanded-current.html)

## Measures (8)
- **adequateplus_pc**: Adequacy of Prenatal Care Utilization: Adequate Plus (mean, unit: percent)
  Proportion of births with prenatal care exceeding 110% of recommended visits, starting by the 4th month.
- **adequate_pc**: Adequacy of Prenatal Care Utilization: Adequate (mean, unit: percent)
  Proportion of births with 80-109% of recommended prenatal visits, starting by the 4th month.
- **intermediate_pc**: Adequacy of Prenatal Care Utilization: Intermediate (mean, unit: percent)
  Proportion of births with 50-79% of recommended prenatal visits, starting by the 4th month.
- **inadequate_pc**: Adequacy of Prenatal Care Utilization: Inadequate (mean, unit: percent)
  Proportion of births with late or no prenatal care, or fewer than 50% of recommended visits.
- **adequateplus**: Prenatal Care Count: Adequate Plus (sum, unit: births)
  Count of births rated adequate-plus on the Kotelchuck Index.
- **adequate**: Prenatal Care Count: Adequate (sum, unit: births)
  Count of births rated adequate on the Kotelchuck Index.
- **intermediate**: Prenatal Care Count: Intermediate (sum, unit: births)
  Count of births rated intermediate on the Kotelchuck Index.
- **inadequate**: Prenatal Care Count: Inadequate (sum, unit: births)
  Count of births rated inadequate on the Kotelchuck Index.

## Data Sources
- [Centers for Disease Control and Prevention (accessed 2026)](https://www.cdc.gov)

## File Format
Data files are provided as CSVs (`.csv`) with the following columns: `geoid`, `region_type`, `region_name`, `year`, `measure`, `value`, `moe` (margin of error, where available). Larger files are provided as xz-compressed CSVs (`.csv.xz`).
