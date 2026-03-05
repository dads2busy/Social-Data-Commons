"""Zenodo dataset archiving for SDC pipelines.

Uploads pipeline distribution files to Zenodo for permanent archiving
and DOI assignment. Reads metadata from pipeline.yaml and measure_info.json
to populate Zenodo deposit metadata automatically.

Usage::

    from sdc_core.zenodo import upload_to_zenodo

    result = upload_to_zenodo("demographics/Gender")
    print(result.doi)
    print(result.deposit_url)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

from sdc_core.log import get_logger

load_dotenv()

log = get_logger("zenodo")

ZENODO_API = "https://zenodo.org/api"
ZENODO_SANDBOX_API = "https://sandbox.zenodo.org/api"

DEFAULT_CREATORS = [
    {"name": "Social Data Commons", "affiliation": "University of Virginia"},
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ZenodoResult:
    """Outcome of a Zenodo upload operation."""

    pipeline_name: str
    deposit_id: int
    version: str
    doi: str | None = None
    deposit_url: str = ""
    files_uploaded: list[str] = field(default_factory=list)
    is_new_version: bool = False
    published: bool = False


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class ZenodoClient:
    """Minimal Zenodo REST API client."""

    def __init__(
        self,
        access_token: str | None = None,
        *,
        sandbox: bool = False,
    ):
        self.token = access_token or os.environ.get("ZENODO_ACCESS_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Zenodo access token required. Set ZENODO_ACCESS_TOKEN in .env "
                "or pass access_token=."
            )
        base_url = ZENODO_SANDBOX_API if sandbox else ZENODO_API
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=300,
        )
        self._sandbox = sandbox

    @property
    def web_base(self) -> str:
        return "https://sandbox.zenodo.org" if self._sandbox else "https://zenodo.org"

    def create_deposit(self, metadata: dict | None = None) -> dict:
        body = {"metadata": metadata} if metadata else {}
        resp = self._http.post("/deposit/depositions", json=body)
        resp.raise_for_status()
        return resp.json()

    def get_deposit(self, deposit_id: int) -> dict:
        resp = self._http.get(f"/deposit/depositions/{deposit_id}")
        resp.raise_for_status()
        return resp.json()

    def update_metadata(self, deposit_id: int, metadata: dict) -> dict:
        resp = self._http.put(
            f"/deposit/depositions/{deposit_id}",
            json={"metadata": metadata},
        )
        resp.raise_for_status()
        return resp.json()

    def upload_file(self, bucket_url: str, filepath: Path) -> dict:
        data = filepath.read_bytes()
        resp = self._http.put(
            f"{bucket_url}/{filepath.name}",
            content=data,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(data)),
            },
        )
        resp.raise_for_status()
        return resp.json()

    def delete_file(self, deposit_id: int, file_id: str) -> None:
        resp = self._http.delete(
            f"/deposit/depositions/{deposit_id}/files/{file_id}"
        )
        resp.raise_for_status()

    def publish(self, deposit_id: int) -> dict:
        resp = self._http.post(
            f"/deposit/depositions/{deposit_id}/actions/publish"
        )
        resp.raise_for_status()
        return resp.json()

    def new_version(self, deposit_id: int) -> dict:
        resp = self._http.post(
            f"/deposit/depositions/{deposit_id}/actions/newversion"
        )
        resp.raise_for_status()
        original = resp.json()
        draft_url = original["links"]["latest_draft"]
        draft_resp = self._http.get(draft_url)
        draft_resp.raise_for_status()
        return draft_resp.json()


# ---------------------------------------------------------------------------
# Metadata builder
# ---------------------------------------------------------------------------


def _prettify_name(name: str) -> str:
    """Convert pipeline name to a human-readable title."""
    return name.replace("_", " ").replace("-", " ").title()


def _build_description(
    config: dict,
    measure_info: dict | None,
) -> str:
    """Build an HTML description from pipeline metadata."""
    parts = [f"<p>{config.get('description', '').strip()}</p>"]

    if measure_info:
        measures = {k: v for k, v in measure_info.items() if not k.startswith("_")}
        if measures:
            parts.append(f"<h3>Measures ({len(measures)})</h3><ul>")
            for name, info in list(measures.items())[:20]:
                long_name = info.get("long_name", name)
                parts.append(f"<li><strong>{name}</strong>: {long_name}</li>")
            if len(measures) > 20:
                parts.append(f"<li>... and {len(measures) - 20} more</li>")
            parts.append("</ul>")

            # Unique data sources
            seen = set()
            source_items = []
            for info in measures.values():
                for src in info.get("sources", []):
                    src_name = src.get("name", "")
                    if src_name and src_name not in seen:
                        seen.add(src_name)
                        url = src.get("url", "")
                        if url:
                            source_items.append(
                                f'<li><a href="{url}">{src_name}</a></li>'
                            )
                        else:
                            source_items.append(f"<li>{src_name}</li>")
            if source_items:
                parts.append("<h3>Data Sources</h3><ul>")
                parts.extend(source_items)
                parts.append("</ul>")

    return "\n".join(parts)


def _extract_keywords(
    config: dict,
    measure_info: dict | None,
    topic_dir: Path,
) -> list[str]:
    """Extract keywords from pipeline metadata."""
    keywords = {"social data commons", "virginia"}

    if measure_info:
        for info in measure_info.values():
            if isinstance(info, dict):
                cat = info.get("category", "")
                if cat:
                    keywords.add(cat.lower())

    # Add topic category from directory path
    category_names = {
        "demographics", "education", "health", "food",
        "financial_well_being", "housing", "transportation",
        "broadband", "environment", "business_climate",
        "public_safety",
    }
    for part in topic_dir.resolve().parts:
        if part.lower().replace(" ", "_") in category_names:
            keywords.add(part.lower().replace("_", " "))

    return sorted(keywords)


def _extract_dates(config: dict) -> list[dict]:
    """Extract date range from pipeline source years."""
    all_years: set[int] = set()
    sources = config.get("sources", {})
    if isinstance(sources, dict):
        for src in sources.values():
            if isinstance(src, dict):
                for y in src.get("years", []):
                    if isinstance(y, int):
                        all_years.add(y)
    elif isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict):
                for y in src.get("years", []):
                    if isinstance(y, int):
                        all_years.add(y)

    if not all_years:
        return []

    return [
        {
            "start": f"{min(all_years)}-01-01",
            "end": f"{max(all_years)}-12-31",
            "type": "Collected",
            "description": "Data coverage period",
        }
    ]


def build_zenodo_metadata(
    topic_dir: Path,
    config: dict,
    measure_info: dict | None = None,
    *,
    creators: list[dict] | None = None,
    license_id: str = "cc-by-4.0",
) -> dict:
    """Build a Zenodo metadata dict from pipeline config and measure info."""
    pipeline_name = config.get("name", topic_dir.name)
    version = config.get("version", "0.1.0")
    title = f"{_prettify_name(pipeline_name)} (v{version})"

    metadata = {
        "upload_type": "dataset",
        "title": title,
        "description": _build_description(config, measure_info),
        "creators": creators or DEFAULT_CREATORS,
        "publication_date": date.today().isoformat(),
        "access_right": "open",
        "license": license_id,
        "version": version,
        "keywords": _extract_keywords(config, measure_info, topic_dir),
        "related_identifiers": [
            {
                "identifier": "https://github.com/dads2busy/sdc",
                "relation": "isSupplementedBy",
                "scheme": "url",
            }
        ],
    }

    dates = _extract_dates(config)
    if dates:
        metadata["dates"] = dates

    return metadata


# ---------------------------------------------------------------------------
# YAML editing (preserves formatting)
# ---------------------------------------------------------------------------

_ZENODO_RE = re.compile(r"^zenodo_deposit_id:\s+")
_VERSION_RE = re.compile(r"^version:\s+")


def _update_yaml_zenodo_id(yaml_path: Path, deposit_id: int) -> None:
    """Insert or update zenodo_deposit_id in pipeline.yaml."""
    text = yaml_path.read_text()
    lines = text.split("\n")

    for i, line in enumerate(lines):
        if _ZENODO_RE.match(line):
            lines[i] = f"zenodo_deposit_id: {deposit_id}"
            yaml_path.write_text("\n".join(lines))
            return

    for i, line in enumerate(lines):
        if _VERSION_RE.match(line):
            lines.insert(i + 1, f"zenodo_deposit_id: {deposit_id}")
            yaml_path.write_text("\n".join(lines))
            return

    raise ValueError(f"Could not find 'version:' line in {yaml_path}")


# ---------------------------------------------------------------------------
# Upload orchestrator
# ---------------------------------------------------------------------------


def upload_to_zenodo(
    topic_dir: str | Path,
    *,
    publish: bool = False,
    dry_run: bool = False,
    sandbox: bool = False,
    creators: list[dict] | None = None,
    license_id: str = "cc-by-4.0",
    file_patterns: list[str] | None = None,
) -> ZenodoResult | None:
    """Upload a pipeline's distribution files to Zenodo.

    Parameters
    ----------
    topic_dir : path to the pipeline topic directory
    publish : if True, publish the deposit (mints DOI, irreversible)
    dry_run : show what would be uploaded without uploading
    sandbox : use sandbox.zenodo.org for testing
    creators : override default creators
    license_id : SPDX license identifier (default: cc-by-4.0)
    file_patterns : glob patterns for files to upload (default: ["*.csv.xz"])
    """
    topic_dir = Path(topic_dir).resolve()
    yaml_path = topic_dir / "pipeline.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No pipeline.yaml in {topic_dir}")

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    pipeline_name = config.get("name", topic_dir.name)
    version = config.get("version", "0.1.0")
    existing_deposit_id = config.get("zenodo_deposit_id")

    # Resolve distribution directory
    dist_dir = topic_dir / config.get("output", {}).get("path", "data/distribution")
    if not dist_dir.exists():
        log.warning("Distribution directory not found: %s", dist_dir)
        return None

    # Load measure_info.json
    mi_path = dist_dir / "measure_info.json"
    measure_info = None
    if mi_path.exists():
        with open(mi_path) as f:
            measure_info = json.load(f)

    # Discover files to upload
    patterns = file_patterns or ["*.csv.xz"]
    files_to_upload: list[Path] = []
    for pat in patterns:
        files_to_upload.extend(sorted(dist_dir.glob(pat)))
    if mi_path.exists():
        files_to_upload.append(mi_path)

    if not files_to_upload:
        log.warning("No files found to upload in %s", dist_dir)
        return None

    # Build metadata
    metadata = build_zenodo_metadata(
        topic_dir, config,
        measure_info=measure_info,
        creators=creators,
        license_id=license_id,
    )

    log.info("Pipeline:  %s v%s", pipeline_name, version)
    log.info("Files:     %d", len(files_to_upload))
    for fp in files_to_upload:
        size_mb = fp.stat().st_size / (1024 * 1024)
        log.info("  %s (%.1f MB)", fp.name, size_mb)
    log.info("Title:     %s", metadata["title"])

    if dry_run:
        log.info("[dry-run] Would upload to %s",
                 "sandbox.zenodo.org" if sandbox else "zenodo.org")
        return ZenodoResult(
            pipeline_name=pipeline_name,
            deposit_id=existing_deposit_id or 0,
            version=version,
            files_uploaded=[fp.name for fp in files_to_upload],
        )

    # Create or update deposit
    client = ZenodoClient(sandbox=sandbox)
    is_new_version = False

    if existing_deposit_id:
        log.info("Creating new version of deposit %d", existing_deposit_id)
        deposit = client.new_version(existing_deposit_id)
        is_new_version = True

        # Delete inherited files from previous version
        for f in deposit.get("files", []):
            client.delete_file(deposit["id"], f["id"])
            log.info("  Removed inherited file: %s", f["filename"])
    else:
        log.info("Creating new deposit")
        deposit = client.create_deposit()

    deposit_id = deposit["id"]
    bucket_url = deposit["links"]["bucket"]

    # Upload files
    uploaded_names = []
    for fp in files_to_upload:
        log.info("Uploading %s", fp.name)
        client.upload_file(bucket_url, fp)
        uploaded_names.append(fp.name)

    # Set metadata
    client.update_metadata(deposit_id, metadata)
    log.info("Metadata updated")

    doi = None
    if publish:
        result = client.publish(deposit_id)
        doi = result.get("doi")
        log.info("Published — DOI: %s", doi)

    deposit_url = f"{client.web_base}/deposit/{deposit_id}"
    log.info("Deposit URL: %s", deposit_url)

    # Save deposit ID to pipeline.yaml on first upload
    if not existing_deposit_id:
        _update_yaml_zenodo_id(yaml_path, deposit_id)
        log.info("Saved zenodo_deposit_id=%d to pipeline.yaml", deposit_id)

    return ZenodoResult(
        pipeline_name=pipeline_name,
        deposit_id=deposit_id,
        version=version,
        doi=doi,
        deposit_url=deposit_url,
        files_uploaded=uploaded_names,
        is_new_version=is_new_version,
        published=publish,
    )
