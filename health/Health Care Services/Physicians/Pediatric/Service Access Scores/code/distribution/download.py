"""Download CMS Doctors and Clinicians data and geocode provider addresses.

Downloads CMS archive ZIPs for 2018-2025, filters to VA/DC/MD pediatric
medicine physicians, and saves per-year CSVs.  Then geocodes new addresses
via the Census Geocoder API, caching results from prior runs.

Uses the same CMS data source as the Primary Care pipeline but filters to
PEDIATRIC MEDICINE specialty instead of family/general practice.
"""

import io
import json
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
from sdc_core.log import get_logger

log = get_logger('peds.download')

TOPIC_DIR = Path(__file__).resolve().parents[2]
ORIGINAL_DIR = TOPIC_DIR / 'data' / 'original'
WORKING_DIR = TOPIC_DIR / 'data' / 'working'

STATES = {'VA', 'DC', 'MD'}
CREDENTIALS = {'MD', 'DO'}
PEDIATRIC_SPECIALTIES = {'PEDIATRIC MEDICINE'}

ALL_YEARS = list(range(2018, 2026))

# CMS column name variants across years
CMS_COLUMN_MAP = {
    # NPI
    'NPI': 'npi',
    'npi': 'npi',
    # Name
    'lst_nm': 'last_name',
    'Lst_Nm': 'last_name',
    'Provider Last Name': 'last_name',
    'frst_nm': 'first_name',
    'Frst_Nm': 'first_name',
    'Provider First Name': 'first_name',
    # Gender
    'gndr': 'gender',
    'Gndr': 'gender',
    # Credential
    'Cred': 'credential',
    'cred': 'credential',
    # Specialties
    'pri_spec': 'primary_specialty',
    'Pri_Spec': 'primary_specialty',
    'sec_spec_1': 'secondary_specialty_1',
    'Sec_Spec_1': 'secondary_specialty_1',
    'sec_spec_2': 'secondary_specialty_2',
    'Sec_Spec_2': 'secondary_specialty_2',
    # Address
    'adr_ln_1': 'address_line_1',
    'Adr_Ln_1': 'address_line_1',
    'adr_ln_2': 'address_line_2',
    'Adr_Ln_2': 'address_line_2',
    # City
    'cty': 'city',
    'Cty': 'city',
    'City/Town': 'city',
    # State
    'st': 'state',
    'St': 'state',
    'State': 'state',
    # Zip
    'zip': 'postalcode',
    'Zip': 'postalcode',
    'ZIP Code': 'postalcode',
}

OUTPUT_COLUMNS = [
    'npi', 'last_name', 'first_name', 'gender', 'credential',
    'primary_specialty', 'secondary_specialty_1', 'secondary_specialty_2',
    'address_line_1', 'address_line_2', 'city', 'state', 'postalcode', 'year',
]


def cms_url(year: int) -> str:
    """Build the CMS Doctors and Clinicians archive URL for a given year."""
    base = 'https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians'
    if year <= 2019:
        return f'{base}/{year}/doc_archive_12_{year}.zip'
    elif year == 2020:
        return f'{base}/{year}/doctors_and_clinicians_archive_12_{year}.zip'
    else:
        return f'{base}/{year}/doctors_and_clinicians_12_{year}.zip'


def download_and_filter_year(year: int) -> pd.DataFrame:
    """Download CMS ZIP for a year, filter to VA/DC/MD pediatric medicine, return DataFrame."""
    url = cms_url(year)
    log.info('Downloading CMS data for %d: %s', year, url)

    resp = requests.get(url, timeout=600)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith('.csv')]
        if not csv_names:
            raise FileNotFoundError(f'No CSV found in ZIP for {year}')

        # For 2021+ there may be multiple CSVs; pick the one with "National" or largest
        csv_name = csv_names[0]
        for n in csv_names:
            if 'national' in n.lower() or 'National' in n:
                csv_name = n
                break

        log.info('Reading %s from ZIP (%d files)', csv_name, len(csv_names))
        with zf.open(csv_name) as f:
            dt = pd.read_csv(f, dtype=str, low_memory=False, encoding='latin-1')

    log.info('Raw rows: %d, columns: %s', len(dt), list(dt.columns[:15]))

    # Strip whitespace from column names (2025 has tabs in 'Cred\t\t\t\t')
    dt.columns = [c.strip() for c in dt.columns]

    # Standardize column names
    rename = {}
    for col in dt.columns:
        if col in CMS_COLUMN_MAP:
            rename[col] = CMS_COLUMN_MAP[col]
    dt = dt.rename(columns=rename)

    # Verify required columns exist
    required = {'npi', 'state', 'credential', 'primary_specialty'}
    missing = required - set(dt.columns)
    if missing:
        raise ValueError(f'Missing columns for {year}: {missing}. Available: {list(dt.columns)}')

    # Fill missing optional columns
    for col in OUTPUT_COLUMNS:
        if col not in dt.columns and col != 'year':
            dt[col] = ''

    # Filter: state in VA/DC/MD, credential MD/DO, pediatric medicine specialty
    dt['credential'] = dt['credential'].fillna('').str.strip().str.upper()
    dt['primary_specialty'] = dt['primary_specialty'].fillna('').str.strip().str.upper()
    dt['secondary_specialty_1'] = dt['secondary_specialty_1'].fillna('').str.strip().str.upper() if 'secondary_specialty_1' in dt.columns else ''
    dt['secondary_specialty_2'] = dt['secondary_specialty_2'].fillna('').str.strip().str.upper() if 'secondary_specialty_2' in dt.columns else ''
    dt['state'] = dt['state'].fillna('').str.strip().str.upper()

    state_mask = dt['state'].isin(STATES)
    cred_mask = dt['credential'].isin(CREDENTIALS)
    spec_mask = (
        dt['primary_specialty'].isin(PEDIATRIC_SPECIALTIES)
        | dt['secondary_specialty_1'].isin(PEDIATRIC_SPECIALTIES)
        | dt['secondary_specialty_2'].isin(PEDIATRIC_SPECIALTIES)
    )

    filtered = dt[state_mask & cred_mask & spec_mask].copy()
    filtered['year'] = year
    filtered = filtered[OUTPUT_COLUMNS]

    log.info('Year %d: %d rows after filtering (%d unique NPIs)', year, len(filtered), filtered['npi'].nunique())
    return filtered


def download_all(years: list[int] | None = None, skip_existing: bool = True) -> None:
    """Download and filter CMS data for all specified years."""
    if years is None:
        years = ALL_YEARS

    ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)

    for year in years:
        out_path = ORIGINAL_DIR / f'vadcmd_cms_{year}_pediatric.csv'
        if skip_existing and out_path.exists():
            log.info('Skipping %d — %s already exists', year, out_path.name)
            continue

        try:
            df = download_and_filter_year(year)
            df.to_csv(out_path, index=False)
            log.info('Wrote %s (%d rows)', out_path.name, len(df))
        except Exception as e:
            log.error('Failed to download year %d: %s', year, e)
            raise


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names from old CMS format to new format."""
    rename = {}
    for col in df.columns:
        if col in CMS_COLUMN_MAP:
            rename[col] = CMS_COLUMN_MAP[col]
    if rename:
        df = df.rename(columns=rename)
    return df


def standardize_existing_files(years: list[int] | None = None) -> None:
    """Re-save existing per-year CSVs with standardized column names if needed."""
    if years is None:
        years = ALL_YEARS

    for year in years:
        path = ORIGINAL_DIR / f'vadcmd_cms_{year}_pediatric.csv'
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype=str, low_memory=False)
        if 'NPI' in df.columns or 'lst_nm' in df.columns:
            log.info('Standardizing columns for %s', path.name)
            df = _standardize_columns(df)
            df['year'] = year
            cols = [c for c in OUTPUT_COLUMNS if c in df.columns]
            df = df[cols]
            df.to_csv(path, index=False)
            log.info('Re-saved %s with standardized columns', path.name)


def build_combined_working_file(years: list[int] | None = None) -> Path:
    """Combine all per-year CSVs into one working file."""
    if years is None:
        years = ALL_YEARS

    frames = []
    for year in years:
        path = ORIGINAL_DIR / f'vadcmd_cms_{year}_pediatric.csv'
        if path.exists():
            df = pd.read_csv(path, dtype={'postalcode': str})
            df = _standardize_columns(df)
            if 'year' not in df.columns:
                df['year'] = year
            frames.append(df)
        else:
            log.warning('Missing %s — skipping', path.name)

    if not frames:
        raise FileNotFoundError('No per-year CSVs found in data/original/')

    combined = pd.concat(frames, ignore_index=True)
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WORKING_DIR / 'vadcmd_cms_2018_2025_pediatric_physicians.csv'
    combined.to_csv(out_path, index=False)
    log.info('Wrote combined file: %s (%d rows)', out_path.name, len(combined))
    return out_path


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

CENSUS_GEOCODER_URL = (
    'https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress'
)


def geocode_address(address: str) -> tuple[float | None, float | None]:
    """Geocode a single address via Census Geocoder API.

    Returns (lat, lon) or (None, None) on failure.
    """
    params = {
        'address': address,
        'benchmark': 'Public_AR_Current',
        'vintage': 'Current_Current',
        'format': 'json',
    }
    try:
        resp = requests.get(CENSUS_GEOCODER_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        matches = data.get('result', {}).get('addressMatches', [])
        if matches:
            coords = matches[0]['coordinates']
            return float(coords['y']), float(coords['x'])
    except Exception as e:
        log.debug('Geocode failed for %s: %s', address[:60], e)
    return None, None


def geocode_new_addresses(years: list[int] | None = None) -> Path:
    """Geocode addresses not already in the cached geocoded file.

    Reads all per-year CSVs, collects unique addresses, checks against the
    existing geocoded cache (including Primary Care's cache as fallback),
    geocodes new ones, and writes an updated cache.
    """
    if years is None:
        years = ALL_YEARS

    # Load all per-year CSVs
    frames = []
    for year in years:
        path = ORIGINAL_DIR / f'vadcmd_cms_{year}_pediatric.csv'
        if path.exists():
            frames.append(pd.read_csv(path, dtype={'postalcode': str}))
    if not frames:
        raise FileNotFoundError('No per-year CSVs found')

    all_data = pd.concat(frames, ignore_index=True)

    # Unique addresses from CMS data
    addr_cols = ['address_line_1', 'city', 'state', 'postalcode']
    unique_addrs = (
        all_data[addr_cols]
        .drop_duplicates()
        .rename(columns={'address_line_1': 'street'})
        .reset_index(drop=True)
    )
    unique_addrs['street'] = unique_addrs['street'].fillna('').str.strip()
    unique_addrs['city'] = unique_addrs['city'].fillna('').str.strip()
    unique_addrs['state'] = unique_addrs['state'].fillna('').str.strip()
    unique_addrs['postalcode'] = unique_addrs['postalcode'].fillna('').str.strip()

    log.info('Total unique addresses across all years: %d', len(unique_addrs))

    # Load existing geocoded cache — check our own first, then Primary Care's
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    geo_cache_path = WORKING_DIR / 'vadcmd_cms_2018_2025_pediatric_physicians_geo.csv'
    primcare_cache = (
        TOPIC_DIR.parents[1] / 'Primary Care' / 'Service Access Scores'
        / 'data' / 'working' / 'vadcmd_cms_2018_2025_primary_care_physicians_geo.csv'
    )

    existing_geo = pd.DataFrame()
    for p in [geo_cache_path, primcare_cache]:
        if p.exists():
            existing_geo = pd.read_csv(p, dtype={'postalcode': str})
            log.info('Loaded geocode cache from %s (%d rows)', p.name, len(existing_geo))
            break

    # Build set of already-geocoded address keys
    geo_key_cols = ['street', 'city', 'state', 'postalcode']
    if not existing_geo.empty and all(c in existing_geo.columns for c in geo_key_cols):
        cached_keys = set(
            existing_geo[geo_key_cols]
            .apply(lambda r: (r['street'].strip(), r['city'].strip(), r['state'].strip(), r['postalcode'].strip()), axis=1)
        )
        existing_geo_dedup = existing_geo.drop_duplicates(subset=geo_key_cols)
    else:
        cached_keys = set()
        existing_geo_dedup = pd.DataFrame()

    # Find addresses needing geocoding
    new_addrs = unique_addrs[
        ~unique_addrs.apply(
            lambda r: (r['street'], r['city'], r['state'], r['postalcode']) in cached_keys,
            axis=1,
        )
    ].copy()

    log.info('Addresses needing geocoding: %d (already cached: %d)', len(new_addrs), len(cached_keys))

    if len(new_addrs) > 0:
        lats, lons, queries = [], [], []
        for i, (_, row) in enumerate(new_addrs.iterrows()):
            address_str = f"{row['street']} {row['city']} {row['state']} {row['postalcode']}"
            lat, lon = geocode_address(address_str)
            lats.append(lat)
            lons.append(lon)
            queries.append('census')

            if (i + 1) % 50 == 0:
                success = sum(1 for la in lats if la is not None)
                log.info('Geocoded %d/%d (%.0f%% success)', i + 1, len(new_addrs), 100 * success / (i + 1))

            time.sleep(0.5)  # Rate limit

        new_addrs['lat'] = lats
        new_addrs['long'] = lons
        new_addrs['query'] = queries
        new_addrs['address'] = new_addrs.apply(
            lambda r: f"{r['street']} {r['city']} {r['state']} {r['postalcode']}", axis=1
        )

        success_count = new_addrs['lat'].notna().sum()
        fail_count = new_addrs['lat'].isna().sum()
        log.info('Geocoding complete: %d success, %d failed', success_count, fail_count)

        # Drop rows that failed geocoding
        new_addrs = new_addrs[new_addrs['lat'].notna()]

    # Combine with existing cache
    geo_cols = ['street', 'city', 'state', 'postalcode', 'address', 'lat', 'long', 'query']
    if not existing_geo_dedup.empty:
        existing_clean = existing_geo_dedup[
            [c for c in geo_cols if c in existing_geo_dedup.columns]
        ].drop_duplicates(subset=['street', 'city', 'state', 'postalcode'])

        if len(new_addrs) > 0:
            new_clean = new_addrs[[c for c in geo_cols if c in new_addrs.columns]]
            combined_geo = pd.concat([existing_clean, new_clean], ignore_index=True)
        else:
            combined_geo = existing_clean
    elif len(new_addrs) > 0:
        combined_geo = new_addrs[[c for c in geo_cols if c in new_addrs.columns]]
    else:
        log.info('No addresses to geocode and no existing cache')
        return geo_cache_path

    combined_geo = combined_geo.drop_duplicates(subset=['street', 'city', 'state', 'postalcode'])
    combined_geo.to_csv(geo_cache_path, index=False)
    log.info('Wrote geocode cache: %s (%d addresses)', geo_cache_path.name, len(combined_geo))
    return geo_cache_path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Download CMS pediatric data and geocode')
    parser.add_argument('--years', nargs='*', type=int, default=None, help='Years to download (default: all)')
    parser.add_argument('--skip-download', action='store_true', help='Skip download, only geocode')
    parser.add_argument('--skip-geocode', action='store_true', help='Skip geocoding')
    parser.add_argument('--force', action='store_true', help='Re-download even if files exist')
    args = parser.parse_args()

    years = args.years or ALL_YEARS

    if not args.skip_download:
        download_all(years=years, skip_existing=not args.force)

    standardize_existing_files(years=years)
    build_combined_working_file(years=years)

    if not args.skip_geocode:
        geocode_new_addresses(years=years)
