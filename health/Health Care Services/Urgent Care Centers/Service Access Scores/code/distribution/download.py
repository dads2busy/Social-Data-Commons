"""Download NPPES NPI Registry data and geocode urgent care center addresses.

Downloads the monthly NPPES full data file from CMS, filters to active
urgent care centers (taxonomy 261QU0200X) in VA/DC/MD, and geocodes
facility addresses via the Census Geocoder API with caching.
"""

import io
import re
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
from sdc_core.log import get_logger

log = get_logger('urgent.download')

TOPIC_DIR = Path(__file__).resolve().parents[2]
ORIGINAL_DIR = TOPIC_DIR / 'data' / 'original'
WORKING_DIR = TOPIC_DIR / 'data' / 'working'

STATES = {'VA', 'DC', 'MD'}
URGENT_CARE_TAXONOMY = '261QU0200X'

NPPES_INDEX_URL = 'https://download.cms.gov/nppes/NPI_Files.html'

# Only load the columns we need from the ~8GB NPPES file
NPPES_USECOLS = [
    'NPI',
    'Entity Type Code',
    'Provider Organization Name (Legal Business Name)',
    'Provider First Line Business Practice Location Address',
    'Provider Second Line Business Practice Location Address',
    'Provider Business Practice Location Address City Name',
    'Provider Business Practice Location Address State Name',
    'Provider Business Practice Location Address Postal Code',
    'NPI Deactivation Date',
    'Provider Enumeration Date',
] + [f'Healthcare Provider Taxonomy Code_{i}' for i in range(1, 16)]

# Standardized output column names
OUTPUT_COLUMNS = [
    'npi', 'name', 'address_line_1', 'address_line_2',
    'city', 'state', 'postalcode', 'enumeration_date',
]

NPPES_COLUMN_MAP = {
    'NPI': 'npi',
    'Provider Organization Name (Legal Business Name)': 'name',
    'Provider First Line Business Practice Location Address': 'address_line_1',
    'Provider Second Line Business Practice Location Address': 'address_line_2',
    'Provider Business Practice Location Address City Name': 'city',
    'Provider Business Practice Location Address State Name': 'state',
    'Provider Business Practice Location Address Postal Code': 'postalcode',
    'Provider Enumeration Date': 'enumeration_date',
}


def find_nppes_zip_url() -> str:
    """Scrape the NPPES download page to find the latest full data file URL."""
    log.info('Fetching NPPES download page: %s', NPPES_INDEX_URL)
    resp = requests.get(NPPES_INDEX_URL, timeout=30)
    resp.raise_for_status()

    # Look for the full monthly file (not weekly or deactivation)
    # Pattern: NPPES_Data_Dissemination_<Month>_<Year>_V2.zip (excludes Weekly)
    pattern = r'(NPPES_Data_Dissemination_[A-Z][a-z]+_\d{4}_V2\.zip)'
    matches = re.findall(pattern, resp.text)

    if not matches:
        raise RuntimeError(
            'Could not find NPPES full data file URL on download page. '
            'Check https://download.cms.gov/nppes/NPI_Files.html manually.'
        )

    url = 'https://download.cms.gov/nppes/' + matches[0]

    log.info('Found NPPES data file URL: %s', url)
    return url


def download_and_filter_nppes(skip_existing: bool = True) -> pd.DataFrame:
    """Download NPPES full file, filter to VA/DC/MD urgent care centers.

    Returns filtered DataFrame with standardized column names.
    """
    out_path = ORIGINAL_DIR / 'vadcmd_nppes_urgent_care.csv'
    if skip_existing and out_path.exists():
        log.info('Filtered file already exists: %s — loading from disk', out_path.name)
        return pd.read_csv(out_path, dtype=str)

    url = find_nppes_zip_url()
    log.info('Downloading NPPES data file (this may take several minutes)...')

    resp = requests.get(url, timeout=1800, stream=True)
    resp.raise_for_status()

    # Read content into memory
    content = resp.content
    log.info('Download complete (%.1f MB)', len(content) / 1e6)

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        # Find the main data CSV (npidata_pfile_*.csv)
        csv_names = [
            n for n in zf.namelist()
            if n.lower().startswith('npidata_pfile') and n.lower().endswith('.csv')
        ]
        if not csv_names:
            # Fallback: any CSV with 'npidata' in the name
            csv_names = [
                n for n in zf.namelist()
                if 'npidata' in n.lower() and n.lower().endswith('.csv')
            ]
        if not csv_names:
            raise FileNotFoundError(
                f'No npidata CSV found in ZIP. Contents: {zf.namelist()[:20]}'
            )

        csv_name = csv_names[0]
        log.info('Reading %s from ZIP (using usecols for efficiency)', csv_name)

        with zf.open(csv_name) as f:
            dt = pd.read_csv(
                f,
                dtype=str,
                usecols=lambda c: c in set(NPPES_USECOLS),
                encoding='latin-1',
                low_memory=False,
            )

    log.info('Raw NPPES rows: %d', len(dt))

    # Filter: Entity Type Code = 2 (organizations only)
    dt = dt[dt['Entity Type Code'] == '2'].copy()
    log.info('After entity type filter (organizations): %d', len(dt))

    # Filter: state in VA/DC/MD
    state_col = 'Provider Business Practice Location Address State Name'
    dt[state_col] = dt[state_col].fillna('').str.strip().str.upper()
    dt = dt[dt[state_col].isin(STATES)].copy()
    log.info('After state filter (VA/DC/MD): %d', len(dt))

    # Filter: active only (NPI Deactivation Date is blank)
    dt = dt[dt['NPI Deactivation Date'].fillna('').str.strip() == ''].copy()
    log.info('After active-only filter: %d', len(dt))

    # Filter: any taxonomy code column contains urgent care taxonomy
    taxonomy_cols = [
        c for c in dt.columns
        if c.startswith('Healthcare Provider Taxonomy Code_')
    ]
    taxonomy_mask = pd.Series(False, index=dt.index)
    for col in taxonomy_cols:
        taxonomy_mask = taxonomy_mask | (
            dt[col].fillna('').str.strip() == URGENT_CARE_TAXONOMY
        )
    dt = dt[taxonomy_mask].copy()
    log.info('After urgent care taxonomy filter (%s): %d', URGENT_CARE_TAXONOMY, len(dt))

    # Rename columns to standardized names
    dt = dt.rename(columns=NPPES_COLUMN_MAP)

    # Clean up postalcode (take first 5 digits)
    dt['postalcode'] = dt['postalcode'].fillna('').str.strip().str[:5]

    # Fill missing optional columns
    for col in OUTPUT_COLUMNS:
        if col not in dt.columns:
            dt[col] = ''

    dt = dt[OUTPUT_COLUMNS].copy()

    # Save filtered data
    ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
    dt.to_csv(out_path, index=False)
    log.info('Wrote %s (%d rows, %d unique NPIs)', out_path.name, len(dt), dt['npi'].nunique())

    return dt


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

CENSUS_GEOCODER_URL = (
    'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
)


def geocode_address(address: str) -> tuple[float | None, float | None]:
    """Geocode a single address via Census Geocoder API.

    Returns (lat, lon) or (None, None) on failure.
    """
    params = {
        'address': address,
        'benchmark': 'Public_AR_Current',
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


def geocode_urgent_care(skip_existing: bool = True) -> Path:
    """Geocode urgent care addresses, using cache from prior runs.

    Reads the filtered NPPES file, collects unique addresses, checks
    against existing geocode cache, geocodes new ones, and writes
    the geocoded output file.
    """
    filtered_path = ORIGINAL_DIR / 'vadcmd_nppes_urgent_care.csv'
    if not filtered_path.exists():
        raise FileNotFoundError(
            f'Filtered NPPES data not found: {filtered_path}. '
            'Run download first.'
        )

    dt = pd.read_csv(filtered_path, dtype=str)
    log.info('Loaded %d urgent care facilities for geocoding', len(dt))

    # Build unique addresses
    addr_cols = ['address_line_1', 'city', 'state', 'postalcode']
    unique_addrs = (
        dt[addr_cols]
        .drop_duplicates()
        .reset_index(drop=True)
        .copy()
    )
    for col in addr_cols:
        unique_addrs[col] = unique_addrs[col].fillna('').str.strip()

    log.info('Total unique addresses: %d', len(unique_addrs))

    # Load existing geocode cache
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = WORKING_DIR / 'vadcmd_nppes_urgent_care_geocode_cache.csv'

    cached_keys: set[tuple[str, ...]] = set()
    existing_cache = pd.DataFrame()
    if cache_path.exists():
        existing_cache = pd.read_csv(cache_path, dtype={'postalcode': str})
        log.info('Loaded geocode cache: %s (%d rows)', cache_path.name, len(existing_cache))
        cache_key_cols = ['address_line_1', 'city', 'state', 'postalcode']
        if all(c in existing_cache.columns for c in cache_key_cols):
            cached_keys = set(
                existing_cache[cache_key_cols].apply(
                    lambda r: tuple(str(v).strip() for v in r), axis=1
                )
            )

    # Find addresses needing geocoding
    new_addrs = unique_addrs[
        ~unique_addrs.apply(
            lambda r: (r['address_line_1'], r['city'], r['state'], r['postalcode']) in cached_keys,
            axis=1,
        )
    ].copy()

    log.info(
        'Addresses needing geocoding: %d (already cached: %d)',
        len(new_addrs), len(cached_keys),
    )

    if len(new_addrs) > 0:
        lats, lons = [], []
        for i, (_, row) in enumerate(new_addrs.iterrows()):
            address_str = (
                f"{row['address_line_1']} {row['city']} "
                f"{row['state']} {row['postalcode']}"
            )
            lat, lon = geocode_address(address_str)
            lats.append(lat)
            lons.append(lon)

            if (i + 1) % 50 == 0:
                success = sum(1 for la in lats if la is not None)
                log.info(
                    'Geocoded %d/%d (%.0f%% success)',
                    i + 1, len(new_addrs), 100 * success / (i + 1),
                )

            time.sleep(0.1)  # Rate limit

        new_addrs['lat'] = lats
        new_addrs['long'] = lons

        success_count = new_addrs['lat'].notna().sum()
        fail_count = new_addrs['lat'].isna().sum()
        log.info('Geocoding complete: %d success, %d failed', success_count, fail_count)

    # Combine with existing cache
    cache_cols = ['address_line_1', 'city', 'state', 'postalcode', 'lat', 'long']

    if not existing_cache.empty and len(new_addrs) > 0:
        existing_clean = existing_cache[
            [c for c in cache_cols if c in existing_cache.columns]
        ].drop_duplicates(subset=['address_line_1', 'city', 'state', 'postalcode'])
        new_clean = new_addrs[[c for c in cache_cols if c in new_addrs.columns]]
        combined_cache = pd.concat([existing_clean, new_clean], ignore_index=True)
    elif not existing_cache.empty:
        combined_cache = existing_cache[
            [c for c in cache_cols if c in existing_cache.columns]
        ].drop_duplicates(subset=['address_line_1', 'city', 'state', 'postalcode'])
    elif len(new_addrs) > 0:
        combined_cache = new_addrs[[c for c in cache_cols if c in new_addrs.columns]]
    else:
        log.info('No addresses to geocode and no existing cache')
        return cache_path

    combined_cache = combined_cache.drop_duplicates(
        subset=['address_line_1', 'city', 'state', 'postalcode']
    )
    combined_cache.to_csv(cache_path, index=False)
    log.info('Wrote geocode cache: %s (%d addresses)', cache_path.name, len(combined_cache))

    # Merge geocoded coordinates back to full facility data
    geo_dt = dt.merge(
        combined_cache,
        on=['address_line_1', 'city', 'state', 'postalcode'],
        how='left',
    )

    geo_out_path = WORKING_DIR / 'vadcmd_nppes_urgent_care_geo.csv'
    geo_dt.to_csv(geo_out_path, index=False)
    log.info(
        'Wrote geocoded facility file: %s (%d rows, %d with coordinates)',
        geo_out_path.name, len(geo_dt), geo_dt['lat'].notna().sum(),
    )

    return cache_path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Download NPPES urgent care data and geocode',
    )
    parser.add_argument(
        '--skip-download', action='store_true',
        help='Skip download, only geocode',
    )
    parser.add_argument(
        '--skip-geocode', action='store_true',
        help='Skip geocoding',
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Re-download even if files exist',
    )
    args = parser.parse_args()

    if not args.skip_download:
        download_and_filter_nppes(skip_existing=not args.force)

    if not args.skip_geocode:
        geocode_urgent_care(skip_existing=not args.force)
