"""CLI entry point for SDC pipelines.

Usage:
    sdc run ingest           # run the ingest step
    sdc run prepare          # run the prepare step
    sdc run all              # run ingest then prepare
    sdc run all --year 2022  # override year
    sdc info                 # show pipeline config
    sdc sources check        # upstream freshness report (exit 1 when action is needed)
    sdc sources audit        # pipelines missing from meta/source_checks.yaml
    sdc sources sync-latest  # refresh `latest` years from pipeline.yaml
"""

from __future__ import annotations

import importlib
import pathlib
import sys

import click

from sdc_core.pipeline import load_pipeline


@click.group()
def main():
    """SDC dataset pipeline runner."""
    pass


@main.command()
@click.argument("step", type=click.Choice(["ingest", "prepare", "all"]))
@click.option("--config", "-c", default="pipeline.yaml", help="Path to pipeline.yaml")
@click.option("--year", "-y", type=int, multiple=True, help="Override year(s)")
@click.option("--state", "-s", multiple=True, help="Override state(s)")
def run(step: str, config: str, year: tuple[int, ...], state: tuple[str, ...]):
    """Run a pipeline step (ingest, prepare, or all)."""
    pipeline = load_pipeline(config)
    click.echo(f"Pipeline: {pipeline.name} v{pipeline.version}")

    # Apply CLI overrides to sources
    if year:
        for source in pipeline.sources:
            source.years = list(year)
    if state:
        for source in pipeline.sources:
            source.states = list(state)

    # Import and run the local code/ modules
    code_dir = pathlib.Path("code")
    if code_dir.is_dir():
        sys.path.insert(0, str(code_dir))

    steps = ["ingest", "prepare"] if step == "all" else [step]

    for s in steps:
        click.echo(f"\n--- Running: {s} ---")
        try:
            mod = importlib.import_module(s)
        except ModuleNotFoundError:
            click.echo(f"No code/{s}.py found, skipping.")
            continue

        if hasattr(mod, "run"):
            mod.run(pipeline)
        elif hasattr(mod, s):
            getattr(mod, s)(pipeline)
        else:
            click.echo(f"Warning: code/{s}.py has no run() or {s}() function.")


@main.command()
@click.option("--config", "-c", default="pipeline.yaml", help="Path to pipeline.yaml")
def info(config: str):
    """Display pipeline configuration."""
    pipeline = load_pipeline(config)
    click.echo(f"Name:        {pipeline.name}")
    click.echo(f"Version:     {pipeline.version}")
    click.echo(f"Description: {pipeline.description}")
    click.echo(f"Sources:     {len(pipeline.sources)}")
    for i, src in enumerate(pipeline.sources):
        click.echo(f"  [{i}] type={src.type} vars={len(src.variables)} "
                    f"years={src.years} states={src.states} geo={src.geography}")
    click.echo(f"Measures:    {len(pipeline.measures)}")
    for m in pipeline.measures:
        click.echo(f"  - {m.name} ({m.aggregation})")
    click.echo(f"Output:      {pipeline.output.geographies} ({pipeline.output.format})")


# ---------------------------------------------------------------------------
# sdc version
# ---------------------------------------------------------------------------

@main.group()
def version():
    """Dataset versioning commands."""
    pass


@version.command("bump")
@click.argument("topic_dir", type=click.Path(exists=True))
@click.option(
    "--force", type=click.Choice(["major", "minor", "patch"]),
    help="Override auto-detected bump level",
)
@click.option("--dry-run", is_flag=True, help="Show what would change without writing")
@click.option("--no-tag", is_flag=True, help="Skip creating a git tag")
@click.option("--no-release", is_flag=True, help="Skip creating a GitHub release")
def version_bump(topic_dir: str, force: str | None, dry_run: bool, no_tag: bool, no_release: bool):
    """Bump the version of a pipeline dataset.

    TOPIC_DIR is the path to the pipeline directory (e.g., demographics/Gender).
    Automatically creates an annotated git tag and GitHub release unless
    --no-tag or --no-release is passed.
    """
    from sdc_core.versioning import update_version

    result = update_version(
        topic_dir,
        force_level=force,
        dry_run=dry_run,
        auto_tag=not no_tag,
        auto_release=not no_release,
    )

    if result is None:
        click.echo("No changes detected — version unchanged.")
        return

    click.echo(f"Pipeline: {result.pipeline_name}")
    if result.old_version:
        click.echo(f"Version:  {result.old_version} -> {result.new_version}")
    else:
        click.echo(f"Version:  (new) -> {result.new_version}")

    if result.bump:
        click.echo(f"Bump:     {result.bump.level}")
        for reason in result.bump.reasons:
            click.echo(f"  - {reason}")

    click.echo(f"Tag:      {result.tag}")


@version.command("manifest")
@click.argument("topic_dir", type=click.Path(exists=True))
def version_manifest(topic_dir: str):
    """Show the current manifest for a pipeline."""
    import json as _json

    from sdc_core.versioning import load_manifest

    yaml_path = pathlib.Path(topic_dir) / "pipeline.yaml"
    if not yaml_path.exists():
        click.echo(f"Error: No pipeline.yaml found in {topic_dir}", err=True)
        raise SystemExit(1)

    import yaml as _yaml

    with open(yaml_path) as f:
        config = _yaml.safe_load(f)
    dist_dir = (
        pathlib.Path(topic_dir)
        / config.get("output", {}).get("path", "data/distribution")
    )

    manifest = load_manifest(dist_dir)
    if manifest is None:
        click.echo("No manifest found. Run 'sdc version bump' first.")
        raise SystemExit(1)

    click.echo(_json.dumps(manifest.to_dict(), indent=2))


@version.command("status")
@click.argument("topic_dir", type=click.Path(exists=True), required=False)
def version_status(topic_dir: str | None):
    """Show version status of one or all pipelines."""
    import yaml as _yaml

    from sdc_core.versioning import load_manifest

    if topic_dir:
        dirs = [pathlib.Path(topic_dir)]
    else:
        dirs = sorted(
            p.parent
            for p in pathlib.Path(".").rglob("pipeline.yaml")
            if ".claude" not in str(p) and "worktree" not in str(p)
        )

    for d in dirs:
        yaml_path = d / "pipeline.yaml"
        if not yaml_path.exists():
            continue
        with open(yaml_path) as f:
            config = _yaml.safe_load(f)
        name = config.get("name", d.name)
        ver = config.get("version", "-")
        dist_dir = d / config.get("output", {}).get("path", "data/distribution")
        manifest = load_manifest(dist_dir)
        has_manifest = "yes" if manifest else "no"
        click.echo(f"{name:<40s} v{ver:<10s} manifest={has_manifest}")


# ---------------------------------------------------------------------------
# sdc zenodo
# ---------------------------------------------------------------------------


@main.group()
def zenodo():
    """Zenodo dataset archiving commands."""
    pass


@zenodo.command("upload")
@click.argument("topic_dir", type=click.Path(exists=True))
@click.option("--publish", is_flag=True, help="Publish after upload (mints DOI, irreversible)")
@click.option("--dry-run", is_flag=True, help="Show what would be uploaded without uploading")
@click.option("--sandbox", is_flag=True, help="Use sandbox.zenodo.org for testing")
@click.option("--license", "license_id", default="cc-by-4.0", help="SPDX license identifier")
def zenodo_upload(topic_dir: str, publish: bool, dry_run: bool, sandbox: bool, license_id: str):
    """Upload a pipeline's distribution files to Zenodo.

    TOPIC_DIR is the path to the pipeline directory (e.g., demographics/Gender).
    Creates a new deposit or updates an existing one based on zenodo_deposit_id
    in pipeline.yaml.
    """
    from sdc_core.zenodo import upload_to_zenodo

    result = upload_to_zenodo(
        topic_dir,
        publish=publish,
        dry_run=dry_run,
        sandbox=sandbox,
        license_id=license_id,
    )

    if result is None:
        click.echo("No distribution files found to upload.")
        return

    click.echo(f"Pipeline:   {result.pipeline_name}")
    click.echo(f"Deposit ID: {result.deposit_id}")
    click.echo(f"Version:    {result.version}")
    if result.deposit_url:
        click.echo(f"URL:        {result.deposit_url}")
    if result.doi:
        click.echo(f"DOI:        {result.doi}")
    click.echo(f"Files:      {len(result.files_uploaded)}")
    for f in result.files_uploaded:
        click.echo(f"  - {f}")
    if result.is_new_version:
        click.echo("(Updated existing deposit)")


# ---------------------------------------------------------------------------
# sdc sync
# ---------------------------------------------------------------------------


@main.command()
@click.argument("dashboard", required=False)
@click.option("--no-build", is_flag=True, help="Skip npm run build:data")
@click.option("--dry-run", is_flag=True, help="Show what would be synced without copying")
def sync(dashboard: str | None, no_build: bool, dry_run: bool):
    """Sync pipeline data to a dashboard repo.

    DASHBOARD is the name of the dashboard (e.g., ncr, va).
    If omitted, syncs all dashboards defined in sync.yaml.
    """
    from sdc_core.sync import run_sync

    run_sync(dashboard, dry_run=dry_run, no_build=no_build)


@zenodo.command("status")
@click.argument("topic_dir", type=click.Path(exists=True), required=False)
def zenodo_status(topic_dir: str | None):
    """Show Zenodo deposit status of one or all pipelines."""
    import yaml as _yaml

    if topic_dir:
        dirs = [pathlib.Path(topic_dir)]
    else:
        dirs = sorted(
            p.parent
            for p in pathlib.Path(".").rglob("pipeline.yaml")
            if ".claude" not in str(p) and "worktree" not in str(p)
        )

    for d in dirs:
        yaml_path = d / "pipeline.yaml"
        if not yaml_path.exists():
            continue
        with open(yaml_path) as f:
            config = _yaml.safe_load(f)
        name = config.get("name", d.name)
        ver = config.get("version", "-")
        deposit_id = config.get("zenodo_deposit_id")
        status = f"deposit={deposit_id}" if deposit_id else "not uploaded"
        click.echo(f"{name:<40s} v{ver:<10s} {status}")


# ---------------------------------------------------------------------------
# sdc sources
# ---------------------------------------------------------------------------


@main.group()
def sources():
    """Upstream source freshness checks (registry: meta/source_checks.yaml)."""
    pass


def _load_sources_registry(root: pathlib.Path):
    """Load meta/source_checks.yaml, turning a malformed file into a clean CLI error."""
    from sdc_core.sources.checks.paths import registry_path
    from sdc_core.sources.checks.registry import RegistryError, load_registry

    try:
        return load_registry(registry_path(root))
    except RegistryError as exc:
        raise click.ClickException(f"{registry_path(root)}: {exc}") from exc


@sources.command("check")
@click.option("--source", "source_ids", multiple=True, help="Only this source id (repeatable)")
@click.option("--pipeline", "pipelines", multiple=True, help="Only this pipeline path (repeatable)")
@click.option(
    "--json",
    "json_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Also write the rows to this JSON file",
)
@click.option(
    "--update-state",
    is_flag=True,
    help="Record successful observations as the new baseline in meta/source_checks_state.json",
)
def sources_check(
    source_ids: tuple[str, ...],
    pipelines: tuple[str, ...],
    json_path: str | None,
    update_state: bool,
):
    """Compare upstream vintages/fingerprints against what each pipeline has ingested.

    Exit 0 when every row is current, baseline, or not_tracked; 1 otherwise.
    """
    from sdc_core.sources.checks import run_checks
    from sdc_core.sources.checks.paths import find_repo_root, state_path
    from sdc_core.sources.checks.report import exit_code, render_json, render_table
    from sdc_core.sources.checks.state import load_state, save_state

    root = find_repo_root()
    registry = _load_sources_registry(root)
    unknown_sources = set(source_ids) - {e.id for e in registry.sources}
    if unknown_sources:
        raise click.ClickException(f"unknown source id(s): {', '.join(sorted(unknown_sources))}")
    unknown_pipelines = set(pipelines) - registry.tracked_paths()
    if unknown_pipelines:
        raise click.ClickException(
            f"unknown pipeline path(s): {', '.join(sorted(unknown_pipelines))}"
        )
    state = load_state(state_path(root))
    rows, observed = run_checks(
        registry, state, root, source_filter=set(source_ids), pipeline_filter=set(pipelines)
    )
    click.echo(render_table(rows))
    if json_path:
        pathlib.Path(json_path).write_text(render_json(rows))
    if update_state:
        state.update(observed)
        save_state(state_path(root), state)
        click.echo(f"state updated: {state_path(root)}")
    sys.exit(exit_code(rows))


@sources.command("audit")
def sources_audit():
    """List pipelines missing from the registry and registry paths missing on disk."""
    from sdc_core.sources.checks.paths import find_repo_root
    from sdc_core.sources.checks.registry import audit

    root = find_repo_root()
    registry = _load_sources_registry(root)
    unregistered, missing = audit(registry, root)
    if unregistered:
        click.echo("Pipelines on disk with no registry entry (add under sources: or untracked:):")
        for path in unregistered:
            click.echo(f"  {path}")
    if missing:
        click.echo("Registry paths not found on disk:")
        for path in missing:
            click.echo(f"  {path}")
    if not unregistered and not missing:
        click.echo("registry and pipelines on disk agree")
    sys.exit(1 if unregistered or missing else 0)


@sources.command("sync-latest")
@click.option("--dry-run", is_flag=True, help="Report what would change without writing")
def sources_sync_latest(dry_run: bool):
    """Rewrite each vintage pipeline's `latest` from its pipeline.yaml years."""
    from sdc_core.sources.checks.paths import find_repo_root, registry_path
    from sdc_core.sources.checks.registry import RegistryError, sync_latest

    root = find_repo_root()
    try:
        changes = sync_latest(registry_path(root), root, dry_run=dry_run)
    except RegistryError as exc:
        raise click.ClickException(f"{registry_path(root)}: {exc}") from exc
    verb = "WOULD SET" if dry_run else "SET"
    n_changed = 0
    for sid, path, old, new in changes:
        if new is None:
            click.echo(f"UNRESOLVED  {sid:<24s} {path}  (latest stays {old})")
        elif new != old:
            n_changed += 1
            click.echo(f"{verb:<11s} {sid:<24s} {path}  {old} -> {new}")
    outcome = "would change" if dry_run else "changed"
    click.echo(f"{len(changes)} vintage pipeline refs checked, {n_changed} {outcome}")
