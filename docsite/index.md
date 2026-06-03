# Social Data Commons

Python packages powering the [Social Data Commons](https://github.com/dads2busy/Social-Data-Commons)
data pipelines — the Python ports of the SDAD R toolkit for census geography
standardization, spatial accessibility, value redistribution, and shared
pipeline utilities.

## Packages

| Package | What it does | Status |
| --- | --- | --- |
| [`sdc-core`](packages/sdc-core/index.md) | Shared pipeline utilities — Census API, file naming, versioning, Zenodo upload, geography aggregation. | Available |
| [`sdc-census10to20`](packages/sdc-census10to20/index.md) | Redistribute 2010–2019 census data onto 2020 boundaries. | Available |
| `sdc-redistribute` | General value redistribution between geographies (currently `sdc_core.redistribute`). | Coming soon |
| `sdc-catchment` | Floating catchment area spatial accessibility (currently `sdc_core.catchment`). | Coming soon |

## Install

```bash
# uv (recommended)
uv add sdc-census10to20

# pip
pip install sdc-census10to20
```

## Links

- Source: [github.com/dads2busy/Social-Data-Commons](https://github.com/dads2busy/Social-Data-Commons)
