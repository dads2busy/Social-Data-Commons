"""Dataset versioning for SDC pipelines.

Tracks per-pipeline versions using semantic versioning. Manifests record
the dimensions and file checksums of the distribution output so that
version bumps can be auto-detected:

  - Major: schema change, measures/years/regions removed
  - Minor: new measures/years/regions added
  - Patch: same dimensions, only values changed

Usage::

    from sdc_core.versioning import update_version

    result = update_version("demographics/Gender")
    print(result.new_version)   # "1.1.0"
    print(result.bump.level)    # "minor"
    print(result.bump.reasons)  # ["New years added: {2024}"]
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
import yaml

from sdc_core.log import get_logger

log = get_logger("versioning")

MANIFEST_FILENAME = "manifest.json"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    """Checksum and size of a single distribution file."""

    sha256: str
    size_bytes: int

    def to_dict(self) -> dict:
        return {"sha256": self.sha256, "size_bytes": self.size_bytes}

    @classmethod
    def from_dict(cls, d: dict) -> FileInfo:
        return cls(sha256=d["sha256"], size_bytes=d["size_bytes"])


@dataclass
class Manifest:
    """Snapshot of a pipeline's distribution output."""

    version: str
    generated: str  # ISO-8601 UTC
    schema: list[str]
    measures: list[str]
    years: list[int]
    regions: list[str]  # 2-digit state FIPS prefixes
    row_count: int
    files: dict[str, FileInfo] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "generated": self.generated,
            "schema": self.schema,
            "measures": sorted(self.measures),
            "years": sorted(self.years),
            "regions": sorted(self.regions),
            "row_count": self.row_count,
            "files": {k: v.to_dict() for k, v in sorted(self.files.items())},
        }

    @classmethod
    def from_dict(cls, d: dict) -> Manifest:
        files = {k: FileInfo.from_dict(v) for k, v in d.get("files", {}).items()}
        return cls(
            version=d["version"],
            generated=d["generated"],
            schema=d["schema"],
            measures=d["measures"],
            years=d["years"],
            regions=d["regions"],
            row_count=d["row_count"],
            files=files,
        )


@dataclass
class BumpResult:
    """Result of comparing two manifests."""

    level: Literal["major", "minor", "patch"]
    reasons: list[str] = field(default_factory=list)


@dataclass
class VersionResult:
    """Result of a version update operation."""

    pipeline_name: str
    old_version: str | None  # None if first run
    new_version: str
    bump: BumpResult | None  # None if first run
    manifest: Manifest
    tag: str  # suggested git tag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def pipeline_slug(name: str) -> str:
    """Convert a pipeline name to a git-tag-safe slug.

    >>> pipeline_slug("health_care_cost")
    'health-care-cost'
    >>> pipeline_slug("gender_demographics")
    'gender-demographics'
    """
    slug = name.strip().lower()
    slug = re.sub(r"[_\W]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _prettify_name(name: str) -> str:
    """Convert a pipeline name to a human-readable title.

    >>> _prettify_name("age_demographics")
    'Age Demographics'
    >>> _prettify_name("segregation")
    'Segregation'
    """
    return name.replace("_", " ").title()


def bump_version(version: str, level: Literal["major", "minor", "patch"]) -> str:
    """Apply a semver bump.

    >>> bump_version("1.2.3", "major")
    '2.0.0'
    >>> bump_version("1.2.3", "minor")
    '1.3.0'
    >>> bump_version("1.2.3", "patch")
    '1.2.4'
    """
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semver: {version!r}")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if level == "major":
        return f"{major + 1}.0.0"
    elif level == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def load_manifest(dist_dir: str | Path) -> Manifest | None:
    """Load manifest.json from a distribution directory. Returns None if absent."""
    path = Path(dist_dir) / MANIFEST_FILENAME
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    return Manifest.from_dict(data)


def save_manifest(manifest: Manifest, dist_dir: str | Path) -> Path:
    """Write manifest.json to a distribution directory."""
    path = Path(dist_dir) / MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
        f.write("\n")
    return path


def generate_manifest(
    dist_dir: str | Path,
    version: str,
    *,
    file_patterns: list[str] | None = None,
) -> Manifest:
    """Build a Manifest by scanning distribution files.

    Parameters
    ----------
    dist_dir : path to the data/distribution/ directory
    version : version string to embed
    file_patterns : glob patterns for files to include (default: ``["*.csv.xz"]``)
    """
    dist_dir = Path(dist_dir)
    patterns = file_patterns or ["*.csv.xz"]

    # Discover files
    data_files: list[Path] = []
    for pattern in patterns:
        data_files.extend(dist_dir.glob(pattern))
    data_files = sorted(set(data_files))

    if not data_files:
        raise FileNotFoundError(
            f"No distribution files found in {dist_dir} matching {patterns}"
        )

    # Read files and compute checksums
    frames: list[pd.DataFrame] = []
    file_infos: dict[str, FileInfo] = {}

    for fp in data_files:
        file_infos[fp.name] = FileInfo(
            sha256=_sha256(fp),
            size_bytes=fp.stat().st_size,
        )
        try:
            df = pd.read_csv(fp, dtype={"geoid": str})
            frames.append(df)
        except Exception as e:
            log.warning("Could not read %s for manifest: %s", fp, e)

    if not frames:
        raise ValueError(f"No readable data files in {dist_dir}")

    combined = pd.concat(frames, ignore_index=True)

    # Extract dimensions
    schema = list(combined.columns)

    measures = (
        sorted(combined["measure"].dropna().unique().tolist())
        if "measure" in combined.columns
        else []
    )
    years = (
        sorted(int(y) for y in combined["year"].dropna().unique())
        if "year" in combined.columns
        else []
    )

    if "geoid" in combined.columns:
        geoids = combined["geoid"].dropna().astype(str)
        regions = sorted(geoids.str[:2].unique().tolist())
    else:
        regions = []

    return Manifest(
        version=version,
        generated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        schema=schema,
        measures=measures,
        years=years,
        regions=regions,
        row_count=len(combined),
        files=file_infos,
    )


# ---------------------------------------------------------------------------
# Bump detection
# ---------------------------------------------------------------------------

def detect_bump(old: Manifest, new: Manifest) -> BumpResult:
    """Compare two manifests and determine the appropriate version bump.

    Rules (all checked; highest severity wins):

    Major: schema columns changed, measures/years/regions removed
    Minor: new measures/years/regions added
    Patch: same dimensions, values changed
    """
    reasons: list[str] = []
    level: Literal["major", "minor", "patch"] = "patch"

    # --- Major checks ---
    if old.schema != new.schema:
        added = set(new.schema) - set(old.schema)
        removed = set(old.schema) - set(new.schema)
        parts = []
        if added:
            parts.append(f"columns added: {added}")
        if removed:
            parts.append(f"columns removed: {removed}")
        reasons.append(f"Schema change ({', '.join(parts)})")
        level = "major"

    removed_measures = set(old.measures) - set(new.measures)
    if removed_measures:
        reasons.append(f"Measures removed: {removed_measures}")
        level = "major"

    removed_years = set(old.years) - set(new.years)
    if removed_years:
        reasons.append(f"Years removed: {removed_years}")
        level = "major"

    removed_regions = set(old.regions) - set(new.regions)
    if removed_regions:
        reasons.append(f"Regions removed: {removed_regions}")
        level = "major"

    # --- Minor checks ---
    added_measures = set(new.measures) - set(old.measures)
    if added_measures:
        reasons.append(f"New measures added: {added_measures}")
        if level != "major":
            level = "minor"

    added_years = set(new.years) - set(old.years)
    if added_years:
        reasons.append(f"New years added: {added_years}")
        if level != "major":
            level = "minor"

    added_regions = set(new.regions) - set(old.regions)
    if added_regions:
        reasons.append(f"New regions added: {added_regions}")
        if level != "major":
            level = "minor"

    # --- Patch (implicit) ---
    if not reasons:
        old_checksums = {k: v.sha256 for k, v in old.files.items()}
        new_checksums = {k: v.sha256 for k, v in new.files.items()}
        if old_checksums != new_checksums:
            reasons.append("File contents changed (same dimensions)")
        elif old.row_count != new.row_count:
            reasons.append(f"Row count changed: {old.row_count} -> {new.row_count}")
        else:
            reasons.append("No changes detected")

    return BumpResult(level=level, reasons=reasons)


# ---------------------------------------------------------------------------
# YAML version editing (preserves formatting)
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^version:\s+")
_NAME_RE = re.compile(r"^name:\s+")


def _update_yaml_version(yaml_path: Path, new_version: str) -> None:
    """Insert or update the version field in pipeline.yaml.

    Uses line-level editing to preserve comments and formatting.
    """
    text = yaml_path.read_text()
    lines = text.split("\n")

    # Try to replace existing version line
    for i, line in enumerate(lines):
        if _VERSION_RE.match(line):
            lines[i] = f'version: "{new_version}"'
            yaml_path.write_text("\n".join(lines))
            return

    # No version line — insert after name line
    for i, line in enumerate(lines):
        if _NAME_RE.match(line):
            lines.insert(i + 1, f'version: "{new_version}"')
            yaml_path.write_text("\n".join(lines))
            return

    raise ValueError(f"Could not find 'name:' line in {yaml_path}")


# ---------------------------------------------------------------------------
# Version update orchestrator
# ---------------------------------------------------------------------------

def update_version(
    topic_dir: str | Path,
    *,
    force_level: Literal["major", "minor", "patch"] | None = None,
    dry_run: bool = False,
    skip_if_unchanged: bool = True,
    auto_tag: bool = True,
    auto_release: bool = True,
) -> VersionResult | None:
    """Generate a manifest, detect changes, bump version, save, and tag.

    Parameters
    ----------
    topic_dir : path to the pipeline topic directory
    force_level : override auto-detected bump level
    dry_run : compute everything but don't write files
    skip_if_unchanged : skip bump if all file checksums match (default True)
    auto_tag : create an annotated git tag after bumping (default True)
    auto_release : create a GitHub release after tagging (default True).
        Requires ``gh`` CLI. Silently skipped if unavailable.

    Returns
    -------
    VersionResult, or None if skip_if_unchanged and nothing changed.
    """
    topic_dir = Path(topic_dir).resolve()
    yaml_path = topic_dir / "pipeline.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No pipeline.yaml in {topic_dir}")

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    pipeline_name = config["name"]
    current_version = config.get("version", "0.1.0")
    dist_dir = topic_dir / config.get("output", {}).get("path", "data/distribution")

    old_manifest = load_manifest(dist_dir)
    new_manifest = generate_manifest(dist_dir, version=current_version)

    if old_manifest is None:
        # First run
        bump = None
        new_version = current_version
        log.info(
            "No previous manifest for '%s'; initializing at v%s",
            pipeline_name, new_version,
        )
    else:
        bump = detect_bump(old_manifest, new_manifest)

        # Skip if unchanged
        if skip_if_unchanged and not force_level:
            old_checksums = {k: v.sha256 for k, v in old_manifest.files.items()}
            new_checksums = {k: v.sha256 for k, v in new_manifest.files.items()}
            if old_checksums == new_checksums:
                log.info("'%s': no changes detected, skipping bump", pipeline_name)
                return None

        effective_level = force_level or bump.level
        if force_level and force_level != bump.level:
            log.info(
                "Overriding auto-detected %s bump with forced %s",
                bump.level, force_level,
            )
            bump = BumpResult(level=effective_level, reasons=bump.reasons)

        new_version = bump_version(current_version, effective_level)
        log.info(
            "'%s': %s bump v%s -> v%s (%s)",
            pipeline_name, effective_level, current_version, new_version,
            "; ".join(bump.reasons),
        )

    new_manifest.version = new_version

    slug = pipeline_slug(pipeline_name)
    tag = f"{slug}/v{new_version}"

    result = VersionResult(
        pipeline_name=pipeline_name,
        old_version=current_version if old_manifest else None,
        new_version=new_version,
        bump=bump,
        manifest=new_manifest,
        tag=tag,
    )

    if dry_run:
        log.info("Dry run: skipping file writes")
        return result

    save_manifest(new_manifest, dist_dir)
    log.info("Wrote manifest to %s", dist_dir / MANIFEST_FILENAME)

    _update_yaml_version(yaml_path, new_version)
    log.info("Updated %s to version %s", yaml_path, new_version)

    if auto_tag:
        try:
            create_git_tag(tag)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            log.warning("Could not create git tag '%s': %s", tag, e)

    if auto_release and auto_tag:
        try:
            create_github_release(result, dist_dir)
        except Exception as e:
            log.warning("Could not create GitHub release for '%s': %s", tag, e)

    return result


# ---------------------------------------------------------------------------
# Git tag
# ---------------------------------------------------------------------------

def create_git_tag(
    tag: str,
    message: str | None = None,
    *,
    repo_dir: str | Path | None = None,
) -> str:
    """Create an annotated git tag.

    Returns the created tag name.
    """
    msg = message or f"Release {tag}"
    cmd = ["git", "tag", "-a", tag, "-m", msg]
    kwargs: dict = {}
    if repo_dir:
        kwargs["cwd"] = str(repo_dir)
    subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)
    log.info("Created git tag: %s", tag)

    # Push the tag so gh release create can find it
    push_cmd = ["git", "push", "origin", tag]
    try:
        subprocess.run(push_cmd, check=True, capture_output=True, text=True, **kwargs)
        log.info("Pushed tag: %s", tag)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.warning("Could not push tag '%s': %s", tag, e)

    return tag


def create_github_release(
    result: VersionResult,
    dist_dir: str | Path,
    *,
    repo_dir: str | Path | None = None,
    file_patterns: list[str] | None = None,
) -> str | None:
    """Create a GitHub release with pipeline data files as assets.

    Uses ``gh release create``. Returns the tag name on success,
    or ``None`` if ``gh`` is not available or the release fails.
    """
    title = f"{_prettify_name(result.pipeline_name)} v{result.new_version}"

    # Build release body
    body_parts: list[str] = []
    if result.bump:
        body_parts.append(f"**Bump level:** {result.bump.level}")
        body_parts.append("")
        body_parts.append("**Changes:**")
        for reason in result.bump.reasons:
            body_parts.append(f"- {reason}")
    else:
        body_parts.append("**Initial release**")

    m = result.manifest
    body_parts.append("")
    body_parts.append("**Manifest summary:**")
    body_parts.append(f"- Measures: {len(m.measures)}")
    if m.measures:
        shown = m.measures[:10]
        body_parts.append(f"  - {', '.join(shown)}")
        if len(m.measures) > 10:
            body_parts.append(f"  - ... and {len(m.measures) - 10} more")
    if m.years:
        body_parts.append(f"- Years: {min(m.years)}\u2013{max(m.years)}")
    if m.regions:
        body_parts.append(f"- Regions (state FIPS): {', '.join(m.regions)}")
    body_parts.append(f"- Row count: {m.row_count:,}")
    body_parts.append(f"- Files: {len(m.files)}")

    body = "\n".join(body_parts)

    # Discover asset files
    dist_path = Path(dist_dir)
    patterns = file_patterns or ["*.csv.xz"]
    assets: list[Path] = []
    for pattern in patterns:
        assets.extend(dist_path.glob(pattern))
    assets = sorted(set(assets))

    cmd: list[str] = [
        "gh", "release", "create", result.tag,
        "--title", title,
        "--notes", body,
    ]
    for asset in assets:
        cmd.append(str(asset))

    kwargs: dict = {}
    if repo_dir:
        kwargs["cwd"] = str(repo_dir)

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)
    except FileNotFoundError:
        log.warning(
            "gh CLI not found — skipping GitHub release for '%s'", result.tag,
        )
        return None
    except subprocess.CalledProcessError as e:
        log.warning(
            "Failed to create GitHub release '%s': %s\nstderr: %s",
            result.tag, e, e.stderr,
        )
        return None

    log.info("Created GitHub release: %s (%d assets)", title, len(assets))
    return result.tag


__all__ = [
    "BumpResult",
    "FileInfo",
    "Manifest",
    "VersionResult",
    "bump_version",
    "create_git_tag",
    "create_github_release",
    "detect_bump",
    "generate_manifest",
    "load_manifest",
    "pipeline_slug",
    "save_manifest",
    "update_version",
]
