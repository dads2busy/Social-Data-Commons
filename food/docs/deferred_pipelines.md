# food/ — Deferred Pipelines

Pipelines that were NOT converted from R to Python, with reasons.

| Pipeline | Location | Reason |
|---|---|---|
| Food Insecurity (SDAD/PUMS) | `food/Food Security/Food Insecurity/` | No source code in repo — only output data exists |
| Healthy Food Availability (MRFEI) | `food/Food Accessibility/Healthy Food Availability/` | Spatial operations (OpenStreetMap distance buffers) |
| Food Accessibility (HOI/FARA) | `food/Food Accessibility/` | Spatial adjacency imputation, inconsistent R code |
| Food Items (Gravity Models) | `food/Food Items/` | Retired method (OSRM + web scraping + gravity models) |
| Food Cost | `food/Food Cost/` | No distribution output, incomplete/exploratory code |

## Converted Pipelines

| Pipeline | Type |
|---|---|
| SNAP | ACS B22010 → county/tract/BG + VA health districts |
| Feeding America — Overall Food Insecurity | MMG Excel + tract 2020 → county/tract + VA HD |
| Feeding America — Children's Food Insecurity | Filter of master → county + VA HD |
| Feeding America — Food Secure Average Meal Cost | Filter of master → county + VA HD |
| Feeding America — Food Budget Shortfall | Filter of master → county + VA HD |
