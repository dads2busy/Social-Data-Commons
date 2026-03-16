"""Tests for HUD FMR ingest pipeline."""

import pandas as pd
import pytest
from pathlib import Path

TOPIC_DIR = Path(__file__).resolve().parents[2]
ORIGINAL_DIR = TOPIC_DIR / "data" / "original"

# Skip all tests if original data files are missing
pytestmark = pytest.mark.skipif(
    not (ORIGINAL_DIR / "fy2023_safmrs.xlsx").exists(),
    reason="Original data files not present",
)


class TestParseSafmr:
    """Test SAFMR Excel parsing."""

    def test_returns_dataframe_with_zip_and_rent_columns(self):
        from ingest import parse_safmr

        df = parse_safmr(ORIGINAL_DIR / "fy2023_safmrs.xlsx")
        assert isinstance(df, pd.DataFrame)
        assert "zip" in df.columns
        expected_rent_cols = ["rent_0br", "rent_1br", "rent_2br", "rent_3br", "rent_4br"]
        for col in expected_rent_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_zip_codes_are_strings_and_zero_padded(self):
        from ingest import parse_safmr

        df = parse_safmr(ORIGINAL_DIR / "fy2023_safmrs.xlsx")
        assert pd.api.types.is_string_dtype(df["zip"])
        assert all(df["zip"].str.len() == 5)

    def test_rent_values_are_positive_numbers(self):
        from ingest import parse_safmr

        df = parse_safmr(ORIGINAL_DIR / "fy2023_safmrs.xlsx")
        for col in ["rent_0br", "rent_1br", "rent_2br", "rent_3br", "rent_4br"]:
            assert df[col].dropna().gt(0).all(), f"{col} has non-positive values"

    def test_has_reasonable_row_count(self):
        from ingest import parse_safmr

        df = parse_safmr(ORIGINAL_DIR / "fy2023_safmrs.xlsx")
        assert len(df) > 25000  # ~27K ZIP codes nationally


class TestParseFmr:
    """Test FMR Excel parsing."""

    def test_returns_dataframe_with_county_fips_and_rents(self):
        from ingest import parse_fmr

        df = parse_fmr(ORIGINAL_DIR / "FY23_FMRs.xlsx")
        assert "county_fips" in df.columns
        for col in ["fmr_0", "fmr_1", "fmr_2", "fmr_3", "fmr_4"]:
            assert col in df.columns

    def test_county_fips_are_5_digit_strings(self):
        from ingest import parse_fmr

        df = parse_fmr(ORIGINAL_DIR / "FY23_FMRs.xlsx")
        assert pd.api.types.is_string_dtype(df["county_fips"])
        assert all(df["county_fips"].str.len() == 5)

    def test_va_counties_present(self):
        from ingest import parse_fmr

        df = parse_fmr(ORIGINAL_DIR / "FY23_FMRs.xlsx")
        va = df[df["county_fips"].str.startswith("51")]
        assert len(va) >= 133  # VA has 133 counties/cities


class TestLoadZipTractCrosswalk:
    """Test ZIP-to-tract crosswalk loading."""

    def test_returns_zip_and_tract_columns(self):
        from ingest import load_zip_tract_crosswalk

        df = load_zip_tract_crosswalk(ORIGINAL_DIR / "ZIP_TRACT_122021.csv")
        assert "zip" in df.columns
        assert "tract" in df.columns

    def test_geoids_are_zero_padded_strings(self):
        from ingest import load_zip_tract_crosswalk

        df = load_zip_tract_crosswalk(ORIGINAL_DIR / "ZIP_TRACT_122021.csv")
        assert pd.api.types.is_string_dtype(df["zip"])
        assert pd.api.types.is_string_dtype(df["tract"])
        # Tracts are 11 digits
        assert all(df["tract"].str.len() == 11)


class TestLoadZctaCounty:
    """Test ZCTA-county relationship file loading."""

    def test_returns_zcta_county_pop_columns(self):
        from ingest import load_zcta_county

        df = load_zcta_county(ORIGINAL_DIR / "zcta_county_rel_10.txt")
        assert "zcta" in df.columns
        assert "county_fips" in df.columns
        assert "pop" in df.columns

    def test_fips_are_5_digit_strings(self):
        from ingest import load_zcta_county

        df = load_zcta_county(ORIGINAL_DIR / "zcta_county_rel_10.txt")
        assert all(df["county_fips"].str.len() == 5)


class TestComputeCountyFmr:
    """Test county-level population-weighted SAFMR averaging."""

    def test_simple_weighted_average(self):
        from ingest import compute_county_fmr

        safmr = pd.DataFrame({
            "zip": ["20001", "20002"],
            "rent_0br": [1000.0, 1200.0],
            "rent_1br": [1100.0, 1300.0],
            "rent_2br": [1200.0, 1400.0],
            "rent_3br": [1500.0, 1700.0],
            "rent_4br": [1800.0, 2000.0],
        })
        zcta_county = pd.DataFrame({
            "zcta": ["20001", "20002"],
            "county_fips": ["11001", "11001"],
            "pop": [100.0, 200.0],
        })
        fmr_fallback = pd.DataFrame({
            "county_fips": ["11001"],
            "fmr_0": [999.0], "fmr_1": [999.0], "fmr_2": [999.0],
            "fmr_3": [999.0], "fmr_4": [999.0],
        })
        result = compute_county_fmr(safmr, zcta_county, ["11001"], fmr_fallback)
        # Weighted avg: (1000*100 + 1200*200) / 300 = 1133.33
        assert abs(result.loc[result["geoid"] == "11001", "rent_0br"].iloc[0] - 1133.33) < 1

    def test_fallback_to_fmr_when_no_zcta_match(self):
        from ingest import compute_county_fmr

        safmr = pd.DataFrame({
            "zip": ["99999"],
            "rent_0br": [500.0], "rent_1br": [600.0], "rent_2br": [700.0],
            "rent_3br": [800.0], "rent_4br": [900.0],
        })
        zcta_county = pd.DataFrame({
            "zcta": ["99999"],
            "county_fips": ["99999"],
            "pop": [100.0],
        })
        fmr_fallback = pd.DataFrame({
            "county_fips": ["51001"],
            "fmr_0": [750.0], "fmr_1": [850.0], "fmr_2": [950.0],
            "fmr_3": [1050.0], "fmr_4": [1150.0],
        })
        result = compute_county_fmr(safmr, zcta_county, ["51001"], fmr_fallback)
        row = result[result["geoid"] == "51001"]
        assert row["rent_0br"].iloc[0] == 750.0
        assert row["data_method"].iloc[0] == "observed"


class TestComputeTractFmr:
    """Test tract-level population-weighted SAFMR averaging with fallback."""

    def test_zip_weighted_average(self):
        from ingest import compute_tract_fmr

        safmr = pd.DataFrame({
            "zip": ["20001", "20002"],
            "rent_0br": [1000.0, 1200.0],
            "rent_1br": [1100.0, 1300.0],
            "rent_2br": [1200.0, 1400.0],
            "rent_3br": [1500.0, 1700.0],
            "rent_4br": [1800.0, 2000.0],
        })
        zip_tract = pd.DataFrame({
            "zip": ["20001", "20002"],
            "tract": ["11001000100", "11001000100"],
        })
        zip_pop = pd.DataFrame({
            "zip": ["20001", "20002"],
            "pop": [100.0, 200.0],
        })
        county_fmr = pd.DataFrame({
            "geoid": ["11001"],
            "rent_0br": [999.0], "rent_1br": [999.0], "rent_2br": [999.0],
            "rent_3br": [999.0], "rent_4br": [999.0], "data_method": ["observed"],
        })
        fmr_fallback = pd.DataFrame({
            "county_fips": ["11001"],
            "fmr_0": [888.0], "fmr_1": [888.0], "fmr_2": [888.0],
            "fmr_3": [888.0], "fmr_4": [888.0],
        })
        result = compute_tract_fmr(
            safmr, zip_tract, zip_pop, county_fmr, fmr_fallback,
            state_fips=["11"],
        )
        row = result[result["geoid"] == "11001000100"]
        assert abs(row["rent_0br"].iloc[0] - 1133.33) < 1
        assert row["data_method"].iloc[0] == "observed"

    def test_fallback_to_county_average(self):
        from ingest import compute_tract_fmr

        safmr = pd.DataFrame({
            "zip": ["99999"],
            "rent_0br": [500.0], "rent_1br": [600.0], "rent_2br": [700.0],
            "rent_3br": [800.0], "rent_4br": [900.0],
        })
        zip_tract = pd.DataFrame({
            "zip": ["99999"],
            "tract": ["99999999999"],
        })
        zip_pop = pd.DataFrame({"zip": ["99999"], "pop": [100.0]})
        county_fmr = pd.DataFrame({
            "geoid": ["11001"],
            "rent_0br": [1050.0], "rent_1br": [1150.0], "rent_2br": [1250.0],
            "rent_3br": [1350.0], "rent_4br": [1450.0], "data_method": ["observed"],
        })
        fmr_fallback = pd.DataFrame({
            "county_fips": ["11001"],
            "fmr_0": [888.0], "fmr_1": [888.0], "fmr_2": [888.0],
            "fmr_3": [888.0], "fmr_4": [888.0],
        })
        result = compute_tract_fmr(
            safmr, zip_tract, zip_pop, county_fmr, fmr_fallback,
            state_fips=["11"],
            tract_geoids=["11001000100"],
        )
        row = result[result["geoid"] == "11001000100"]
        # Should fall back to county average since no ZIP matches this tract
        assert row["rent_0br"].iloc[0] == 1050.0
        assert row["data_method"].iloc[0] == "scaled"
