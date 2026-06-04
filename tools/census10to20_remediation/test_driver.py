import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

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
    assert report["before"]["status"] == "fail"
    assert report["before"]["max_ratio"] > 1.1
