"""CLI entry point for SDC pipelines.

Usage:
    sdc run ingest           # run the ingest step
    sdc run prepare          # run the prepare step
    sdc run all              # run ingest then prepare
    sdc run all --year 2022  # override year
    sdc info                 # show pipeline config
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
def version_bump(topic_dir: str, force: str | None, dry_run: bool, no_tag: bool):
    """Bump the version of a pipeline dataset.

    TOPIC_DIR is the path to the pipeline directory (e.g., demographics/Gender).
    Automatically creates an annotated git tag unless --no-tag is passed.
    """
    from sdc_core.versioning import update_version

    result = update_version(
        topic_dir,
        force_level=force,
        dry_run=dry_run,
        auto_tag=not no_tag,
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
