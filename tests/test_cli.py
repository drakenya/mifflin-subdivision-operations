from pathlib import Path
import yaml
from click.testing import CliRunner
from waybill_generator.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output


def test_validate_passes_with_valid_data():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "validate"])
    assert result.exit_code == 0
    assert "Cars: 2" in result.output
    assert "Waybills: 6" in result.output
    assert "Railroads: 1" in result.output


def test_list_cars():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "list", "cars"])
    assert result.exit_code == 0
    assert "PRR-12345" in result.output
    assert "PRR-67890" in result.output


def test_list_waybills():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "list", "waybills"])
    assert result.exit_code == 0
    assert "waybill-1" in result.output
    assert "LOADED" in result.output


def test_list_waybills_filtered_by_type():
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(FIXTURES), "list", "waybills", "--type", "EMPTY"]
    )
    assert result.exit_code == 0
    assert "empty-1" in result.output
    assert "waybill-1" not in result.output


def test_generate_produces_pdf(tmp_path):
    session = tmp_path / "session.yaml"
    session.write_text(
        "cards:\n  - car: PRR-12345\n    waybill: waybill-1\n"
        "  - car: PRR-67890\n    waybill: empty-1\n"
    )
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [
        "--data-path", str(FIXTURES),
        "generate",
        "--session", str(session),
        "--output", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"


def test_search_returns_results():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--keyword", "clearfield"])
    assert result.exit_code == 0
    assert "cat-001" in result.output


def test_search_no_results():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--keyword", "xyznotfound"])
    assert result.exit_code == 0
    assert "No results" in result.output


def test_search_missing_catalog(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(tmp_path), "search", "--keyword", "coal"])
    assert result.exit_code != 0


def test_search_by_car_type():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--car-type", "HM"])
    assert result.exit_code == 0
    assert "cat-001" in result.output


def test_search_by_source():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--source", "opsig"])
    assert result.exit_code == 0
    assert "cat-001" in result.output
    assert "cat-002" not in result.output


def _make_catalog(tmp_path):
    """Write a minimal industry_catalog.yaml to tmp_path."""
    (tmp_path / "industry_catalog.yaml").write_text(
        "- id: cat-001\n"
        "  name: Clearfield Coal Co.\n"
        "  city: Clearfield\n"
        "  state: PA\n"
        "  railroad_id: PRR\n"
        "  source: opsig\n"
        "  source_file: coal.csv\n"
        "  ships: [coal]\n"
        "  receives: []\n"
        "  car_types: [HM]\n"
    )


def _make_locations(tmp_path, content="- id: LEW\n  name: Lewistown\n  industries: []\n"):
    (tmp_path / "locations.yaml").write_text(content)


def test_add_industry_preview_shows_yaml(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001", "--preview"]
    )
    assert result.exit_code == 0
    assert "Clearfield Coal Co." in result.output
    assert "Proposed YAML" in result.output
    # File must be unchanged
    assert "Clearfield" not in (tmp_path / "locations.yaml").read_text()


def test_add_industry_new_location_writes_file(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001"], input="Y\n"
    )
    assert result.exit_code == 0
    content = (tmp_path / "locations.yaml").read_text()
    assert "Clearfield" in content
    assert "Clearfield Coal Co." in content


def test_add_industry_cancel_does_not_write(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    original = (tmp_path / "locations.yaml").read_text()
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001"], input="N\n"
    )
    assert result.exit_code == 0
    assert (tmp_path / "locations.yaml").read_text() == original


def test_add_industry_missing_catalog(tmp_path):
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(tmp_path), "add-industry", "cat-001"])
    assert result.exit_code != 0


def test_add_industry_missing_catalog_id(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-NOTFOUND"], input="Y\n"
    )
    assert result.exit_code != 0


def test_add_industry_existing_location(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(
        tmp_path,
        "- id: CLR\n  name: Clearfield\n  state: PA\n  railroad_id: PRR\n  industries: []\n",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001"], input="y\nY\n"
    )
    assert result.exit_code == 0
    locs = yaml.safe_load((tmp_path / "locations.yaml").read_text())
    clr = next(l for l in locs if l["id"] == "CLR")
    assert any(i["name"] == "Clearfield Coal Co." for i in clr.get("industries", []))


def test_add_industry_preview_with_matching_location_no_prompt(tmp_path):
    _make_catalog(tmp_path)
    # Create a location that WILL match the catalog entry (Clearfield, PA, PRR)
    _make_locations(
        tmp_path,
        "- id: CLR\n  name: Clearfield\n  state: PA\n  railroad_id: PRR\n  industries: []\n",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001", "--preview"]
    )
    assert result.exit_code == 0
    assert "Proposed YAML" in result.output
    # File unchanged — no write
    locs = yaml.safe_load((tmp_path / "locations.yaml").read_text())
    assert all(len(loc.get("industries", [])) == 0 for loc in locs)
