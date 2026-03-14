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
import lzma
import os
import re
import tempfile
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
    {"name": "Schroeder, Aaron", "affiliation": "University of Virginia"},
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
            timeout=600,
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


def _md_overview(config: dict) -> str:
    """Generate Overview section in Markdown."""
    pipeline_name = _prettify_name(config.get("name", ""))
    desc = config.get("description", "").strip()
    if desc and not desc.endswith((".", "!", "?")):
        desc += "."
    return (
        f"{desc} This dataset is produced by the "
        f"**Social Data Commons** at the University of Virginia "
        f"as part of the **{pipeline_name}** data pipeline."
    )


def _md_provenance(measure_info: dict | None) -> str:
    """Generate Provenance section in Markdown."""
    if not measure_info:
        return ""
    seen: set[str] = set()
    paragraphs: list[str] = []
    for info in measure_info.values():
        if isinstance(info, dict):
            prov = info.get("provenance", "").strip()
            if prov and prov not in seen:
                seen.add(prov)
                paragraphs.append(prov)
    return "\n\n".join(paragraphs)


def _md_coverage(config: dict) -> str:
    """Generate Coverage section in Markdown."""
    years, geos, coverage_areas = _extract_coverage(config)
    lines: list[str] = []
    if years:
        temporal_label = config.get("temporal_label", "ACS 5-year estimates")
        lines.append(
            f"- **Temporal coverage:** {min(years)}\u2013{max(years)} "
            f"({temporal_label})"
        )
    if geos:
        geo_labels = [g.replace("_", " ").title() for g in sorted(geos)]
        lines.append(f"- **Geographic levels:** {', '.join(geo_labels)}")
    if coverage_areas:
        area_labels = {
            "va": "Virginia (statewide)",
            "ncr": "National Capital Region (DC metro)",
            "us": "United States (national)",
        }
        normalized = set()
        for a in coverage_areas:
            base = a.lower().split("_")[0]
            normalized.add(base)
        labels = [area_labels.get(a, a.upper()) for a in sorted(normalized)]
        lines.append(f"- **Coverage areas:** {', '.join(labels)}")
    return "\n".join(lines)


def _md_methodology(measure_info: dict | None) -> str:
    """Generate Methodology section in Markdown."""
    if not measure_info:
        return ""
    measures = {k: v for k, v in measure_info.items() if not k.startswith("_")}
    seen: set[str] = set()
    paragraphs: list[str] = []
    for info in measures.values():
        long_desc = info.get("long_description", "").strip()
        if not long_desc:
            continue
        rest = long_desc.split(". ", 1)[1] if ". " in long_desc else long_desc
        if rest not in seen:
            seen.add(rest)
            paragraphs.append(long_desc)
    return "\n\n".join(paragraphs)


def _md_source_tables(measure_info: dict | None) -> str:
    """Generate Source Tables section in Markdown."""
    if not measure_info:
        return ""
    measures = {k: v for k, v in measure_info.items() if not k.startswith("_")}
    seen: set[str] = set()
    lines: list[str] = []
    for info in measures.values():
        for src in info.get("sources", []):
            loc = src.get("location", "")
            if loc and loc not in seen:
                seen.add(loc)
                loc_url = src.get("location_url", "")
                if loc_url:
                    lines.append(f"- [{loc}]({loc_url})")
                else:
                    lines.append(f"- {loc}")
    return "\n".join(lines)


def _md_variables(config: dict) -> str:
    """Generate Variables section in Markdown."""
    sources = config.get("sources", {})
    all_vars: dict[str, str] = {}
    if isinstance(sources, dict):
        for src in sources.values():
            if isinstance(src, dict):
                for var_name, var_id in src.get("variables", {}).items():
                    all_vars[var_name] = var_id
    if not all_vars:
        return ""
    lines: list[str] = []
    for var_name, var_id in all_vars.items():
        label = var_name.replace("_", " ").title()
        lines.append(f"- **{var_id}**: {label}")
    return "\n".join(lines)


def _md_measures(measure_info: dict | None) -> str:
    """Generate Measures section in Markdown."""
    if not measure_info:
        return ""
    measures = {k: v for k, v in measure_info.items() if not k.startswith("_")}
    if not measures:
        return ""

    lines: list[str] = []

    # Naming convention notes
    has_geo20 = any("_geo20" in k for k in measures)
    has_geo10 = any("_geo10" in k for k in measures)
    has_parcels = any("_parcels" in k for k in measures)
    has_direct = any("_direct" in k for k in measures)

    notes: list[str] = []
    if has_geo20 or has_geo10:
        note = "Measures containing `_geo20` are computed using 2020 Census geographic boundaries"
        if has_geo10:
            note += ", while those containing `_geo10` use 2010 Census geographic boundaries"
        note += "."
        notes.append(note)
    if has_parcels or has_direct:
        notes.append(
            "Measures containing `_parcels` use parcel-based redistribution "
            "(block group values are distributed to individual living units, "
            "then aggregated to target regions). Measures containing `_direct` "
            "use direct spatial overlap (block group values are "
            "aggregated/disaggregated to target regions based on proportion "
            "of overlap)."
        )
    if notes:
        lines.append(f"*Note on naming conventions: {' '.join(notes)}*")
        lines.append("")

    for name, info in list(measures.items())[:30]:
        long_name = info.get("long_name", name)
        short_desc = info.get("short_description", "")
        agg = info.get("aggregation_method", "") or info.get("type", "")
        unit = info.get("unit", "")

        meta_parts = []
        if agg:
            meta_parts.append(agg)
        if unit:
            meta_parts.append(f"unit: {unit}")
        meta_str = f" ({', '.join(meta_parts)})" if meta_parts else ""

        lines.append(f"- **{name}**: {long_name}{meta_str}")
        if short_desc:
            lines.append(f"  {short_desc}")

    if len(measures) > 30:
        lines.append(f"- \u2026 and {len(measures) - 30} additional measures")

    return "\n".join(lines)


def _md_data_sources(measure_info: dict | None) -> str:
    """Generate Data Sources section in Markdown."""
    if not measure_info:
        return ""
    measures = {k: v for k, v in measure_info.items() if not k.startswith("_")}
    seen: set[str] = set()
    lines: list[str] = []
    for info in measures.values():
        for src in info.get("sources", []):
            src_name = src.get("name", "")
            if src_name and src_name not in seen:
                seen.add(src_name)
                url = src.get("url", "")
                accessed = src.get("date_accessed", "")
                label = src_name
                if accessed:
                    label += f" (accessed {accessed})"
                if url:
                    lines.append(f"- [{label}]({url})")
                else:
                    lines.append(f"- {label}")
    return "\n".join(lines)


_FILE_FORMAT_MD = (
    "Data files are provided as CSVs (`.csv`) "
    "with the following columns: `geoid`, `region_type`, `region_name`, "
    "`year`, `measure`, `value`, `moe` (margin of error, where available). "
    "Larger files are provided as xz-compressed CSVs (`.csv.xz`)."
)


def _md_to_html(md: str) -> str:
    """Convert a Markdown description to HTML for Zenodo.

    Handles the subset of Markdown used in our descriptions:
    headers, bold, code, italic, links, lists, and paragraphs.
    """
    lines = md.split("\n")
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Blank line: close list if open
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        # Header
        if stripped.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            title = stripped[3:].strip()
            html_parts.append(f"<h3>{title}</h3>")
            continue

        # List item
        if stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item = stripped[2:]
            item = _inline_md_to_html(item)
            html_parts.append(f"<li>{item}</li>")
            continue

        # Indented continuation of list item (e.g. "  short description")
        if in_list and line.startswith("  ") and not stripped.startswith("- "):
            # Append to previous <li> as a sub-line
            text = _inline_md_to_html(stripped)
            if html_parts and html_parts[-1].endswith("</li>"):
                html_parts[-1] = html_parts[-1][:-5] + f" {text}</li>"
            continue

        # Regular paragraph
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        text = _inline_md_to_html(stripped)
        html_parts.append(f"<p>{text}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline_md_to_html(text: str) -> str:
    """Convert inline Markdown (bold, code, italic, links) to HTML."""
    # Links: [text](url) → <a href="url">text</a>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold: **text** → <strong>text</strong>
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Code: `text` → <code>text</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Italic: *text* → <em>text</em>
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text


def build_zenodo_description(
    config: dict,
    measure_info: dict | None,
) -> tuple[str, str]:
    """Build a Zenodo description in both Markdown and HTML.

    Returns (markdown, html) tuple. The Markdown is saved to
    docs/zenodo_description.md; the HTML is sent to the Zenodo API.
    """
    measures = {k: v for k, v in (measure_info or {}).items()
                if not k.startswith("_")}
    measure_count = len(measures)

    sections: list[str] = []

    # Overview
    overview = _md_overview(config)
    if overview:
        sections.append(f"## Overview\n{overview}")

    # Provenance
    provenance = _md_provenance(measure_info)
    if provenance:
        sections.append(f"## Provenance\n{provenance}")

    # Coverage
    coverage = _md_coverage(config)
    if coverage:
        sections.append(f"## Coverage\n{coverage}")

    # Methodology
    methodology = _md_methodology(measure_info)
    if methodology:
        sections.append(f"## Methodology\n{methodology}")

    # Source Tables
    source_tables = _md_source_tables(measure_info)
    if source_tables:
        sections.append(f"## Source Tables\n{source_tables}")

    # Variables
    variables = _md_variables(config)
    if variables:
        sections.append(f"## Variables\n{variables}")

    # Measures
    measures_md = _md_measures(measure_info)
    if measures_md:
        sections.append(f"## Measures ({measure_count})\n{measures_md}")

    # Data Sources
    data_sources = _md_data_sources(measure_info)
    if data_sources:
        sections.append(f"## Data Sources\n{data_sources}")

    # File Format
    sections.append(f"## File Format\n{_FILE_FORMAT_MD}")

    markdown = "\n\n".join(sections) + "\n"
    html = _md_to_html(markdown)
    return markdown, html


def _build_description(
    config: dict,
    measure_info: dict | None,
) -> str:
    """Build an HTML description from pipeline metadata."""
    _, html = build_zenodo_description(config, measure_info)
    return html


def _extract_coverage(config: dict) -> tuple[set[int], set[str], set[str]]:
    """Extract years, geographies, and coverage areas from pipeline sources."""
    years: set[int] = set()
    geos: set[str] = set()
    coverage_areas: set[str] = set()

    sources = config.get("sources", {})
    if isinstance(sources, dict):
        for key, src in sources.items():
            if isinstance(src, dict):
                coverage_areas.add(key)
                for y in src.get("years", []):
                    if isinstance(y, int):
                        years.add(y)
                for g in src.get("geographies", []):
                    geos.add(g)
    elif isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict):
                for y in src.get("years", []):
                    if isinstance(y, int):
                        years.add(y)
                for g in src.get("geographies", []):
                    geos.add(g)

    return years, geos, coverage_areas


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
    display_name = config.get("title", _prettify_name(pipeline_name))
    title = f"Social Data Commons: {display_name} (v{version})"

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

    if not files_to_upload:
        log.warning("No files found to upload in %s", dist_dir)
        return None

    # Build metadata (also generates Markdown description for docs/)
    metadata = build_zenodo_metadata(
        topic_dir, config,
        measure_info=measure_info,
        creators=creators,
        license_id=license_id,
    )

    # Save Markdown description to docs/zenodo_description.md
    md_desc, _ = build_zenodo_description(config, measure_info)
    docs_dir = topic_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "zenodo_description.md").write_text(md_desc)
    log.info("Saved description to docs/zenodo_description.md")

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

    # Upload files (decompress .csv.xz to .csv for Zenodo preview)
    uploaded_names = []
    tmp_dir = None
    try:
        for fp in files_to_upload:
            if fp.suffix == ".xz" and fp.name.endswith(".csv.xz"):
                # Decompress to a temp directory for upload
                if tmp_dir is None:
                    tmp_dir = tempfile.mkdtemp(prefix="zenodo_")
                csv_name = fp.name.removesuffix(".xz")
                csv_path = Path(tmp_dir) / csv_name
                log.info("Decompressing %s → %s", fp.name, csv_name)
                csv_path.write_bytes(lzma.decompress(fp.read_bytes()))
                log.info("Uploading %s", csv_name)
                client.upload_file(bucket_url, csv_path)
                uploaded_names.append(csv_name)
            else:
                log.info("Uploading %s", fp.name)
                client.upload_file(bucket_url, fp)
                uploaded_names.append(fp.name)
    finally:
        # Clean up temp files
        if tmp_dir is not None:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

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
