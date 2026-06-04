import sdc_core.versioning as versioning


def test_sdc_no_publish_forces_no_tag_no_release(monkeypatch, tmp_path):
    calls = {"tag": 0, "release": 0}
    monkeypatch.setattr(versioning, "create_git_tag", lambda *a, **k: calls.__setitem__("tag", calls["tag"] + 1))
    monkeypatch.setattr(versioning, "create_github_release", lambda *a, **k: calls.__setitem__("release", calls["release"] + 1))
    monkeypatch.setenv("SDC_NO_PUBLISH", "1")

    topic = tmp_path / "demo"
    dist = topic / "data" / "distribution"
    dist.mkdir(parents=True)
    (topic / "pipeline.yaml").write_text('name: demo\nversion: "1.0.0"\noutput:\n  path: data/distribution\n')
    import pandas as pd
    pd.DataFrame({"geoid": ["51001000020"], "year": [2018], "measure": ["x_geo20"],
                  "value": [1.0], "moe": [pd.NA], "region_type": ["tract"]}).to_csv(dist / "d.csv.xz", index=False)

    versioning.update_version(topic, force_level="patch")
    assert calls["tag"] == 0
    assert calls["release"] == 0
