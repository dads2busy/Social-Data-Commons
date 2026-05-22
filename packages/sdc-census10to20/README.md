# sdc-census10to20

Redistribute 2010-2019 census data onto 2020 census boundaries.

This is the Python port of the R package
[`sdc.census10to20`](https://uva-bi-sdad.github.io/sdc.censes10to20/), used by
the Social Data Commons pipelines to standardize tract- and block-group-level
data across the 2020 decennial census boundary changes.

## Install

```bash
pip install sdc-census10to20
```

## Quick start

```python
import pandas as pd
from sdc_census10to20 import standardize_all

df = pd.DataFrame({
    "geoid": ["51059450100", "51059450200"],
    "year": [2018, 2018],
    "measure": ["population", "population"],
    "value": [3000, 4500],
    "moe": [pd.NA, pd.NA],
})

standardized = standardize_all(df)
```

See the [documentation](https://uva-bi-sdad.github.io/sdc-census10to20/) for the
full API reference and a worked example with Virginia tract-level data.

## Releasing

This package uses
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no API
tokens are stored in GitHub.

One-time setup (done by a maintainer):

1. Register the project name on [TestPyPI](https://test.pypi.org/) and
   [PyPI](https://pypi.org/) with a "pending publisher" pointing at this repo
   and workflow file (`.github/workflows/publish.yml`).
2. Configure two GitHub environments on the repo: `testpypi` and `pypi`.

To cut a release:

1. Bump `version` in `pyproject.toml`, update `CHANGELOG.md`.
2. Commit and tag: `git tag census10to20-v0.1.0 && git push --tags`.
3. The `publish.yml` workflow builds the wheel, uploads to TestPyPI first,
   then PyPI on success.

To publish docs:

The `docs.yml` workflow runs on every push to `main` that touches
`packages/sdc-census10to20/`. No tag required.

## License

MIT
