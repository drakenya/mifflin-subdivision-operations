from waybill_generator.importers.base import ImportedRow, group_rows, make_catalog_id


def _row(
    name="Acme Corp", city="Reading", state="PA", railroad="PRR",
    direction="S", commodity="coal", notes="", car_types=None, source_ref="",
) -> ImportedRow:
    return ImportedRow(
        year="1945", name=name, city=city, state=state, railroad=railroad,
        direction=direction, commodity=commodity, notes=notes,
        car_types=car_types or [], source_ref=source_ref,
    )


class TestGroupRows:
    def test_single_row_ships(self):
        groups = group_rows([_row(direction="S", commodity="coal")])
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == []

    def test_single_row_receives(self):
        groups = group_rows([_row(direction="R", commodity="lumber")])
        assert groups[0]["receives"] == ["lumber"]
        assert groups[0]["ships"] == []

    def test_blank_direction_non_empty_commodity_goes_to_both(self):
        groups = group_rows([_row(direction="", commodity="freight")])
        assert "freight" in groups[0]["ships"]
        assert "freight" in groups[0]["receives"]

    def test_blank_direction_blank_commodity_ignored(self):
        groups = group_rows([_row(direction="", commodity="")])
        assert groups[0]["ships"] == []
        assert groups[0]["receives"] == []

    def test_multiple_rows_same_industry_grouped(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="R", commodity="lumber")]
        groups = group_rows(rows)
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == ["lumber"]

    def test_duplicate_commodity_deduplicated(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="S", commodity="coal")]
        groups = group_rows(rows)
        assert groups[0]["ships"].count("coal") == 1

    def test_different_industries_produce_separate_groups(self):
        rows = [_row(name="A Corp"), _row(name="B Corp")]
        groups = group_rows(rows)
        assert len(groups) == 2

    def test_notes_taken_from_first_non_empty(self):
        rows = [_row(notes=""), _row(notes="Main Line - 220"), _row(notes="Different note")]
        groups = group_rows(rows)
        assert groups[0]["notes"] == "Main Line - 220"

    def test_car_types_merged_and_deduplicated(self):
        rows = [
            _row(car_types=["HM", "GB"]),
            _row(direction="R", commodity="ore", car_types=["GB", "XM"]),
        ]
        groups = group_rows(rows)
        assert set(groups[0]["raw_car_types"]) == {"HM", "GB", "XM"}

    def test_source_ref_from_first_row(self):
        rows = [_row(source_ref="pennsyrr.com"), _row(source_ref="other")]
        groups = group_rows(rows)
        assert groups[0]["source_ref"] == "pennsyrr.com"


class TestMakeCatalogId:
    def test_returns_cat_prefixed_8_hex(self):
        id_ = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        assert id_.startswith("cat-")
        assert len(id_) == 12  # "cat-" + 8 hex chars

    def test_deterministic(self):
        a = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        b = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        assert a == b

    def test_different_source_file_different_id(self):
        a = make_catalog_id("file-a.txt", "Acme", "Reading", "PA", "PRR")
        b = make_catalog_id("file-b.txt", "Acme", "Reading", "PA", "PRR")
        assert a != b

    def test_different_name_different_id(self):
        a = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        b = make_catalog_id("file.txt", "Other Corp", "Reading", "PA", "PRR")
        assert a != b


from waybill_generator.importers.opsig import parse_opsig, _parse_line as opsig_parse_line


class TestOpSIGParseLine:
    def test_full_row(self):
        line = ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S",
                "latex, plastic pellets", "butadiene prod.mfg", "VH(e)", "CH,T"]
        row = opsig_parse_line(line)
        assert row is not None
        assert row.name == "Dow"
        assert row.city == "Allyn's Point"
        assert row.state == "CT"
        assert row.railroad == "P&W"
        assert row.direction == "S"
        assert row.commodity == "latex, plastic pellets"
        assert row.notes == "butadiene prod.mfg"
        assert row.car_types == ["CH", "T"]
        assert row.source_ref == ""

    def test_blank_name_returns_none(self):
        line = ["2004", "", "City", "PA", "PRR", "S", "coal", "", "", ""]
        assert opsig_parse_line(line) is None

    def test_short_line_padded_to_10(self):
        line = ["2004", "Acme", "Reading", "PA", "PRR", "S", "coal"]
        row = opsig_parse_line(line)
        assert row is not None
        assert row.car_types == []

    def test_single_car_type(self):
        line = ["55", "Firm", "City", "PA", "PRR", "S", "steel", "", "", "G"]
        row = opsig_parse_line(line)
        assert row.car_types == ["G"]

    def test_receives_direction(self):
        line = ["2004", "Mill", "City", "PA", "PRR", "R", "coal", "", "", "HM"]
        row = opsig_parse_line(line)
        assert row.direction == "R"

    def test_blank_car_type_column(self):
        line = ["2004", "Mill", "City", "PA", "PRR", "R", "coal", "", "", ""]
        row = opsig_parse_line(line)
        assert row.car_types == []


class TestParseOpSIGFile:
    def test_parses_txt_rows(self, tmp_path):
        content = (
            "2004\tDow\tAllyn's Point\tCT\tP&W\tS\tlatex\tbutadiene\tVH\tCH,T\r\n"
            "2004\tPeter Paul\tBeacon Falls\tCT\tGRS\tR\tcorn syrup\tcandy mfg\tH\tT\r\n"
            "\t\t\t\t\t\t\t\t\t\r\n"
        )
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_opsig(p)
        assert len(rows) == 2
        assert rows[0].name == "Dow"
        assert rows[1].name == "Peter Paul"

    def test_skips_blank_name_rows(self, tmp_path):
        content = "\t\t\t\t\t\t\t\t\t\r\n2004\tAcme\tCity\tPA\tPRR\tS\tcoal\t\t\tH\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Acme"


from waybill_generator.importers.jbritton import parse_jbritton, _parse_line as jb_parse_line


class TestJBrittonParseLine:
    def _line(
        self, name="Standard Novelty Works", city="Duncannon", state="PA",
        railroad="PRR", direction="S", commodity="Sleds",
        location_ref="Middle Division - Main Line - 208",
        source_ref="pennsyrr.com PRR CT1000",
    ) -> list[str]:
        line = ["1945", name, city, state, railroad, direction, commodity,
                "", location_ref, source_ref]
        line.extend([""] * (256 - len(line)))
        return line

    def test_full_row(self):
        row = jb_parse_line(self._line())
        assert row is not None
        assert row.name == "Standard Novelty Works"
        assert row.city == "Duncannon"
        assert row.state == "PA"
        assert row.railroad == "PRR"
        assert row.direction == "S"
        assert row.commodity == "Sleds"
        assert row.notes == "Middle Division - Main Line - 208"
        assert row.source_ref == "pennsyrr.com PRR CT1000"
        assert row.car_types == []

    def test_blank_name_returns_none(self):
        assert jb_parse_line(self._line(name="")) is None

    def test_blank_direction_allowed(self):
        row = jb_parse_line(self._line(direction="", commodity=""))
        assert row is not None
        assert row.direction == ""
        assert row.commodity == ""

    def test_short_line_padded(self):
        line = ["1945", "Station", "Perdix", "PA", "PRR"]
        row = jb_parse_line(line)
        assert row is not None
        assert row.commodity == ""
        assert row.notes == ""
        assert row.source_ref == ""


class TestParseJBrittonFile:
    def test_parses_rows(self, tmp_path):
        tabs = "\t" * 246
        content = (
            f"1945\tStandard Novelty Works\tDuncannon\tPA\tPRR\tS\tSleds\t\tMain Line\tpennsyrr.com{tabs}\r\n"
            f"1945\tStandard Novelty Works\tDuncannon\tPA\tPRR\tR\tLumber\t\tMain Line\tpennsyrr.com{tabs}\r\n"
            f"1945\tStation\tPerdix\tPA\tPRR\t\t\t\tMain Line\tpennsyrr.com{tabs}\r\n"
        )
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_jbritton(p)
        assert len(rows) == 3
        assert rows[0].direction == "S"
        assert rows[1].direction == "R"
        assert rows[2].direction == ""

    def test_no_car_types(self, tmp_path):
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tsource{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_jbritton(p)
        assert rows[0].car_types == []


import pytest
from waybill_generator.importers.normalizer import (
    load_commodity_map,
    build_auto_map,
    load_opsig_car_map,
    _normalize_commodity,
    normalize_entries,
    NormReport,
)

_COMMODITIES_YAML = """\
- id: coal
  name: Bituminous Coal
  aar_code: "01210"
  acceptable_car_types: [HM, GB]
- id: lumber
  name: Lumber
  aar_code: "02410"
  acceptable_car_types: [FM, XM]
"""

_OPSIG_CAR_MAP_YAML = "T: TM\nH: HM\nB: XM\nCH: LO\nG: GB\n"


@pytest.fixture
def commodities_file(tmp_path):
    p = tmp_path / "commodities.yaml"
    p.write_text(_COMMODITIES_YAML)
    return p


@pytest.fixture
def opsig_car_map_file(tmp_path):
    p = tmp_path / "opsig_car_map.yaml"
    p.write_text(_OPSIG_CAR_MAP_YAML)
    return p


@pytest.fixture
def empty_commodity_map(tmp_path):
    p = tmp_path / "commodity_map.yaml"
    p.write_text("")
    return p


def _grouped(ships=None, receives=None, raw_car_types=None, source_ref="") -> list[dict]:
    return [{
        "name": "Test Industry", "city": "Reading", "state": "PA", "railroad": "PRR",
        "ships": ships or [], "receives": receives or [],
        "notes": "", "raw_car_types": raw_car_types or [], "source_ref": source_ref,
    }]


class TestLoadCommodityMap:
    def test_loads_entries_case_insensitive(self, tmp_path):
        p = tmp_path / "commodity_map.yaml"
        p.write_text("- source_text: Petroleum Products\n  commodity_id: null\n"
                     "- source_text: Specialty Steel\n  commodity_id: steel\n")
        cmap = load_commodity_map(p)
        assert cmap["petroleum products"] is None
        assert cmap["specialty steel"] == "steel"

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_commodity_map(tmp_path / "nonexistent.yaml") == {}


class TestBuildAutoMap:
    def test_builds_from_commodity_names(self, commodities_file):
        auto = build_auto_map(commodities_file)
        assert auto["bituminous coal"] == "coal"
        assert auto["lumber"] == "lumber"


class TestLoadOpSIGCarMap:
    def test_loads_and_uppercases_keys(self, opsig_car_map_file):
        cmap = load_opsig_car_map(opsig_car_map_file)
        assert cmap["T"] == "TM"
        assert cmap["H"] == "HM"

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_opsig_car_map(tmp_path / "nonexistent.yaml") == {}


class TestNormalizeCommodity:
    def setup_method(self):
        self.auto_map = {"bituminous coal": "coal", "lumber": "lumber"}
        self.commodity_map = {"petroleum products": None, "specialty steel": "steel"}

    def test_explicit_map_wins_over_auto(self):
        # "Specialty Steel" would not auto-match, but explicit map hits
        norm, mt = _normalize_commodity("Specialty Steel", self.commodity_map, self.auto_map)
        assert norm == "steel"
        assert mt == "map"

    def test_null_sentinel_keeps_free_text(self):
        norm, mt = _normalize_commodity("Petroleum Products", self.commodity_map, self.auto_map)
        assert norm == "Petroleum Products"
        assert mt == "map"

    def test_auto_match_case_insensitive(self):
        norm, mt = _normalize_commodity("Bituminous Coal", {}, self.auto_map)
        assert norm == "coal"
        assert mt == "auto"

    def test_auto_match_substring_source_contains_name(self):
        # "lumber" is in "lumber supply"
        norm, mt = _normalize_commodity("lumber supply", {}, self.auto_map)
        assert norm == "lumber"
        assert mt == "auto"

    def test_auto_match_substring_name_contains_source(self):
        # "coal" is in "bituminous coal"
        norm, mt = _normalize_commodity("coal", {}, self.auto_map)
        assert norm == "coal"
        assert mt == "auto"

    def test_free_text_fallback(self):
        norm, mt = _normalize_commodity("Sleds", {}, self.auto_map)
        assert norm == "Sleds"
        assert mt == "free"

    def test_auto_match_reverse_requires_word_boundary(self):
        # "oil" should NOT match commodity named "soil" via reverse direction
        # but SHOULD match a commodity named "fuel oil"
        auto = {"soil": "dirt", "fuel oil": "petroleum"}
        result, tier = _normalize_commodity("oil", {}, auto)
        # "oil" in "soil" is not a word boundary — should NOT match "soil"
        # "oil" in "fuel oil" IS a word boundary — SHOULD match "fuel oil"
        assert result == "petroleum"
        assert tier == "auto"


class TestNormalizeEntries:
    def test_auto_matched_commodity_written_as_id(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, report = normalize_entries(
            _grouped(ships=["Bituminous Coal"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert entries[0].ships == ["coal"]
        assert report.auto_count == 1
        assert report.map_count == 0

    def test_map_matched_wins_over_auto(
        self, tmp_path, commodities_file, opsig_car_map_file
    ):
        cmap = tmp_path / "commodity_map.yaml"
        cmap.write_text("- source_text: Bituminous Coal\n  commodity_id: coal-override\n")
        entries, report = normalize_entries(
            _grouped(ships=["Bituminous Coal"]), "jbritton", "file.txt",
            cmap, opsig_car_map_file, commodities_file,
        )
        assert entries[0].ships == ["coal-override"]
        assert report.map_count == 1

    def test_free_text_tracked_in_report(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, report = normalize_entries(
            _grouped(ships=["Sleds"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert entries[0].ships == ["Sleds"]
        assert report.free_count == 1
        assert "Sleds" in report.unmatched

    def test_null_sentinel_suppresses_unmatched_report(
        self, tmp_path, commodities_file, opsig_car_map_file
    ):
        cmap = tmp_path / "commodity_map.yaml"
        cmap.write_text("- source_text: Sleds\n  commodity_id:\n")
        _, report = normalize_entries(
            _grouped(ships=["Sleds"]), "jbritton", "file.txt",
            cmap, opsig_car_map_file, commodities_file,
        )
        assert "Sleds" not in report.unmatched

    def test_opsig_car_types_mapped_to_aar(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, report = normalize_entries(
            _grouped(ships=["coal"], raw_car_types=["H", "T"]), "opsig", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert "HM" in entries[0].car_types
        assert "TM" in entries[0].car_types

    def test_unknown_opsig_car_code_logged(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        _, report = normalize_entries(
            _grouped(ships=["coal"], raw_car_types=["ZZ"]), "opsig", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert "ZZ" in report.unknown_car_codes

    def test_jbritton_car_types_inferred_from_matched_commodity(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, _ = normalize_entries(
            _grouped(ships=["Bituminous Coal"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert "HM" in entries[0].car_types
        assert "GB" in entries[0].car_types

    def test_jbritton_unmatched_commodity_empty_car_types(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, _ = normalize_entries(
            _grouped(ships=["Sleds"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert entries[0].car_types == []

    def test_entry_fields_set_correctly(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, _ = normalize_entries(
            _grouped(ships=["coal"], source_ref="pennsyrr.com"),
            "jbritton", "prr_middle.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        e = entries[0]
        assert e.source == "jbritton"
        assert e.source_file == "prr_middle.txt"
        assert e.source_ref == "pennsyrr.com"
        assert e.id.startswith("cat-")
        assert len(e.id) == 12

import yaml
from waybill_generator.repository.catalog_repo import CatalogRepository
from waybill_generator.models.catalog import CatalogIndustry


def _cat_entry(id_, source_file="file.txt", source="opsig") -> CatalogIndustry:
    return CatalogIndustry(
        id=id_, name=f"Industry {id_}", city="Reading", state="PA",
        source=source, source_file=source_file,
    )


def _write_catalog(tmp_path, entries) -> "Path":
    p = tmp_path / "industry_catalog.yaml"
    data = [e.model_dump(exclude_none=True) for e in entries]
    p.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    return p


class TestReplaceFromSource:
    def test_replaces_entries_from_source_file_only(self, tmp_path):
        old = [_cat_entry("cat-aaa", "file.txt"), _cat_entry("cat-bbb", "other.txt")]
        p = _write_catalog(tmp_path, old)
        repo = CatalogRepository(p)
        repo.replace_from_source("file.txt", [_cat_entry("cat-ccc", "file.txt")])
        ids = {e.id for e in CatalogRepository(p).search(limit=999)}
        assert "cat-bbb" in ids   # different source_file — untouched
        assert "cat-aaa" not in ids  # same source_file — replaced
        assert "cat-ccc" in ids   # new entry

    def test_returns_replaced_and_added_counts(self, tmp_path):
        old = [_cat_entry("cat-aaa", "file.txt"), _cat_entry("cat-bbb", "file.txt")]
        p = _write_catalog(tmp_path, old)
        repo = CatalogRepository(p)
        new = [_cat_entry("cat-aaa", "file.txt"), _cat_entry("cat-ccc", "file.txt")]
        replaced, added = repo.replace_from_source("file.txt", new)
        assert replaced == 1   # cat-aaa in both old and new
        assert added == 1      # cat-ccc is new

    def test_first_import_returns_zero_replaced(self, tmp_path):
        p = tmp_path / "industry_catalog.yaml"
        p.write_text("")
        repo = CatalogRepository(p)
        replaced, added = repo.replace_from_source("file.txt", [_cat_entry("cat-new")])
        assert replaced == 0
        assert added == 1

    def test_manual_entries_never_removed(self, tmp_path):
        old = [
            _cat_entry("cat-manual", "manual", "manual"),
            _cat_entry("cat-old", "file.txt", "opsig"),
        ]
        p = _write_catalog(tmp_path, old)
        repo = CatalogRepository(p)
        repo.replace_from_source("file.txt", [_cat_entry("cat-new", "file.txt")])
        ids = {e.id for e in CatalogRepository(p).search(limit=999)}
        assert "cat-manual" in ids
        assert "cat-old" not in ids

    def test_reimport_same_file_replaces_all(self, tmp_path):
        first = [_cat_entry("cat-aaa"), _cat_entry("cat-bbb")]
        p = _write_catalog(tmp_path, first)
        repo = CatalogRepository(p)
        second = [_cat_entry("cat-aaa"), _cat_entry("cat-bbb")]
        replaced, added = repo.replace_from_source("file.txt", second)
        assert replaced == 2
        assert added == 0


from click.testing import CliRunner
from waybill_generator.cli import main


def _setup_dirs(tmp_path, commodities_yaml="[]"):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "commodities.yaml").write_text(commodities_yaml)
    (data_dir / "industry_catalog.yaml").write_text("")
    db_dir = tmp_path / "industry_database"
    db_dir.mkdir()
    (db_dir / "commodity_map.yaml").write_text("")
    (db_dir / "opsig_car_map.yaml").write_text("H: HM\nT: TM\nB: XM\n")
    return data_dir, db_dir


class TestImportCommand:
    def test_jbritton_import_writes_catalog(self, tmp_path):
        data_dir, db_dir = _setup_dirs(
            tmp_path,
            "- id: lumber\n  name: Lumber\n  aar_code: '02410'\n  acceptable_car_types: [FM]\n",
        )
        jb_dir = db_dir / "jbritton"
        jb_dir.mkdir()
        tabs = "\t" * 246
        content = (
            f"1945\tAcme Lumber Co\tReading\tPA\tPRR\tS\tLumber\t\tMain Line\tsrc{tabs}\r\n"
            f"1945\tAcme Lumber Co\tReading\tPA\tPRR\tR\tHardware\t\tMain Line\tsrc{tabs}\r\n"
        )
        src = jb_dir / "prr_middle.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import", str(src),
            "--industry-db", str(db_dir),
        ])

        assert result.exit_code == 0, result.output
        assert "1 industries grouped" in result.output
        catalog = yaml.safe_load((data_dir / "industry_catalog.yaml").read_text()) or []
        assert len(catalog) == 1
        assert catalog[0]["name"] == "Acme Lumber Co"
        assert "lumber" in catalog[0]["ships"]

    def test_auto_detects_opsig_from_dir(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        opsig_dir = db_dir / "opsig"
        opsig_dir.mkdir()
        content = "2004\tAcme Corp\tCity\tPA\tPRR\tS\tCoal\tnotes\tH\tH\r\n"
        src = opsig_dir / "test.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import", str(src),
            "--industry-db", str(db_dir),
        ])
        assert result.exit_code == 0, result.output
        assert "[opsig]" in result.output

    def test_unknown_dir_requires_source_flag(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        src = tmp_path / "mystery.txt"
        src.write_text("2004\tAcme\tCity\tPA\tPRR\tS\tCoal\t\t\t\r\n")

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import", str(src),
            "--industry-db", str(db_dir),
        ])
        assert result.exit_code != 0

    def test_report_shows_replaced_added_total(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        jb_dir = db_dir / "jbritton"
        jb_dir.mkdir()
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tsrc{tabs}\r\n"
        src = jb_dir / "test.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        # First import
        runner.invoke(main, ["--data-path", str(data_dir), "import", str(src),
                             "--industry-db", str(db_dir)])
        # Re-import
        result = runner.invoke(main, ["--data-path", str(data_dir), "import", str(src),
                                      "--industry-db", str(db_dir)])

        assert result.exit_code == 0
        assert "Replaced:" in result.output
        assert "Added:" in result.output
        assert "Catalog total:" in result.output

    def test_unmatched_commodities_shown_in_report(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        jb_dir = db_dir / "jbritton"
        jb_dir.mkdir()
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tSleds\t\tMain Line\tsrc{tabs}\r\n"
        src = jb_dir / "test.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, ["--data-path", str(data_dir), "import", str(src),
                                      "--industry-db", str(db_dir)])
        assert "Sleds" in result.output
