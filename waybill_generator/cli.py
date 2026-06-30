from datetime import date
from pathlib import Path
import yaml
import click
from waybill_generator.config import load_config
from waybill_generator.repository.yaml_repo import YamlRepository
from waybill_generator.repository.catalog_repo import CatalogRepository
from waybill_generator.layouts.modelling_the_sp import ModellingTheSpLayout
from waybill_generator.layouts.experimental_1 import Experimental1Layout
from waybill_generator.models.waybill import LoadedWaybill
from waybill_generator.renderer.pdf import render_pdf

_LAYOUTS = {
    "modelling_the_sp": ModellingTheSpLayout,
    "experimental_1": Experimental1Layout,
}


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


def _generate_location_id(city: str, existing_ids: set[str]) -> str:
    base = city[:3].upper().replace(" ", "")
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _generate_industry_id(loc_id: str, industry_name: str, existing_ids: set[str]) -> str:
    first_word = industry_name.split()[0].upper()[:6]
    base = f"{loc_id}-{first_word}"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _display_catalog_entry(entry) -> None:
    click.echo(f"\nCatalog: {entry.id}")
    click.echo(f"  Name:     {entry.name}")
    click.echo(f"  Location: {entry.city}, {entry.state}")
    click.echo(f"  Railroad: {entry.railroad_id or '(unknown)'}")
    click.echo(f"  Source:   {entry.source} / {entry.source_file}")
    if entry.source_ref:
        click.echo(f"  Ref:      {entry.source_ref}")
    if entry.ships:
        click.echo(f"  Ships:    {', '.join(entry.ships)}")
    if entry.receives:
        click.echo(f"  Receives: {', '.join(entry.receives)}")
    if entry.car_types:
        click.echo(f"  Car types: {', '.join(entry.car_types)}")
    if entry.notes:
        click.echo(f"  Notes:    {entry.notes}")
    click.echo()


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


@main.command("search")
@click.option("--keyword", default=None, help="Search name, city, notes")
@click.option("--commodity", default=None, help="Commodity id or keyword")
@click.option("--car-type", default=None, help="AAR code (e.g. HM, XM, GB)")
@click.option("--railroad", default=None, help="Railroad id (e.g. PRR, NYC)")
@click.option("--ships", "direction", flag_value="ships", default=None,
              help="Match only industries that ship the commodity")
@click.option("--receives", "direction", flag_value="receives", default=None,
              help="Match only industries that receive the commodity")
@click.option("--source", default=None, help="Filter by source (opsig, jbritton, manual)")
@click.option("--limit", default=20, show_default=True, help="Max results")
@click.pass_context
def search(ctx, keyword, commodity, car_type, railroad, direction, source, limit):
    """Search the industry reference catalog."""
    catalog_path = Path(ctx.obj["data_path"]) / "industry_catalog.yaml"
    if not catalog_path.exists():
        click.echo("No industry_catalog.yaml found in data path.", err=True)
        raise SystemExit(1)
    repo = CatalogRepository(catalog_path)
    results = repo.search(
        keyword=keyword,
        commodity=commodity,
        car_type=car_type,
        railroad=railroad,
        ships=(direction == "ships"),
        receives=(direction == "receives"),
        source=source,
        limit=limit,
    )
    if not results:
        click.echo("No results found.")
        return
    click.echo(f"{'ID':<12} {'Name':<36} {'City':<15} {'RR':<6} {'Ships':<18} {'Receives':<18} Source")
    click.echo("-" * 112)
    for e in results:
        ships_str = ", ".join(e.ships[:2]) + ("…" if len(e.ships) > 2 else "")
        recv_str = ", ".join(e.receives[:2]) + ("…" if len(e.receives) > 2 else "")
        rr = e.railroad_id or ""
        src = f"{e.source}/{e.source_file}"[:28]
        click.echo(
            f"{e.id:<12} {e.name[:35]:<36} {e.city[:14]:<15} {rr:<6}"
            f" {ships_str:<18} {recv_str:<18} {src}"
        )


@main.command("add-industry")
@click.argument("catalog_id")
@click.option("--preview", is_flag=True, help="Show proposed YAML without writing")
@click.pass_context
def add_industry(ctx, catalog_id, preview):
    """Add a catalog industry entry to locations.yaml."""
    data_path = Path(ctx.obj["data_path"])
    catalog_path = data_path / "industry_catalog.yaml"
    locations_path = data_path / "locations.yaml"

    if not catalog_path.exists():
        click.echo("No industry_catalog.yaml found in data path.", err=True)
        raise SystemExit(1)

    repo = CatalogRepository(catalog_path)
    try:
        entry = repo.get(catalog_id)
    except KeyError:
        click.echo(f"Catalog entry not found: {catalog_id!r}", err=True)
        raise SystemExit(1)

    _display_catalog_entry(entry)

    raw_locations = yaml.safe_load(locations_path.read_text()) or []
    existing_loc_ids = {loc["id"] for loc in raw_locations}
    existing_ind_ids = {
        ind["id"]
        for loc in raw_locations
        for ind in loc.get("industries", [])
    }

    matches = [
        loc for loc in raw_locations
        if loc.get("name", "").lower() == entry.city.lower()
        and loc.get("state", "").upper() == entry.state.upper()
        and loc.get("railroad_id") == entry.railroad_id
    ]

    add_to_existing = False
    target_loc_id: str | None = None

    if preview:
        # In preview mode: no interactive prompts — auto-pick first match or generate new id
        if matches:
            target_loc_id = matches[0]["id"]
            add_to_existing = True
        else:
            target_loc_id = _generate_location_id(entry.city, existing_loc_ids)
    else:
        if len(matches) == 1:
            target_loc_id = matches[0]["id"]
            click.echo(f"Existing location found: {target_loc_id} ({matches[0]['name']})")
            if click.confirm("Add industry to this location?", default=True):
                add_to_existing = True
            else:
                target_loc_id = None
        elif len(matches) > 1:
            click.echo("Multiple matching locations:")
            for i, m in enumerate(matches, 1):
                click.echo(f"  [{i}] {m['id']} — {m['name']}")
            choice = click.prompt("Choose location number (0 = create new)", type=int, default=0)
            if 1 <= choice <= len(matches):
                target_loc_id = matches[choice - 1]["id"]
                add_to_existing = True

        if not add_to_existing:
            target_loc_id = _generate_location_id(entry.city, existing_loc_ids)

    ind_id = _generate_industry_id(target_loc_id, entry.name, existing_ind_ids)
    industry_dict = {
        "id": ind_id,
        "name": entry.name,
        "location_id": target_loc_id,
        "ships": entry.ships,
        "receives": entry.receives,
    }

    if add_to_existing:
        click.echo(f"Will add to location: {target_loc_id}")
        proposed_yaml = yaml.dump(industry_dict, default_flow_style=False, allow_unicode=True)
    else:
        new_loc: dict = {
            "id": target_loc_id,
            "name": entry.city,
            "state": entry.state,
            "industries": [industry_dict],
        }
        if entry.railroad_id:
            new_loc["railroad_id"] = entry.railroad_id
        click.echo(f"Will create new location: {target_loc_id}")
        proposed_yaml = yaml.dump([new_loc], default_flow_style=False, allow_unicode=True)

    click.echo("\nProposed YAML:\n---")
    click.echo(proposed_yaml.rstrip())
    click.echo("---\n")

    if preview:
        return

    action = click.prompt("Write to locations.yaml? [Y/e/N]", default="Y").strip().upper()

    if action == "N":
        click.echo("Cancelled.")
        return

    if action == "E":
        edited = click.edit(proposed_yaml, extension=".yaml")
        if edited is None:
            click.echo("No changes made. Cancelled.")
            return
        try:
            yaml.safe_load(edited)
        except yaml.YAMLError as exc:
            click.echo(f"Invalid YAML after editing: {exc}", err=True)
            raise SystemExit(1)
        proposed_yaml = edited

    if add_to_existing:
        parsed_industry = yaml.safe_load(proposed_yaml)
        locs = yaml.safe_load(locations_path.read_text()) or []
        for loc in locs:
            if loc["id"] == target_loc_id:
                loc.setdefault("industries", []).append(parsed_industry)
                break
        locations_path.write_text(yaml.dump(locs, default_flow_style=False, allow_unicode=True))
        click.echo(f"Added industry {ind_id} to {target_loc_id}.")
    else:
        with locations_path.open("a") as f:
            f.write("\n")
            f.write(proposed_yaml)
        click.echo(f"Added location {target_loc_id} with industry {ind_id} to locations.yaml.")


@main.command("import")
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--source", default=None, type=click.Choice(["opsig", "jbritton"]),
              help="Source format (auto-detected from parent directory if omitted)")
@click.option("--industry-db", default="./industry_database", show_default=True,
              help="Path to industry_database directory")
@click.pass_context
def import_catalog(ctx, filepath, source, industry_db):
    """Import an OpSIG or JBritton source file into the industry catalog."""
    from waybill_generator.importers.opsig import parse_opsig
    from waybill_generator.importers.jbritton import parse_jbritton
    from waybill_generator.importers.base import group_rows
    from waybill_generator.importers.normalizer import normalize_entries

    fp = Path(filepath)
    db_path = Path(industry_db)
    data_path = Path(ctx.obj["data_path"])

    if source is None:
        parent = fp.parent.name.lower()
        if parent == "opsig":
            source = "opsig"
        elif parent == "jbritton":
            source = "jbritton"
        else:
            click.echo(
                f"Cannot auto-detect source from directory {fp.parent.name!r}. "
                "Use --source opsig or --source jbritton.",
                err=True,
            )
            raise SystemExit(1)

    rows = parse_opsig(fp) if source == "opsig" else parse_jbritton(fp)
    grouped = group_rows(rows)
    source_file = fp.name

    catalog_path = data_path / "industry_catalog.yaml"
    entries, report = normalize_entries(
        grouped, source, source_file,
        db_path / "commodity_map.yaml",
        db_path / "opsig_car_map.yaml",
        data_path / "commodities.yaml",
    )

    catalog_repo = CatalogRepository(catalog_path)
    replaced, added = catalog_repo.replace_from_source(source_file, entries)
    total = len(catalog_repo.search(limit=999_999))

    click.echo(f"\nImporting: {source_file}  [{source}]")
    click.echo(f"  Rows parsed:    {len(rows):<6}  →  {len(grouped)} industries grouped")
    click.echo(f"  Replaced:       {replaced:<6}  existing entries")
    click.echo(f"  Added:          {added:<6}  new entries")
    click.echo(f"  Catalog total:  {total:<6}  entries")
    click.echo()
    click.echo("Commodity normalization:")
    click.echo(f"  map-matched:    {report.map_count}")
    click.echo(f"  auto-matched:   {report.auto_count}")
    click.echo(f"  free-text:      {report.free_count}")

    if report.unmatched:
        click.echo()
        click.echo("Unmatched commodities (add to commodity_map.yaml to normalize):")
        for commodity, count in sorted(report.unmatched.items(), key=lambda x: -x[1]):
            noun = "industry" if count == 1 else "industries"
            click.echo(f"  {commodity!r:<40} {count} {noun}")

    if report.unknown_car_codes:
        click.echo()
        unknown = ", ".join(report.unknown_car_codes)
        click.echo(f"Unknown OpSIG car codes (not in opsig_car_map.yaml): {unknown}")
