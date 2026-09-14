from pathlib import Path

import pytest

from waybill_generator.converters.base import RawRow, parse_tab_line, group_by_industry, to_json_records


class TestParseTabLine:
    def test_full_opsig_style_row(self):
        line = ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S",
                "latex, plastic pellets", "butadiene prod.mfg", "VH(e)", "CH,T"]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        assert row is not None
        assert row.year == "2004"
        assert row.name == "Dow"
        assert row.city == "Allyn's Point"
        assert row.state == "CT"
        assert row.railroad == "P&W"
        assert row.direction == "S"
        assert row.commodity == "latex, plastic pellets"
        assert row.notes == "butadiene prod.mfg"
        assert row.car_types == ["CH", "T"]
        assert row.source_ref == ""

    def test_full_jbritton_style_row(self):
        line = ["1945", "Standard Novelty Works", "Duncannon", "PA", "PRR", "S", "Sleds",
                "", "Middle Division - Main Line - 208", "pennsyrr.com PRR CT1000"]
        row = parse_tab_line(line, notes_col=8, source_ref_col=9, car_types_col=None)
        assert row is not None
        assert row.notes == "Middle Division - Main Line - 208"
        assert row.source_ref == "pennsyrr.com PRR CT1000"
        assert row.car_types == []

    def test_blank_name_returns_none(self):
        line = ["2004", "", "City", "PA", "PRR", "S", "coal", "", "", ""]
        assert parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9) is None

    def test_short_line_padded_to_10(self):
        line = ["2004", "Acme", "Reading", "PA", "PRR", "S", "coal"]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        assert row is not None
        assert row.car_types == []

    def test_blank_car_types_column(self):
        line = ["2004", "Mill", "City", "PA", "PRR", "R", "coal", "", "", ""]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        assert row.car_types == []


def _row(
    name="Acme Corp", city="Reading", state="PA", railroad="PRR", year="1945",
    direction="S", commodity="coal", notes="", car_types=None, source_ref="",
) -> RawRow:
    return RawRow(
        year=year, name=name, city=city, state=state, railroad=railroad,
        direction=direction, commodity=commodity, notes=notes,
        car_types=car_types or [], source_ref=source_ref,
    )


class TestGroupByIndustry:
    def test_single_row_ships(self):
        groups = group_by_industry([_row(direction="S", commodity="coal")])
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == []

    def test_single_row_receives(self):
        groups = group_by_industry([_row(direction="R", commodity="lumber")])
        assert groups[0]["receives"] == ["lumber"]
        assert groups[0]["ships"] == []

    def test_blank_direction_non_empty_commodity_goes_to_both(self):
        groups = group_by_industry([_row(direction="", commodity="freight")])
        assert "freight" in groups[0]["ships"]
        assert "freight" in groups[0]["receives"]

    def test_blank_direction_blank_commodity_ignored(self):
        groups = group_by_industry([_row(direction="", commodity="")])
        assert groups[0]["ships"] == []
        assert groups[0]["receives"] == []

    def test_multiple_rows_same_industry_grouped(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="R", commodity="lumber")]
        groups = group_by_industry(rows)
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == ["lumber"]

    def test_duplicate_commodity_deduplicated(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="S", commodity="coal")]
        groups = group_by_industry(rows)
        assert groups[0]["ships"].count("coal") == 1

    def test_different_industries_produce_separate_groups(self):
        rows = [_row(name="A Corp"), _row(name="B Corp")]
        groups = group_by_industry(rows)
        assert len(groups) == 2

    def test_notes_taken_from_first_non_empty(self):
        rows = [_row(notes=""), _row(notes="Main Line - 220"), _row(notes="Different note")]
        groups = group_by_industry(rows)
        assert groups[0]["notes"] == "Main Line - 220"

    def test_source_ref_taken_from_first_non_empty(self):
        rows = [_row(source_ref=""), _row(source_ref="pennsyrr.com")]
        groups = group_by_industry(rows)
        assert groups[0]["source_ref"] == "pennsyrr.com"

    def test_year_taken_from_first_row(self):
        rows = [_row(year="1945"), _row(year="1946")]
        groups = group_by_industry(rows)
        assert groups[0]["year"] == "1945"

    def test_car_types_merged_and_deduplicated(self):
        rows = [
            _row(car_types=["HM", "GB"]),
            _row(direction="R", commodity="ore", car_types=["GB", "XM"]),
        ]
        groups = group_by_industry(rows)
        assert set(groups[0]["car_types"]) == {"HM", "GB", "XM"}


class TestToJsonRecords:
    def test_stamps_source_and_source_file(self):
        groups = group_by_industry([_row(direction="S", commodity="coal")])
        records = to_json_records(groups, source="opsig", source_file="coal-mines-pa.csv")
        assert len(records) == 1
        r = records[0]
        assert r["source"] == "opsig"
        assert r["source_file"] == "coal-mines-pa.csv"
        assert r["name"] == "Acme Corp"
        assert r["ships"] == ["coal"]
        assert r["receives"] == []
        assert r["car_types"] == []
        assert r["source_ref"] == ""
        assert r["notes"] == ""
        assert r["year"] == "1945"


from waybill_generator.converters.opsig import parse_opsig


class TestParseOpSIGFile:
    def test_parses_txt_rows(self, tmp_path):
        content = (
            "2004\tDow\tAllyn's Point\tCT\tP&W\tS\tlatex\tbutadiene\tVH\tCH,T\r\n"
            "2004\tPeter Paul\tBeacon Falls\tCT\tGRS\tR\tcorn syrup\tcandy mfg\tH\tT\r\n"
        )
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, skipped = parse_opsig(p)
        assert len(rows) == 2
        assert rows[0].name == "Dow"
        assert rows[1].name == "Peter Paul"
        assert skipped == 0

    def test_skips_blank_name_rows_and_counts_them(self, tmp_path):
        content = "\t\t\t\t\t\t\t\t\t\r\n2004\tAcme\tCity\tPA\tPRR\tS\tcoal\t\t\tH\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Acme"
        assert skipped == 1


class _FakeSheet:
    def __init__(self, rows: list[list[str]], name: str = "Sheet1"):
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = len(rows[0]) if rows else 10
        self.name = name

    def cell_value(self, row, col):
        return self._rows[row][col]


class _FakeWorkbook:
    def __init__(self, rows: list[list[str]], extra_sheets: list["_FakeSheet"] | None = None):
        self._sheet = _FakeSheet(rows)
        self._extra_sheets = extra_sheets or []
        self.nsheets = 1 + len(self._extra_sheets)

    def sheet_by_index(self, index):
        if index == 0:
            return self._sheet
        return self._extra_sheets[index - 1]


class TestParseOpSIGXls:
    def test_parses_xls_via_xlrd(self, monkeypatch, tmp_path):
        rows_data = [
            ["ERA", "NAME", "CITY", "ST", "RR", "S/R", "COMMODITY", "STTC", "RECIP", "CONTRIB"],
            ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S", "latex", "butadiene", "", "CH,T"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Dow"
        assert rows[0].car_types == ["CH", "T"]
        assert skipped == 0

    def test_xls_integer_float_year_stringified_without_decimal(self, monkeypatch, tmp_path):
        rows_data = [
            ["ERA", "NAME", "CITY", "ST", "RR", "S/R", "COMMODITY", "STTC", "RECIP", "CONTRIB"],
            [2004.0, "Dow", "Allyn's Point", "CT", "P&W", "S", "latex", "butadiene", "", "CH,T"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert rows[0].year == "2004"

    def test_header_row_not_parsed_as_data(self, monkeypatch, tmp_path):
        rows_data = [
            ["ERA", "INDUSTRY/COMPANY NAME", "CITY", "ST", "SERVING RAILROADS", "S/R",
             "COMMODITY", "STTC", "RECIP. SWITCH.", "CONTRIBUTOR"],
            ["90", "Conagra Fertilizer", "Beamer", "AB", "CN", "S", "Ammonium nitrate", "", "", "butts"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Conagra Fertilizer"
        assert all(r.name != "INDUSTRY/COMPANY NAME" for r in rows)

    def test_11_column_dh_layout_shifts_and_tags_notes(self, monkeypatch, tmp_path):
        rows_data = [
            ["List", "Era", "Ind", "City", "St", "RR", "SR", "Comm", "STCC", "Recip", "Contrib"],
            ["C", "1996", "Sherridan Fertilizer", "Beamer", "AB", "CN", "", "Ammonium nitrate",
             "4918311", "", "spwayb"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        row = rows[0]
        assert row.year == "1996"
        assert row.name == "Sherridan Fertilizer"
        assert row.city == "Beamer"
        assert row.state == "AB"
        assert row.railroad == "CN"
        assert row.notes == "[list: C] 4918311"
        assert row.car_types == ["spwayb"]
        assert skipped == 0

    def test_warns_when_other_sheet_has_data(self, monkeypatch, tmp_path):
        header_and_row = [
            ["ERA", "NAME", "CITY", "ST", "RR", "S/R", "COMMODITY", "STTC", "RECIP", "CONTRIB"],
            ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S", "latex", "butadiene", "", "CH,T"],
        ]
        other_sheet = _FakeSheet([["x"]], name="Extra")
        monkeypatch.setattr(
            "xlrd.open_workbook",
            lambda path: _FakeWorkbook(header_and_row, extra_sheets=[other_sheet]),
        )
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        with pytest.warns(UserWarning, match="sheet 1"):
            rows, skipped = parse_opsig(p)
        assert len(rows) == 1

    def test_unexpected_column_count_warns_and_falls_back(self, monkeypatch, tmp_path):
        rows_data = [
            ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            ["2004", "Dow", "City", "CT", "P&W", "S", "latex", "note", "CH"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        with pytest.warns(UserWarning, match="expected 10 or 11 columns"):
            rows, skipped = parse_opsig(p)


from waybill_generator.converters.jbritton import parse_jbritton


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
        rows, skipped = parse_jbritton(p)
        assert len(rows) == 3
        assert rows[0].direction == "S"
        assert rows[1].direction == "R"
        assert rows[2].direction == ""
        assert skipped == 0

    def test_no_car_types(self, tmp_path):
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tsource{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, _ = parse_jbritton(p)
        assert rows[0].car_types == []

    def test_source_ref_captured(self, tmp_path):
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tpennsyrr.com CT1000{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, _ = parse_jbritton(p)
        assert rows[0].source_ref == "pennsyrr.com CT1000"

    def test_blank_name_row_skipped_and_counted(self, tmp_path):
        tabs = "\t" * 247
        content = f"1945\t\tCity\tPA\tPRR{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, skipped = parse_jbritton(p)
        assert len(rows) == 0
        assert skipped == 1


import json
from click.testing import CliRunner
from waybill_generator.cli import main


class TestConvertIndustryDbCommand:
    def _make_opsig_txt(self, industry_db: Path) -> Path:
        opsig_dir = industry_db / "opsig"
        opsig_dir.mkdir(parents=True)
        p = opsig_dir / "sample.txt"
        p.write_bytes(
            "2004\tDow\tAllyn's Point\tCT\tP&W\tS\tlatex\tbutadiene\tVH\tCH,T\r\n".encode("latin-1")
        )
        return opsig_dir

    def _make_jbritton_txt(self, industry_db: Path) -> Path:
        jbritton_dir = industry_db / "jbritton"
        jbritton_dir.mkdir(parents=True)
        tabs = "\t" * 246
        p = jbritton_dir / "sample.txt"
        p.write_bytes(
            f"1945\tStandard Novelty Works\tDuncannon\tPA\tPRR\tS\tSleds\t\tMain Line\tpennsyrr.com{tabs}\r\n".encode("latin-1")
        )
        return jbritton_dir

    def test_writes_json_for_opsig_and_jbritton(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        self._make_opsig_txt(industry_db)
        self._make_jbritton_txt(industry_db)

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output

        opsig_json = json.loads((industry_db / "opsig" / "json" / "sample.json").read_text())
        assert len(opsig_json) == 1
        assert opsig_json[0]["name"] == "Dow"
        assert opsig_json[0]["source"] == "opsig"
        assert opsig_json[0]["source_file"] == "sample.txt"

        jbritton_json = json.loads((industry_db / "jbritton" / "json" / "sample.json").read_text())
        assert len(jbritton_json) == 1
        assert jbritton_json[0]["name"] == "Standard Novelty Works"
        assert jbritton_json[0]["source"] == "jbritton"

    def test_prints_summary_with_skipped_count(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        opsig_dir = self._make_opsig_txt(industry_db)
        blank_line = "\t" * 9 + "\r\n"
        with open(opsig_dir / "sample.txt", "ab") as f:
            f.write(blank_line.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output
        assert "sample.txt" in result.output
        assert "1 rows skipped" in result.output

    def test_unrecognized_extension_warned_not_errored(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        opsig_dir = self._make_opsig_txt(industry_db)
        (opsig_dir / "notes.pdf").write_bytes(b"not a real pdf")

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output
        assert "notes.pdf" in result.output

    def test_missing_source_subfolder_skipped_silently(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        self._make_opsig_txt(industry_db)  # no jbritton/ folder created

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output

    def test_unparseable_file_reported_but_run_continues(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        opsig_dir = self._make_opsig_txt(industry_db)
        (opsig_dir / "corrupt.xls").write_bytes(b"not a real xls file")

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output
        assert "ERROR" in result.output
        assert "corrupt.xls" in result.output
        # the good file in the same folder is still converted
        assert (opsig_dir / "json" / "sample.json").exists()
