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
        assert df["zip"].dtype == object  # string
        assert all(df["zip"].str.len() == 5)

    def test_rent_values_are_positive_numbers(self):
        from ingest import parse_safmr

        df = parse_safmr(ORIGINAL_DIR / "fy2023_safmrs.xlsx")
        for col in ["rent_0br", "rent_1br", "rent_2br", "rent_3br", "rent_4br"]:
            assert df[col].dropna().gt(0).all(), f"{col} has non-positive values"

    def test_has_reasonable_row_count(self):
        from ingest import parse_safmr

        df = parse_safmr(ORIGINAL_DIR / "fy2023_safmrs.xlsx")
        assert len(df) > 30000  # ~33K ZIP codes nationally


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
        assert df["county_fips"].dtype == object
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
        assert df["zip"].dtype == object
        assert df["tract"].dtype == object
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
