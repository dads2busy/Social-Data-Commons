"""A throwaway repo root: sync.yaml marker, meta/, and three pipelines."""

from pathlib import Path

import pytest


def add_pipeline(root: Path, rel: str, sources_yaml: str) -> Path:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "pipeline.yaml").write_text(f"name: {d.name.lower()}\nsources:\n{sources_yaml}")
    return d


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "sync.yaml").write_text("dashboards: {}\n")
    (tmp_path / "meta").mkdir()
    add_pipeline(tmp_path, "demographics/Age", "  va:\n    type: census_acs\n    years: [2022, 2023]\n")
    add_pipeline(
        tmp_path,
        "demographics/Geographic Mobility (HOI)",
        "  va:\n    type: census_acs\n    years: [2023, 2024]\n"
        "  chr:\n    type: county_health_rankings\n    urls:\n"
        "      2024: https://chr.example/2024.xlsx\n      2025: https://chr.example/2025.xlsx\n",
    )
    add_pipeline(tmp_path, "energy/Thing", "  va:\n    type: computed\n")
    # a hidden dir and a worktree must never be discovered as pipelines
    add_pipeline(tmp_path, ".claude/worktrees/x/demographics/Age", "  va:\n    type: census_acs\n")
    add_pipeline(tmp_path, "worktree-feature/demographics/Age", "  va:\n    type: census_acs\n")
    return tmp_path
