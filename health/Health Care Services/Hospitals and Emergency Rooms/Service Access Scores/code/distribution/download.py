"""Download CMS Hospital Compare data and geocode hospital addresses.

Downloads CMS Hospital Compare archive ZIPs for 2015-2025, extracts the
hospital general information CSV from each ZIP, filters to VA/DC/MD
non-psychiatric hospitals, and geocodes via HIFLD fallback + Census Geocoder.
"""

import io
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
from sdc_core.log import get_logger

log = get_logger('hospitals.download')

TOPIC_DIR = Path(__file__).resolve().parents[2]
ORIGINAL_DIR = TOPIC_DIR / 'data' / 'original'
WORKING_DIR = TOPIC_DIR / 'data' / 'working'

STATES = {'VA', 'DC', 'MD'}
EXCLUDE_TYPES = {'Psychiatric'}

ALL_YEARS = list(range(2015, 2026))

# CMS URL patterns — month varies by year
CMS_URLS = {
    2015: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2015/hos_revised_flatfiles_archive_12_2015.zip',
    2016: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2016/hos_revised_flatfiles_archive_12_2016.zip',
    2017: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2017/hos_revised_flatfiles_archive_10_2017.zip',
    2018: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2018/hos_revised_flatfiles_archive_10_2018.zip',
    2019: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2019/hos_revised_flatfiles_archive_10_2019.zip',
    2020: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2020/hos_revised_flatfiles_archive_04_2020.zip',
    2021: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2021/hospitals_10_2021.zip',
    2022: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2022/hospitals_10_2022.zip',
    2023: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2023/hospitals_10_2023.zip',
    2024: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2024/hospitals_10_2024.zip',
    2025: 'https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2025/hospitals_04_2025.zip',
}

# Column name variants across CMS years
CMS_COLUMN_MAP = {
    'Provider ID': 'facility_id',
    'Facility ID': 'facility_id',
    'Hospital Name': 'facility_name',
    'Facility Name': 'facility_name',
    'Address': 'address',
    'City': 'city',
    'City/Town': 'city',
    'State': 'state',
    'ZIP Code': 'zip_code',
    'County Name': 'county_name',
    'County/Parish': 'county_name',
    'Phone Number': 'phone_number',
    'Telephone Number': 'phone_number',
    'Hospital Type': 'hospital_type',
    'Hospital Ownership': 'hospital_ownership',
    'Emergency Services': 'emergency_services',
}

OUTPUT_COLUMNS = [
    'facility_id', 'facility_name', 'address', 'city', 'state', 'zip_code',
    'county_name', 'phone_number', 'hospital_type', 'hospital_ownership',
    'emergency_services', 'year',
]


def find_general_info_csv(zf: zipfile.ZipFile) -> str:
    """Find the Hospital General Information CSV within a CMS ZIP archive."""
    csv_names = [n for n in zf.namelist() if n.lower().endswith('.csv')]
    if not csv_names:
        raise FileNotFoundError('No CSV found in ZIP')

    # Try to match "General" in the filename (case-insensitive)
    for n in csv_names:
        if 'general' in n.lower():
            return n

    # Fall back to the first CSV (2015-2016 ZIPs may not have "General" in name)
    # Sort by name and pick the one most likely to be general info
    # The general info CSV typically has the most rows and fewest columns
    log.warning('No "General" match in ZIP files: %s; using first CSV', csv_names)
    return csv_names[0]


def download_and_filter_year(year: int) -> pd.DataFrame:
    """Download CMS Hospital Compare ZIP, extract general info, filter to VA/DC/MD."""
    url = CMS_URLS.get(year)
    if not url:
        raise ValueError(f'No CMS URL configured for year {year}')

    log.info('Downloading CMS Hospital Compare for %d: %s', year, url)
    resp = requests.get(url, timeout=600)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = find_general_info_csv(zf)
        log.info('Reading %s from ZIP (%d files total)', csv_name, len(zf.namelist()))

        with zf.open(csv_name) as f:
            dt = pd.read_csv(f, dtype=str, low_memory=False, encoding='latin-1')

    log.info('Raw rows: %d, columns: %s', len(dt), list(dt.columns[:12]))

    # Standardize column names
    dt.columns = [c.strip() for c in dt.columns]
    rename = {col: CMS_COLUMN_MAP[col] for col in dt.columns if col in CMS_COLUMN_MAP}
    dt = dt.rename(columns=rename)

    required = {'facility_id', 'state', 'hospital_type'}
    missing = required - set(dt.columns)
    if missing:
        raise ValueError(f'Missing columns for {year}: {missing}. Available: {list(dt.columns)}')

    # Fill optional columns
    for col in OUTPUT_COLUMNS:
        if col not in dt.columns and col != 'year':
            dt[col] = ''

    # Filter: state in VA/DC/MD
    dt['state'] = dt['state'].fillna('').str.strip().str.upper()
    state_mask = dt['state'].isin(STATES)

    # Filter: exclude psychiatric hospitals
    dt['hospital_type'] = dt['hospital_type'].fillna('').str.strip()
    type_mask = ~dt['hospital_type'].str.lower().str.contains('psychiatric', na=False)

    filtered = dt[state_mask & type_mask].copy()
    filtered['year'] = year
    filtered = filtered[OUTPUT_COLUMNS]

    log.info(
        'Year %d: %d hospitals after filtering (types: %s)',
        year, len(filtered), filtered['hospital_type'].unique().tolist(),
    )
    return filtered


def download_all(years: list[int] | None = None, skip_existing: bool = True) -> None:
    """Download and filter CMS Hospital Compare data for all specified years."""
    if years is None:
        years = ALL_YEARS

    ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)

    for year in years:
        out_path = ORIGINAL_DIR / f'cms_hospitals_{year}.csv'
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


def read_and_filter_original(path: Path, year: int) -> pd.DataFrame:
    """Read a CMS original CSV, standardize columns, filter to VA/DC/MD non-psychiatric."""
    df = pd.read_csv(path, dtype=str, low_memory=False, encoding='latin-1')
    df.columns = [c.strip() for c in df.columns]
    rename = {col: CMS_COLUMN_MAP[col] for col in df.columns if col in CMS_COLUMN_MAP}
    df = df.rename(columns=rename)

    for col in OUTPUT_COLUMNS:
        if col not in df.columns and col != 'year':
            df[col] = ''

    df['state'] = df['state'].fillna('').str.strip().str.upper()
    df['hospital_type'] = df['hospital_type'].fillna('').str.strip()

    state_mask = df['state'].isin(STATES)
    type_mask = ~df['hospital_type'].str.lower().str.contains('psychiatric', na=False)

    filtered = df[state_mask & type_mask].copy()
    filtered['year'] = year
    filtered = filtered[OUTPUT_COLUMNS]
    return filtered


def build_combined_working_file(years: list[int] | None = None) -> Path:
    """Combine all per-year CSVs into one working file for VA/DC/MD.

    Handles both filtered (from download.py) and unfiltered (legacy R-downloaded) originals.
    """
    if years is None:
        years = ALL_YEARS

    frames = []
    for year in years:
        path = ORIGINAL_DIR / f'cms_hospitals_{year}.csv'
        if path.exists():
            df = read_and_filter_original(path, year)
            frames.append(df)
            log.info('Year %d: %d hospitals after filtering', year, len(df))
        else:
            log.warning('Missing %s — skipping', path.name)

    if not frames:
        raise FileNotFoundError('No per-year CMS hospital CSVs found in data/original/')

    combined = pd.concat(frames, ignore_index=True)
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WORKING_DIR / 'vadcmd_cms_2015_2025_hospitals.csv'
    combined.to_csv(out_path, index=False)
    log.info('Wrote combined file: %s (%d rows)', out_path.name, len(combined))
    return out_path


# ---------------------------------------------------------------------------
# Geocoding: HIFLD primary, Census Geocoder fallback
# ---------------------------------------------------------------------------

CENSUS_GEOCODER_URL = (
    'https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress'
)


def geocode_address(address: str) -> tuple[float | None, float | None]:
    """Geocode a single address via Census Geocoder API."""
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
        log.debug('Census geocode failed for %s: %s', address[:60], e)
    return None, None


def load_hifld_lookup() -> pd.DataFrame:
    """Load HIFLD hospital file as a geocode lookup."""
    hifld_path = ORIGINAL_DIR / 'us_hifld_2022_hospitals.csv'
    if not hifld_path.exists():
        log.warning('HIFLD file not found at %s', hifld_path)
        return pd.DataFrame()

    hifld = pd.read_csv(hifld_path, dtype=str)
    hifld['LATITUDE'] = pd.to_numeric(hifld['LATITUDE'], errors='coerce')
    hifld['LONGITUDE'] = pd.to_numeric(hifld['LONGITUDE'], errors='coerce')
    hifld = hifld.dropna(subset=['LATITUDE', 'LONGITUDE'])

    # Normalize for matching
    hifld['_name_norm'] = hifld['NAME'].fillna('').str.strip().str.upper()
    hifld['_state_norm'] = hifld['STATE'].fillna('').str.strip().str.upper()
    hifld['_addr_norm'] = hifld['ADDRESS'].fillna('').str.strip().str.upper()
    hifld['_city_norm'] = hifld['CITY'].fillna('').str.strip().str.upper()

    return hifld


def match_hifld(
    hospitals: pd.DataFrame, hifld: pd.DataFrame,
) -> pd.DataFrame:
    """Match CMS hospitals to HIFLD records for lat/lon.

    Strategy: match on (facility_name + state), then fall back to (address + city + state).
    """
    hospitals = hospitals.copy()
    hospitals['lat'] = None
    hospitals['long'] = None
    hospitals['geo_source'] = ''

    hospitals['_name_norm'] = hospitals['facility_name'].fillna('').str.strip().str.upper()
    hospitals['_state_norm'] = hospitals['state'].fillna('').str.strip().str.upper()
    hospitals['_addr_norm'] = hospitals['address'].fillna('').str.strip().str.upper()
    hospitals['_city_norm'] = hospitals['city'].fillna('').str.strip().str.upper()

    if hifld.empty:
        return hospitals

    # Build HIFLD lookup dicts
    name_state_to_coords: dict[tuple[str, str], tuple[float, float]] = {}
    addr_city_state_to_coords: dict[tuple[str, str, str], tuple[float, float]] = {}

    for _, row in hifld.iterrows():
        key_ns = (row['_name_norm'], row['_state_norm'])
        if key_ns not in name_state_to_coords:
            name_state_to_coords[key_ns] = (row['LATITUDE'], row['LONGITUDE'])

        key_acs = (row['_addr_norm'], row['_city_norm'], row['_state_norm'])
        if key_acs not in addr_city_state_to_coords:
            addr_city_state_to_coords[key_acs] = (row['LATITUDE'], row['LONGITUDE'])

    matched = 0
    for idx, row in hospitals.iterrows():
        # Try name + state
        key_ns = (row['_name_norm'], row['_state_norm'])
        coords = name_state_to_coords.get(key_ns)
        if coords:
            hospitals.at[idx, 'lat'] = coords[0]
            hospitals.at[idx, 'long'] = coords[1]
            hospitals.at[idx, 'geo_source'] = 'hifld_name'
            matched += 1
            continue

        # Try address + city + state
        key_acs = (row['_addr_norm'], row['_city_norm'], row['_state_norm'])
        coords = addr_city_state_to_coords.get(key_acs)
        if coords:
            hospitals.at[idx, 'lat'] = coords[0]
            hospitals.at[idx, 'long'] = coords[1]
            hospitals.at[idx, 'geo_source'] = 'hifld_addr'
            matched += 1

    log.info('HIFLD matched %d / %d unique hospital records', matched, len(hospitals))
    return hospitals


def geocode_missing(hospitals: pd.DataFrame) -> pd.DataFrame:
    """Geocode hospitals not matched by HIFLD using Census Geocoder."""
    missing = hospitals[hospitals['lat'].isna()].copy()
    if len(missing) == 0:
        log.info('All hospitals geocoded via HIFLD — no Census geocoding needed')
        return hospitals

    log.info('Geocoding %d hospitals via Census Geocoder', len(missing))

    for idx, row in missing.iterrows():
        address_str = f"{row['address']} {row['city']} {row['state']} {row['zip_code']}"
        lat, lon = geocode_address(address_str)
        if lat is not None:
            hospitals.at[idx, 'lat'] = lat
            hospitals.at[idx, 'long'] = lon
            hospitals.at[idx, 'geo_source'] = 'census'
        time.sleep(0.5)  # Rate limit

    success = hospitals['lat'].notna().sum()
    total = len(hospitals)
    log.info('Geocoding complete: %d / %d geocoded (%.0f%%)', success, total, 100 * success / total)
    return hospitals


def geocode_hospitals(years: list[int] | None = None) -> Path:
    """Geocode all unique hospital locations using HIFLD + Census fallback.

    Produces a deduplicated geocode cache keyed by (facility_id, address, state).
    """
    if years is None:
        years = ALL_YEARS

    # Load combined file
    combined_path = WORKING_DIR / 'vadcmd_cms_2015_2025_hospitals.csv'
    if not combined_path.exists():
        combined_path = build_combined_working_file(years)

    all_data = pd.read_csv(combined_path, dtype=str)

    # Deduplicate by (facility_id, address, state) for geocoding
    unique_hosp = (
        all_data[['facility_id', 'facility_name', 'address', 'city', 'state', 'zip_code']]
        .drop_duplicates(subset=['facility_id', 'address', 'state'])
        .reset_index(drop=True)
    )
    log.info('Unique hospital locations to geocode: %d', len(unique_hosp))

    # Load existing geocode cache
    geo_cache_path = WORKING_DIR / 'vadcmd_cms_2015_2025_hospitals_geo.csv'
    if geo_cache_path.exists():
        existing = pd.read_csv(geo_cache_path, dtype={'facility_id': str, 'zip_code': str})
        cached_keys = set(
            existing[['facility_id', 'address', 'state']]
            .apply(lambda r: (r['facility_id'], r['address'], r['state']), axis=1)
        )
        need_geocode = unique_hosp[
            ~unique_hosp.apply(
                lambda r: (r['facility_id'], r['address'], r['state']) in cached_keys, axis=1,
            )
        ]
        if len(need_geocode) == 0:
            log.info('All hospitals already geocoded in cache (%d)', len(existing))
            return geo_cache_path
        log.info('%d new hospitals need geocoding (%d cached)', len(need_geocode), len(existing))
        unique_hosp = need_geocode
    else:
        existing = pd.DataFrame()

    # HIFLD matching
    hifld = load_hifld_lookup()
    geocoded = match_hifld(unique_hosp, hifld)

    # Census fallback for unmatched
    geocoded = geocode_missing(geocoded)

    # Drop helper columns
    drop_cols = [c for c in geocoded.columns if c.startswith('_')]
    geocoded = geocoded.drop(columns=drop_cols)

    # Combine with existing cache
    if not existing.empty:
        combined_geo = pd.concat([existing, geocoded], ignore_index=True)
        combined_geo = combined_geo.drop_duplicates(subset=['facility_id', 'address', 'state'])
    else:
        combined_geo = geocoded

    combined_geo.to_csv(geo_cache_path, index=False)
    log.info('Wrote geocode cache: %s (%d records)', geo_cache_path.name, len(combined_geo))

    failed = combined_geo['lat'].isna().sum()
    if failed > 0:
        log.warning('%d hospitals could not be geocoded', failed)

    return geo_cache_path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Download CMS Hospital Compare data and geocode')
    parser.add_argument('--years', nargs='*', type=int, default=None, help='Years to download')
    parser.add_argument('--skip-download', action='store_true', help='Skip download, only geocode')
    parser.add_argument('--skip-geocode', action='store_true', help='Skip geocoding')
    parser.add_argument('--force', action='store_true', help='Re-download even if files exist')
    args = parser.parse_args()

    years = args.years or ALL_YEARS

    if not args.skip_download:
        download_all(years=years, skip_existing=not args.force)

    build_combined_working_file(years=years)

    if not args.skip_geocode:
        geocode_hospitals(years=years)
