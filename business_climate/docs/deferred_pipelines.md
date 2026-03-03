# Business Climate — Deferred Pipeline Report

**Date:** 2026-03-03
**Updated:** 2026-03-03

## Overview

No business_climate pipelines are currently deferred. All 10 pipelines
(2 standalone + 8 Mergent Intellect) have been converted to Python.

## Previously deferred (now converted)

The 8 Mergent Intellect sub-pipelines were initially deferred because the
data source has no API. However, the upstream feature files already exist in
`Microdata/Mergent_intellect/data/working/` and the downstream aggregation
logic was fully automatable. These were converted on 2026-03-03:

- Business_characteristics: Total, Minority_owned, Industry, Industry_Minority_owned
- Employment: Total, Minority_owned, Industry, Industry_Minority_owned

See `Microdata/Mergent_intellect/docs/validation_report.md` for full
validation results (all files match old R output within floating-point
precision).
