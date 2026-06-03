import pandas as pd
from sdc_core.io import write_data


def test_write_data_passes_measure_info_to_standardize(monkeypatch, tmp_path):
    captured = {}

    def fake_standardize_all(df, *, measure_info=None, **kw):
        captured["measure_info"] = measure_info
        return df

    import sdc_core.io as io
    monkeypatch.setattr(io, "standardize_all", fake_standardize_all)

    df = pd.DataFrame({
        "geoid": ["51001000020"], "year": [2018], "measure": ["pop"],
        "value": [1.0], "moe": [pd.NA], "region_type": ["tract"],
    })
    mi = {"pop_geo20": {"geo_standardize": {"measure_type": "count"}}}
    write_data(df, tmp_path / "out.csv", census_standardize=True, measure_info=mi)
    assert captured["measure_info"] == mi
