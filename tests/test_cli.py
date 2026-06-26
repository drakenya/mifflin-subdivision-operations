from pathlib import Path
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
