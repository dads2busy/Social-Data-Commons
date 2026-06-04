import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from driver import run_entrypoint
from datasets import BASE_ACS


def test_all_manifest_entries_resolve():
    import glob
    from datasets import ALL_DATASETS
    repo = Path(__file__).resolve().parents[2]
    assert len(ALL_DATASETS) == 24, f"expected 24 datasets, got {len(ALL_DATASETS)}"
    for entry in ALL_DATASETS:
        topic = repo / entry["topic"]
        assert topic.is_dir(), f"missing topic dir: {entry['topic']}"
        for ep in entry["entrypoints"]:
            mod_rel, _, func = ep.partition(":")
            assert (topic / mod_rel).is_file(), f"missing module: {entry['topic']}/{mod_rel}"
        mi = topic / entry["measure_info"]
        assert mi.is_file(), f"missing measure_info: {entry['topic']}/{entry['measure_info']}"
        matches = glob.glob(str(topic / entry["dist_glob"]))
        assert matches, f"dist_glob matches nothing: {entry['topic']} :: {entry['dist_glob']}"


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
    # Dry-run is side-effect-free and reports a structured BEFORE acceptance.
    # (Asserts structure, not specific values: Age's data state changes as the
    # remediation regenerates it; corruption detection is covered by synthetic tests.)
    assert report["dry_run"] is True
    assert report["regenerated"] is False
    assert report["committed"] is False
    assert report["before"]["conservation"]["status"] in {"pass", "fail", "n/a"}
    assert "ratio" in report["before"]


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


def test_real_mode_runs_gates_versions_commits(tmp_path, monkeypatch):
    import json, pandas as pd
    import driver as drv

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    code = topic / "code" / "distribution"
    dist.mkdir(parents=True); code.mkdir(parents=True)
    pd.DataFrame({
        "geoid": ["51001000001", "51001000002", "51001000003"], "year": [2018]*3,
        "measure": ["c_count_geo10", "c_count_geo20", "c_count_geo20"], "value": [1000, 900, 600],
        "moe": [pd.NA]*3, "region_type": ["tract"]*3,
    }).to_csv(dist / "d.csv.xz", index=False)
    (dist / "measure_info.json").write_text(json.dumps(
        {"c_count_geo20": {"geo_standardize": {"measure_type": "count"}}}))
    (code / "ingest.py").write_text(
        "import pandas as pd\nfrom pathlib import Path\n"
        "def run():\n"
        "    p = Path(__file__).resolve().parents[2] / 'data/distribution/d.csv.xz'\n"
        "    pd.DataFrame({'geoid':['51001000001','51001000002','51001000003'],'year':[2018]*3,"
        "'measure':['c_count_geo10','c_count_geo20','c_count_geo20'],'value':[1000,600,400],'moe':[pd.NA]*3,"
        "'region_type':['tract']*3}).to_csv(p, index=False)\n")
    (code / "prepare.py").write_text("def run():\n    pass\n")

    calls = {"version": 0, "tag": 0, "commit": 0}
    monkeypatch.setattr(drv, "update_version",
        lambda *a, **k: (calls.__setitem__("version", calls["version"] + 1),
                         type("R", (), {"tag": "demo/v1.0.1", "new_version": "1.0.1"})())[1])
    monkeypatch.setattr(drv, "_local_tag", lambda *a, **k: calls.__setitem__("tag", calls["tag"] + 1))
    monkeypatch.setattr(drv, "_commit_dataset", lambda *a, **k: calls.__setitem__("commit", calls["commit"] + 1))

    entry = {"topic": "demo", "dist_glob": "data/distribution/d.csv.xz",
             "measure_info": "data/distribution/measure_info.json",
             "entrypoints": ["code/distribution/ingest.py:run", "code/distribution/prepare.py:run"]}
    report = drv.regenerate_dataset(entry, repo_root=tmp_path, dry_run=False)
    assert report["regenerated"] is True
    assert report["after"]["status"] == "pass"
    assert report["before"]["conservation"]["max_ratio"] == pytest.approx(1.5)
    assert report["after"]["conservation"]["max_ratio"] == pytest.approx(1.0)
    # Tags are deferred for the remediation: version bump + commit, NO tag.
    assert calls["version"] == 1
    assert calls["commit"] == 1
    assert calls["tag"] == 0
    assert report["committed"] is True


def test_inflation_reduced_edge_cases():
    from driver import _inflation_reduced
    none_rep = {"conservation": {"max_ratio": None}}
    r2 = {"conservation": {"max_ratio": 2.0}}
    r1 = {"conservation": {"max_ratio": 1.0}}
    assert _inflation_reduced(none_rep, none_rep) is True       # never a count -> pass
    assert _inflation_reduced(r2, r1) is True                   # 2.0 -> 1.0 reduced
    assert _inflation_reduced(r1, r2) is False                  # got worse
    assert _inflation_reduced(r2, none_rep) is False            # count dropped after -> fail (regression)
    assert _inflation_reduced(none_rep, r1) is False            # count appeared after -> fail (suspicious)


def test_real_mode_removes_stale_renamed_outputs(tmp_path, monkeypatch):
    import json, os, pandas as pd
    import driver as drv

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    code = topic / "code" / "distribution"
    dist.mkdir(parents=True); code.mkdir(parents=True)
    # OLD-named, corrupt (inflated 1.5), with an ANCIENT mtime -> stale
    old = dist / "ncr_x_census_acs_2009_2024_demo.csv.xz"
    pd.DataFrame({
        "geoid": ["51001000001", "51001000002", "51001000003"], "year": [2018]*3,
        "measure": ["c_count_geo10", "c_count_geo20", "c_count_geo20"], "value": [1000, 900, 600],
        "moe": [pd.NA]*3, "region_type": ["tract"]*3,
    }).to_csv(old, index=False)
    os.utime(old, (1, 1))  # 1970 -> definitely older than run_start
    (dist / "measure_info.json").write_text(json.dumps(
        {"c_count_geo20": {"geo_standardize": {"measure_type": "count"}}}))
    # ingest writes the NEW-named file (2010_2024), conserved (1.0); does NOT touch the old name
    (code / "ingest.py").write_text(
        "import pandas as pd\nfrom pathlib import Path\n"
        "def run():\n"
        "    p = Path(__file__).resolve().parents[2] / 'data/distribution/ncr_x_census_acs_2010_2024_demo.csv.xz'\n"
        "    pd.DataFrame({'geoid':['51001000001','51001000002','51001000003'],'year':[2018]*3,"
        "'measure':['c_count_geo10','c_count_geo20','c_count_geo20'],'value':[1000,600,400],'moe':[pd.NA]*3,"
        "'region_type':['tract']*3}).to_csv(p, index=False)\n")
    (code / "prepare.py").write_text("def run():\n    pass\n")
    monkeypatch.setattr(drv, "update_version", lambda *a, **k: type("R", (), {"tag": "demo/v1.0.1"})())
    monkeypatch.setattr(drv, "_local_tag", lambda *a, **k: None)
    monkeypatch.setattr(drv, "_commit_dataset", lambda *a, **k: None)

    entry = {"topic": "demo", "dist_glob": "data/distribution/*demo.csv.xz",
             "measure_info": "data/distribution/measure_info.json",
             "entrypoints": ["code/distribution/ingest.py:run", "code/distribution/prepare.py:run"]}
    report = drv.regenerate_dataset(entry, repo_root=tmp_path, dry_run=False)
    # stale old-named file removed; fresh new-named present; gate passed on fresh only
    assert not old.exists()
    assert (dist / "ncr_x_census_acs_2010_2024_demo.csv.xz").exists()
    assert report["after"]["status"] == "pass"
    assert report["after"]["conservation"]["max_ratio"] == pytest.approx(1.0)
    assert report["committed"] is True


def test_commit_dataset_does_not_commit_clobbered_measure_info(tmp_path):
    import subprocess, json
    import driver as drv

    repo = tmp_path
    def git(*a): subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True)
    git("init"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
    # committed shared dashboard measure_info with TWO datasets' entries
    site = repo / "dashboard_data" / "ncr"; site.mkdir(parents=True)
    mi = site / "measure_info.json"
    mi.write_text(json.dumps({"broadband_x": {"a": 1}, "health_y": {"b": 2}}))
    dist = repo / "demo" / "data" / "distribution"; dist.mkdir(parents=True)
    (dist / "ncr_demo.csv.xz").write_text("seed")
    (repo / "demo" / "pipeline.yaml").write_text("version: '1.0.0'\n")
    git("add", "-A"); git("commit", "-m", "seed")

    # simulate a prepare run: clobber measure_info to ONE dataset + write a new data file
    mi.write_text(json.dumps({"age_z": {"c": 3}}))             # clobbered (lost broadband/health)
    (site / "ncr_ct_demo.csv.xz").write_text("new dashboard data")
    (dist / "ncr_demo.csv.xz").write_text("regenerated")

    entry = {"topic": "demo"}
    drv._commit_dataset(entry, repo, "regenerate demo")

    # the committed measure_info must STILL have both original datasets (not clobbered)
    committed_mi = subprocess.run(["git", "show", "HEAD:dashboard_data/ncr/measure_info.json"],
                                  cwd=repo, capture_output=True, text=True).stdout
    assert json.loads(committed_mi) == {"broadband_x": {"a": 1}, "health_y": {"b": 2}}
    # but the regenerated data + dashboard csv ARE committed
    tree = subprocess.run(["git", "show", "--stat", "HEAD"], cwd=repo, capture_output=True, text=True).stdout
    assert "ncr_ct_demo.csv.xz" in tree
    assert "ncr_demo.csv.xz" in tree
    # working-tree measure_info is restored to the committed (un-clobbered) content
    assert json.loads(mi.read_text()) == {"broadband_x": {"a": 1}, "health_y": {"b": 2}}
