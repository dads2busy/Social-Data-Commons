# SDC PyPI Publish Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sdc-census10to20` publishable to PyPI via a tag-driven, hatch-vcs-versioned, OIDC Trusted Publishing GitHub Actions workflow, and cut `v0.1.0`.

**Architecture:** The package's version becomes dynamic (derived from the git tag by `hatch-vcs`, filtered to `census10to20-v*` tags). A single-job workflow `publish-census10to20.yml` builds and publishes to PyPI on a matching tag push. Stale `uva-bi-sdad` PyPI metadata is corrected. `sdc-core` is untouched (never published).

**Tech Stack:** hatchling + hatch-vcs, `python -m build`, `pypa/gh-action-pypi-publish`, GitHub Actions OIDC, uv (local verification).

**Spec:** `docs/specs/2026-06-03-pypi-publish-flow-design.md`

**Branch:** `feat/pypi-publish-flow` (already created).

**Verification note:** Run all commands from the repo root
`/Users/ads7fg/git/social-data-commons`. There is no unit-test surface here; the
gates are a real `build` producing a tag-derived version, an installed-wheel
`__version__` check, and YAML validity. hatch-vcs reads git tags, so local
verification creates a **temporary** `census10to20-v0.1.0` tag and deletes it —
the real release tag is pushed later (Task 3 handoff), after merge + Trusted
Publishing setup.

---

## File Structure

**Modify:**
- `packages/sdc-census10to20/pyproject.toml` — dynamic version + hatch-vcs config + corrected `[project.urls]`
- `packages/sdc-census10to20/src/sdc_census10to20/__init__.py` — `__version__` from installed metadata

**Rename + rewrite:**
- `.github/workflows/publish.yml` → `.github/workflows/publish-census10to20.yml` (3 jobs → 1, `fetch-depth: 0`)

**Untouched:** `sdc-core`, all other packages, `docs.yml`.

---

## Task 1: Tag-derived versioning for sdc-census10to20

**Files:**
- Modify: `packages/sdc-census10to20/pyproject.toml`
- Modify: `packages/sdc-census10to20/src/sdc_census10to20/__init__.py`

- [ ] **Step 1: Make the version dynamic in `[project]`**

In `packages/sdc-census10to20/pyproject.toml`, replace the static version line (line 3) with a `dynamic` declaration. Change:

```toml
name = "sdc-census10to20"
version = "0.1.0"
description = "Redistribute 2010-2019 census data onto 2020 census boundaries"
```

to:

```toml
name = "sdc-census10to20"
dynamic = ["version"]
description = "Redistribute 2010-2019 census data onto 2020 census boundaries"
```

- [ ] **Step 2: Correct the stale `[project.urls]`**

Replace the entire `[project.urls]` block (currently pointing at `uva-bi-sdad`):

```toml
[project.urls]
Homepage = "https://uva-bi-sdad.github.io/sdc-census10to20/"
Documentation = "https://uva-bi-sdad.github.io/sdc-census10to20/"
Repository = "https://github.com/uva-bi-sdad/sdc-census10to20"
Issues = "https://github.com/uva-bi-sdad/sdc-census10to20/issues"
Changelog = "https://github.com/uva-bi-sdad/sdc-census10to20/blob/main/CHANGELOG.md"
```

with:

```toml
[project.urls]
Homepage = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/"
Documentation = "https://dads2busy.github.io/Social-Data-Commons/packages/sdc-census10to20/"
Repository = "https://github.com/dads2busy/Social-Data-Commons"
Issues = "https://github.com/dads2busy/Social-Data-Commons/issues"
Changelog = "https://github.com/dads2busy/Social-Data-Commons/blob/main/packages/sdc-census10to20/CHANGELOG.md"
```

- [ ] **Step 3: Add hatch-vcs to the build system and configure the version source**

Replace the build-system block (currently):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sdc_census10to20"]
```

with (adds `hatch-vcs` + version config, keeps the wheel-packages line):

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"
tag-pattern = "census10to20-v(?P<version>.+)"

[tool.hatch.version.raw-options]
git_describe_command = ["git", "describe", "--dirty", "--tags", "--long", "--match", "census10to20-v*"]

[tool.hatch.build.targets.wheel]
packages = ["src/sdc_census10to20"]
```

- [ ] **Step 4: Derive `__version__` from installed metadata**

In `packages/sdc-census10to20/src/sdc_census10to20/__init__.py`, replace:

```python
__version__ = "0.1.0"
```

with:

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sdc-census10to20")
except PackageNotFoundError:  # running from a raw checkout, not installed
    __version__ = "0.0.0"
```

- [ ] **Step 5: Commit the version changes (clean tree before tagging)**

```bash
git add packages/sdc-census10to20/pyproject.toml packages/sdc-census10to20/src/sdc_census10to20/__init__.py
git commit -m "feat(census10to20): tag-derived versioning via hatch-vcs + fix PyPI urls"
```

- [ ] **Step 6: Create a temporary tag and build, verifying the version comes from the tag**

```bash
git tag census10to20-v0.1.0
rm -rf /tmp/c1020-verify
uv build --package sdc-census10to20 --out-dir /tmp/c1020-verify
ls /tmp/c1020-verify
```

Expected: exactly `sdc_census10to20-0.1.0.tar.gz` and `sdc_census10to20-0.1.0-py3-none-any.whl`. The `0.1.0` proves hatch-vcs read the tag (not a hardcoded value). If you instead see something like `0.1.0.post0.dev0+...` or `0.0.1.dev...`, the tree was dirty or the tag/match is wrong — fix before continuing.

- [ ] **Step 7: Verify the installed wheel reports the right `__version__`**

```bash
uv run --no-project --with /tmp/c1020-verify/sdc_census10to20-0.1.0-py3-none-any.whl \
  python -c "import sdc_census10to20; print(sdc_census10to20.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 8: Delete the temporary tag**

The real release tag is pushed in Task 3 (after merge + Trusted Publishing setup), so it lands on the right commit. Remove the local test tag now:

```bash
git tag -d census10to20-v0.1.0
rm -rf /tmp/c1020-verify
```

Expected: `Deleted tag 'census10to20-v0.1.0'`. (No commit in this step — the temp tag was never committed content.)

---

## Task 2: Single-job publish workflow

**Files:**
- Rename: `.github/workflows/publish.yml` → `.github/workflows/publish-census10to20.yml`

- [ ] **Step 1: Rename the workflow file**

```bash
git mv .github/workflows/publish.yml .github/workflows/publish-census10to20.yml
```

- [ ] **Step 2: Replace its contents with the single-job PyPI-only workflow**

Overwrite `.github/workflows/publish-census10to20.yml` with exactly:

```yaml
name: Publish sdc-census10to20 to PyPI

on:
  push:
    tags:
      - "census10to20-v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/sdc-census10to20
    permissions:
      id-token: write          # OIDC Trusted Publishing — no API tokens
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0        # hatch-vcs needs full tag history
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Build wheel and sdist
        working-directory: packages/sdc-census10to20
        run: |
          python -m pip install --upgrade build
          python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: packages/sdc-census10to20/dist/
```

- [ ] **Step 3: Validate the workflow YAML parses**

```bash
uv run --group docs python -c "import yaml; yaml.safe_load(open('.github/workflows/publish-census10to20.yml')); print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Confirm the old filename is gone and only the new one remains**

```bash
ls .github/workflows/
```

Expected: `docs.yml` and `publish-census10to20.yml` only (no `publish.yml`).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/
git commit -m "ci(publish): single-job PyPI-only workflow, renamed per-package"
```

---

## Task 3: Final verification + release handoff

**Files:** none (verification + user handoff)

- [ ] **Step 1: Final clean build from a temp tag**

```bash
git tag census10to20-v0.1.0
rm -rf /tmp/c1020-final
uv build --package sdc-census10to20 --out-dir /tmp/c1020-final && ls /tmp/c1020-final
git tag -d census10to20-v0.1.0
rm -rf /tmp/c1020-final
```

Expected: `0.1.0` sdist + wheel build cleanly; temp tag deleted.

- [ ] **Step 2: Confirm metadata in the built wheel is correct**

```bash
git tag census10to20-v0.1.0
uv build --package sdc-census10to20 --out-dir /tmp/c1020-meta >/dev/null 2>&1
uv run --no-project --with twine python -m twine check /tmp/c1020-meta/*
git tag -d census10to20-v0.1.0; rm -rf /tmp/c1020-meta
```

Expected: `Checking ... PASSED` for both sdist and wheel.

- [ ] **Step 3: Finish the development branch**

Use the **superpowers:finishing-a-development-branch** skill to merge `feat/pypi-publish-flow` to `main` and push. The workflow only triggers on a `census10to20-v*` tag, so merging/pushing the branch does NOT publish anything.

- [ ] **Step 4: User completes Trusted Publishing setup (manual, one-time)**

Tell the user to, before the release tag is pushed:

1. Register a **pending publisher** at <https://pypi.org/manage/account/publishing/>:
   - PyPI Project Name: `sdc-census10to20`
   - Owner: `dads2busy`
   - Repository name: `Social-Data-Commons`
   - Workflow name: `publish-census10to20.yml`
   - Environment name: `pypi`
2. Create a GitHub **environment named `pypi`** (repo Settings → Environments).

Do not push the release tag until both are done.

- [ ] **Step 5: Cut the release (after Step 4 confirmed)**

On `main`, after the user confirms Trusted Publishing setup is complete:

```bash
git checkout main && git pull
git tag census10to20-v0.1.0
git push origin census10to20-v0.1.0
```

Then watch the run:

```bash
gh run watch "$(gh run list --workflow=publish-census10to20.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status --interval 15
```

Expected: green run.

- [ ] **Step 6: Verify the package is live on PyPI**

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://pypi.org/pypi/sdc-census10to20/0.1.0/json
```

Expected: `HTTP 200`. Optionally confirm install:

```bash
uv run --no-project --with sdc-census10to20 python -c "import sdc_census10to20 as m; print(m.__version__)"
```

Expected: `0.1.0`

---

## Self-Review

- **Spec coverage:** dynamic version + hatch-vcs config → Task 1 §1,§3. Corrected urls → Task 1 §2. `__version__` from metadata → Task 1 §4. Workflow rename + single job + `fetch-depth: 0` + `pypi` env + OIDC → Task 2. Trusted Publishing manual setup → Task 3 §4. First release `v0.1.0` → Task 3 §5. Success criteria (tag-derived build, twine-valid metadata, green run, live on PyPI, importable) → Tasks 1,3. All covered.
- **Placeholder scan:** none — every step has concrete content or an exact command + expected output. The `"0.0.0"` fallback is intentional.
- **Consistency:** the tag prefix `census10to20-v` is identical across the workflow trigger, `tag-pattern`, `git_describe_command --match`, and every test/release tag command. Package name `sdc-census10to20`, environment `pypi`, and workflow filename `publish-census10to20.yml` match between the workflow, the Trusted Publishing fields, and the run-watch command.
- **Tag hygiene:** every local test tag (Task 1 §6, Task 3 §1–2) is deleted in the same task; only Task 3 §5 creates a tag that is pushed, and only after merge to main + Trusted Publishing setup.
