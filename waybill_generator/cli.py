from datetime import date
from pathlib import Path
import yaml
import click
from waybill_generator.config import load_config
from waybill_generator.repository.yaml_repo import YamlRepository
from waybill_generator.layouts.modelling_the_sp import StandardPrrLayout
from waybill_generator.models.waybill import LoadedWaybill
from waybill_generator.renderer.pdf import render_pdf

_LAYOUTS = {"modelling_the_sp": StandardPrrLayout}


@click.group()
@click.option("--layout", default=None, help="Layout class name")
@click.option("--data-source", default=None, help="Data backend (yaml)")
@click.option("--data-path", default=None, help="Path to data directory")
@click.option("--output-dir", default=None, help="Directory for PDF output")
@click.pass_context
def main(ctx, layout, data_source, data_path, output_dir):
    """PRR model railroad car card + waybill PDF generator."""
    cfg = load_config()
    ctx.ensure_object(dict)
    ctx.obj["layout"] = layout or cfg.layout
    ctx.obj["data_source"] = data_source or cfg.data_source
    ctx.obj["data_path"] = data_path or cfg.data_path
    ctx.obj["output_dir"] = output_dir or cfg.output_dir


def _get_repo(ctx):
    return YamlRepository(ctx.obj["data_path"])


@main.command()
@click.option("--session", required=True, type=click.Path(exists=True), help="Session YAML file")
@click.option("--output", default=None, help="Output PDF path")
@click.pass_context
def generate(ctx, session, output):
    """Generate a PDF from a session file."""
    session_data = yaml.safe_load(Path(session).read_text()) or {}
    repo = _get_repo(ctx)

    triples = []
    for card in session_data.get("cards", []):
        car = repo.get_car(card["car"])
        waybill = repo.get_waybill(card["waybill"])
        railroad = repo.get_railroad(waybill.originating_railroad_id)
        if isinstance(waybill, LoadedWaybill):
            consignee_ind = repo.get_industry(waybill.consignee_id)
            consignee_loc = repo.get_location(consignee_ind.location_id)
            shipper_ind = repo.get_industry(waybill.shipper_id)
            shipper_loc = repo.get_location(shipper_ind.location_id)
            waybill = waybill.model_copy(update={
                "to_city": consignee_loc.name,
                "to_state": consignee_loc.state,
                "consignee_name": consignee_ind.name,
                "from_city": shipper_loc.name,
                "from_state": shipper_loc.state,
                "shipper_name": shipper_ind.name,
            })
        triples.append((car, waybill, railroad))

    layout_cls = _LAYOUTS.get(ctx.obj["layout"])
    if layout_cls is None:
        raise click.BadParameter(f"Unknown layout: {ctx.obj['layout']!r}")
    layout = layout_cls()

    if output is None:
        out_dir = Path(ctx.obj["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        output = str(out_dir / f"waybills-{date.today().isoformat()}.pdf")

    render_pdf(triples, layout, output)
    click.echo(f"Generated: {output}")


@main.group("list")
def list_group():
    """List cars or waybills."""
    pass


@list_group.command("cars")
@click.pass_context
def list_cars(ctx):
    """List all cars in the roster."""
    repo = _get_repo(ctx)
    for car in repo.get_cars():
        status = "" if car.active else "  [inactive]"
        click.echo(f"{car.id:<20} {car.capacity_tons}T{status}")


@list_group.command("layouts")
def list_layouts():
    """List available layout names for --layout."""
    for name in _LAYOUTS:
        click.echo(name)


@list_group.command("waybills")
@click.option("--type", "waybill_type", default=None, help="Filter by type (LOADED, EMPTY, etc.)")
@click.pass_context
def list_waybills(ctx, waybill_type):
    """List all waybills, optionally filtered by type."""
    repo = _get_repo(ctx)
    waybills = repo.get_waybills()
    if waybill_type:
        waybills = [w for w in waybills if str(w.waybill_type) == waybill_type.upper()]
    for w in waybills:
        # waybill_type is stored as a plain str when using Literal[...] in pydantic
        wtype_str = w.waybill_type.value if hasattr(w.waybill_type, "value") else str(w.waybill_type)
        click.echo(f"{w.id:<20} [{wtype_str}]")


@main.command()
@click.pass_context
def validate(ctx):
    """Validate all data files against schema."""
    repo = _get_repo(ctx)
    errors = []

    for label, loader in [
        ("Cars", repo.get_cars),
        ("Locations", repo.get_locations),
        ("Commodities", repo.get_commodities),
        ("Waybills", repo.get_waybills),
        ("Railroads", repo.get_railroads),
    ]:
        try:
            items = loader()
            click.echo(f"{label}: {len(items)} loaded")
        except Exception as e:
            errors.append(f"{label}: {e}")

    if errors:
        for err in errors:
            click.echo(f"ERROR: {err}", err=True)
        raise SystemExit(1)
    else:
        click.echo("All data files valid.")
