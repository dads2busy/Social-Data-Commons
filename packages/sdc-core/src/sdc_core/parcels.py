"""Parcel centroid ingestion from ArcGIS FeatureServer APIs.

Downloads parcel polygon geometries county-by-county, computes centroids,
and stores lightweight centroid files (parquet) for use by
:func:`sdc_core.redistribute.redistribute_parcels`.

Three data sources cover the NCR region:

- **Virginia**: VGIN statewide parcel basemap
- **Maryland**: MD iMAP parcel boundaries
- **DC**: DCGIS Record Lots

Usage:
    from sdc_core.parcels import ingest_parcels

    # Download all NCR parcel centroids
    ingest_parcels(output_dir="geographies/parcels", region="ncr")

    # Download a single VA county
    ingest_va_county("51059", output_dir="geographies/parcels/va")
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import pandas as pd

log = logging.getLogger(__name__)

# --- ArcGIS FeatureServer endpoints ---

VA_FEATURE_SERVER = (
    "https://vginmaps.vdem.virginia.gov/arcgis/rest/services"
    "/VA_Base_Layers/VA_Parcels/FeatureServer/0/query"
)
VA_PAGE_SIZE = 2000
VA_ID_FIELD = "PARCELID"
VA_FIPS_FIELD = "FIPS"

MD_FEATURE_SERVER = (
    "https://mdgeodata.md.gov/imap/rest/services"
    "/PlanningCadastre/MD_ParcelBoundaries/MapServer/0/query"
)
MD_PAGE_SIZE = 1000
MD_ID_FIELD = "ACCTID"

DC_FEATURE_SERVER = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services"
    "/DCGIS_DATA/Property_and_Land_WebMercator/FeatureServer/35/query"
)
DC_PAGE_SIZE = 2000
DC_ID_FIELD = "SSL"

# NCR county FIPS codes by state
NCR_VA_FIPS = [
    "51013",  # Arlington
    "51059",  # Fairfax County
    "51107",  # Loudoun
    "51153",  # Prince William
    "51510",  # Alexandria city
    "51600",  # Fairfax city
    "51610",  # Falls Church city
    "51683",  # Manassas city
    "51685",  # Manassas Park city
]

NCR_MD_FIPS = [
    "24017",  # Charles
    "24021",  # Frederick
    "24031",  # Montgomery
    "24033",  # Prince George's
]


def _query_feature_server(
    url: str,
    where: str,
    out_fields: str,
    page_size: int,
    *,
    out_sr: int = 4326,
    geometry_precision: int = 6,
    delay: float = 0.5,
    max_records: int | None = None,
) -> list[dict]:
    """Page through an ArcGIS FeatureServer query, returning all GeoJSON features.

    Parameters
    ----------
    max_records : int or None
        Stop after fetching this many records (for testing). None = fetch all.
    """
    all_features: list[dict] = []
    offset = 0

    with httpx.Client(timeout=120) as client:
        while True:
            batch_size = page_size
            if max_records is not None:
                remaining = max_records - len(all_features)
                if remaining <= 0:
                    break
                batch_size = min(page_size, remaining)

            params = {
                "where": where,
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": out_sr,
                "geometryPrecision": geometry_precision,
                "resultOffset": offset,
                "resultRecordCount": batch_size,
                "f": "geojson",
            }

            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            features = data.get("features", [])
            if not features:
                break

            all_features.extend(features)
            log.info("  fetched %d features (total: %d)", len(features), len(all_features))

            # Check if there are more pages
            if len(features) < batch_size:
                break

            offset += len(features)
            time.sleep(delay)

    return all_features


def _features_to_centroids(features: list[dict], id_field: str, fips: str) -> pd.DataFrame:
    """Convert GeoJSON polygon features to a centroid DataFrame."""
    from shapely.geometry import shape

    rows = []
    for feat in features:
        geom = feat.get("geometry")
        props = feat.get("properties", {})
        if geom is None:
            continue

        try:
            poly = shape(geom)
            centroid = poly.centroid
            rows.append(
                {
                    "parcel_id": str(props.get(id_field, "")),
                    "fips": fips,
                    "lon": round(centroid.x, 6),
                    "lat": round(centroid.y, 6),
                }
            )
        except Exception:
            continue

    return pd.DataFrame(rows)


def ingest_va_county(fips: str, output_dir: str | Path) -> Path:
    """Download parcel centroids for a single Virginia county.

    Parameters
    ----------
    fips : str
        5-digit county FIPS code (e.g., "51059" for Fairfax).
    output_dir : path
        Directory to write output file.

    Returns
    -------
    Path
        Path to the written parquet file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Ingesting VA parcels for FIPS %s", fips)
    features = _query_feature_server(
        url=VA_FEATURE_SERVER,
        where=f"{VA_FIPS_FIELD}='{fips}'",
        out_fields=f"{VA_FIPS_FIELD},{VA_ID_FIELD}",
        page_size=VA_PAGE_SIZE,
    )

    df = _features_to_centroids(features, VA_ID_FIELD, fips)
    out_path = output_dir / f"{fips}_parcel_centroids.parquet"
    df.to_parquet(out_path, index=False)
    log.info("Wrote %d centroids to %s", len(df), out_path)
    return out_path


def ingest_md_county(fips: str, output_dir: str | Path) -> Path:
    """Download parcel centroids for a single Maryland county.

    Parameters
    ----------
    fips : str
        5-digit county FIPS code (e.g., "24031" for Montgomery).
    output_dir : path
        Directory to write output file.

    Returns
    -------
    Path
        Path to the written parquet file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # MD parcels have a CT2020 field (census tract FIPS) that starts with the county FIPS
    log.info("Ingesting MD parcels for FIPS %s", fips)
    features = _query_feature_server(
        url=MD_FEATURE_SERVER,
        where=f"CT2020 LIKE '{fips}%'",
        out_fields=MD_ID_FIELD,
        page_size=MD_PAGE_SIZE,
    )

    df = _features_to_centroids(features, MD_ID_FIELD, fips)
    out_path = output_dir / f"{fips}_parcel_centroids.parquet"
    df.to_parquet(out_path, index=False)
    log.info("Wrote %d centroids to %s", len(df), out_path)
    return out_path


def ingest_dc(output_dir: str | Path) -> Path:
    """Download record lot centroids for Washington DC.

    Returns
    -------
    Path
        Path to the written parquet file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fips = "11001"

    log.info("Ingesting DC record lots")
    features = _query_feature_server(
        url=DC_FEATURE_SERVER,
        where="1=1",
        out_fields=DC_ID_FIELD,
        page_size=DC_PAGE_SIZE,
    )

    df = _features_to_centroids(features, DC_ID_FIELD, fips)
    out_path = output_dir / f"{fips}_parcel_centroids.parquet"
    df.to_parquet(out_path, index=False)
    log.info("Wrote %d centroids to %s", len(df), out_path)
    return out_path


def ingest_parcels(
    output_dir: str | Path,
    region: str = "ncr",
    *,
    states: list[str] | None = None,
    fips_codes: list[str] | None = None,
) -> list[Path]:
    """Download parcel centroids for a region.

    Parameters
    ----------
    output_dir : path
        Root output directory. State subdirs (va/, md/, dc/) are created.
    region : str
        Predefined region ("ncr") or "all" for all available.
    states : list[str] or None
        Override: only process these states (e.g., ["va", "dc"]).
    fips_codes : list[str] or None
        Override: only process these specific FIPS codes.

    Returns
    -------
    list[Path]
        Paths to all written parquet files.
    """
    output_dir = Path(output_dir)
    written: list[Path] = []

    if fips_codes is not None:
        # Process specific FIPS codes
        for fips in fips_codes:
            if fips.startswith("51"):
                written.append(ingest_va_county(fips, output_dir / "va"))
            elif fips.startswith("24"):
                written.append(ingest_md_county(fips, output_dir / "md"))
            elif fips.startswith("11"):
                written.append(ingest_dc(output_dir / "dc"))
        return written

    # Determine which counties to process
    va_fips = NCR_VA_FIPS if region == "ncr" else []
    md_fips = NCR_MD_FIPS if region == "ncr" else []
    do_dc = region == "ncr"

    if states is not None:
        if "va" not in states:
            va_fips = []
        if "md" not in states:
            md_fips = []
        if "dc" not in states:
            do_dc = False

    for fips in va_fips:
        written.append(ingest_va_county(fips, output_dir / "va"))

    for fips in md_fips:
        written.append(ingest_md_county(fips, output_dir / "md"))

    if do_dc:
        written.append(ingest_dc(output_dir / "dc"))

    log.info("Parcel ingestion complete: %d files written", len(written))
    return written


def load_parcel_centroids(parcel_dir: str | Path, fips_codes: list[str] | None = None) -> pd.DataFrame:
    """Load parcel centroids from parquet files.

    Parameters
    ----------
    parcel_dir : path
        Root directory containing state subdirs with parquet files.
    fips_codes : list[str] or None
        If provided, only load these counties. Otherwise loads all.

    Returns
    -------
    pd.DataFrame
        Combined centroids with columns: parcel_id, fips, lon, lat.
    """
    parcel_dir = Path(parcel_dir)
    parts = []

    for pq_file in sorted(parcel_dir.rglob("*_parcel_centroids.parquet")):
        file_fips = pq_file.stem.split("_")[0]
        if fips_codes is not None and file_fips not in fips_codes:
            continue
        parts.append(pd.read_parquet(pq_file))

    if not parts:
        return pd.DataFrame(columns=["parcel_id", "fips", "lon", "lat"])

    return pd.concat(parts, ignore_index=True)
