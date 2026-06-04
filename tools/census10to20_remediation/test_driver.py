import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from driver import run_entrypoint
from datasets import BASE_ACS


def test_base_acs_manifest_paths_resolve():
    repo = Path(__file__).resolve().parents[2]
    assert BASE_ACS, "manifest is empty"
    for entry in BASE_ACS:
        topic = repo / entry["topic"]
        assert topic.is_dir(), f"missing topic dir: {entry['topic']}"
        for ep in entry["entrypoints"]:
            mod_rel, _, func = ep.partition(":")
            assert (topic / mod_rel).is_file(), f"missing module: {entry['topic']}/{mod_rel}"
            assert func, f"entrypoint missing function: {ep}"


def test_run_entrypoint_calls_module_function_not_main(tmp_path):
    mod = tmp_path / "stub.py"
    mod.write_text(
        "ran = []\n"
        "def run():\n    ran.append('run')\n    return 'ok'\n"
        "if __name__ == '__main__':\n    raise SystemExit('main should not run')\n"
    )
    result = run_entrypoint(mod, "run")
    assert result == "ok"


def test_dry_run_reports_before_acceptance_on_age():
    from driver import regenerate_dataset
    from datasets import BASE_ACS
    repo = Path(__file__).resolve().parents[2]
    age = next(e for e in BASE_ACS if e["topic"] == "demographics/Age")
    report = regenerate_dataset(age, repo_root=repo, dry_run=True)
    assert report["dry_run"] is True
    assert report["regenerated"] is False
    assert report["committed"] is False
    # The committed Age data is still corrupt -> BEFORE acceptance fails (inflation).
    assert report["before"]["conservation"]["status"] == "fail"
    assert report["before"]["conservation"]["max_ratio"] > 1.1


def test_acceptance_combines_conservation_and_ratio(tmp_path):
    import json, pandas as pd
    from driver import _acceptance

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    dist.mkdir(parents=True)
    rows = pd.DataFrame({
        "geoid": ["51001000001", "51001000002", "51001000003", "51001000002", "51001000002"],
        "year": [2018, 2018, 2018, 2018, 2018],
        "measure": ["tot_count_geo10", "tot_count_geo20", "tot_count_geo20",
                    "sub_count_geo20", "sub_pct_geo20"],
        "value": [1000, 600, 400, 30, 18.0],  # tot conserved (1.0); sub_pct diluted (18 vs 100*30/?)
        "moe": [pd.NA] * 5,
        "region_type": ["tract"] * 5,
    })
    rows.to_csv(dist / "d.csv.xz", index=False)
    mi = {
        "tot_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "sub_count_geo20": {"geo_standardize": {"measure_type": "count"}},
        "sub_pct_geo20": {"geo_standardize": {"measure_type": "ratio",
            "numerator": "sub_count", "denominator": "tot_count", "scale": 100}},
    }
    (dist / "measure_info.json").write_text(json.dumps(mi))
    entry = {"topic": "demo", "dist_glob": "data/distribution/d.csv.xz",
             "measure_info": "data/distribution/measure_info.json"}
    rep = _acceptance(entry, tmp_path)
    assert rep["ratio"]["status"] == "fail"   # 18.0 != 100*30/tot_count for that geoid
    assert rep["status"] == "fail"


def test_dist_files_returns_all_matches_and_acceptance_aggregates(tmp_path):
    import pandas as pd
    from driver import _dist_files, _acceptance_conservation

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    dist.mkdir(parents=True)
    def w(name, g20a, g20b):
        pd.DataFrame({
            "geoid": ["51001000001", "51001000002", "51001000003"],
            "year": [2018, 2018, 2018],
            "measure": ["pop_count_geo10", "pop_count_geo20", "pop_count_geo20"],
            "value": [1000, g20a, g20b],
            "moe": [pd.NA, pd.NA, pd.NA],
            "region_type": ["tract", "tract", "tract"],
        }).to_csv(dist / name, index=False)
    w("a.csv.xz", 600, 400)   # sum 1000 -> 1.0
    w("b.csv.xz", 900, 600)   # sum 1500 -> 1.5
    entry = {"topic": "demo", "dist_glob": "data/distribution/*.csv.xz"}
    files = _dist_files(entry, tmp_path)
    assert len(files) == 2
    rep = _acceptance_conservation(entry, tmp_path)
    assert rep["status"] == "fail"
    assert rep["max_ratio"] == pytest.approx(1.5)
