"""Download substance abuse treatment facilities from SAMHSA findtreatment.gov API.

Paginates through the SAMHSA treatment locator API (sType=SA), filters to
states within travel time coverage (VA/DC/MD/WV/KY/NC/TN/DE), and writes
a CSV of facility locations for use by ingest.py.
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests
from sdc_core.log import get_logger

log = get_logger('substance.download')

TOPIC_DIR = Path(__file__).resolve().parents[2]
WORKING_DIR = TOPIC_DIR / 'data' / 'working'

SAMHSA_URL = 'https://findtreatment.gov/locator/listing'
STYPE = 'SA'
PAGE_SIZE = 100
SEARCH_ADDR = '37.5,-78.5'  # VA centroid

# States covered by travel time matrices
KEEP_STATES = {'VA', 'DC', 'MD', 'WV', 'KY', 'NC', 'TN', 'DE'}


def fetch_page(page: int, max_retries: int = 5) -> dict:
    """Fetch a single page of SAMHSA results with retry on 403."""
    data = {
        'sType': STYPE,
        'sAddr': SEARCH_ADDR,
        'pageSize': str(PAGE_SIZE),
        'page': str(page),
        'sort': '0',
        'sd': '0',
    }
    for attempt in range(max_retries):
        resp = requests.post(
            SAMHSA_URL,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=60,
        )
        if resp.status_code == 403 and attempt < max_retries - 1:
            wait = 60 * (attempt + 1)
            log.warning('Got 403 on page %d, retrying in %ds (attempt %d/%d)',
                        page, wait, attempt + 1, max_retries)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


def download_all_facilities() -> pd.DataFrame:
    """Download all SA facilities from SAMHSA, paginating through all pages.

    Saves progress to a temp JSON file so partial downloads can resume.
    """
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    progress_path = WORKING_DIR / '_sa_download_progress.json'

    # Try to resume from progress file
    all_rows = []
    start_page = 1
    if progress_path.exists():
        with open(progress_path) as f:
            progress = json.load(f)
        all_rows = progress.get('rows', [])
        start_page = progress.get('next_page', 1)
        log.info('Resuming from page %d with %d rows already downloaded', start_page, len(all_rows))

    # First page to get total
    if start_page == 1:
        result = fetch_page(1)
        total_pages = result['totalPages']
        record_count = result['recordCount']
        log.info('SAMHSA SA: %d total records, %d pages', record_count, total_pages)
        all_rows = list(result.get('rows', []))
        start_page = 2
    else:
        result = fetch_page(1)
        total_pages = result['totalPages']

    for page in range(start_page, total_pages + 1):
        time.sleep(1.5)
        if page % 50 == 0:
            log.info('Cooldown pause at page %d...', page)
            time.sleep(10)
        result = fetch_page(page)
        rows = result.get('rows', [])
        all_rows.extend(rows)
        if page % 20 == 0:
            log.info('Fetched page %d/%d (%d rows so far)', page, total_pages, len(all_rows))
            with open(progress_path, 'w') as f:
                json.dump({'rows': all_rows, 'next_page': page + 1}, f)

    log.info('Downloaded %d total facility records', len(all_rows))

    if progress_path.exists():
        progress_path.unlink()

    # Extract relevant fields
    records = []
    for row in all_rows:
        records.append({
            'frid': row.get('frid', ''),
            'name': row.get('name1', ''),
            'address': row.get('street1', ''),
            'city': row.get('city', ''),
            'state': row.get('state', ''),
            'zip': row.get('zip', ''),
            'lat': row.get('latitude', ''),
            'lon': row.get('longitude', ''),
        })

    df = pd.DataFrame(records)

    # Filter to states within travel time coverage
    df['state'] = df['state'].str.strip().str.upper()
    df = df[df['state'].isin(KEEP_STATES)].copy()
    log.info('After state filter (%s): %d facilities', ', '.join(sorted(KEEP_STATES)), len(df))

    # Convert lat/lon to float, drop missing
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    before = len(df)
    df = df.dropna(subset=['lat', 'lon']).reset_index(drop=True)
    if before > len(df):
        log.warning('Dropped %d facilities with missing coordinates', before - len(df))

    return df


def run() -> Path:
    """Download SAMHSA SA facilities and write to working directory."""
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WORKING_DIR / 'samhsa_2025_substance_abuse_facilities.csv'

    df = download_all_facilities()
    df.to_csv(out_path, index=False)
    log.info('Wrote %s (%d facilities)', out_path.name, len(df))
    return out_path


if __name__ == '__main__':
    run()
