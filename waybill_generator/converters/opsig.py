import csv
import warnings
from pathlib import Path
from waybill_generator.converters.base import RawRow, parse_tab_line

# OpSIG's real column 7 is STTC (a shipping commodity code) and column 9 is
# CONTRIBUTOR (the initials of whoever submitted the row to OpSIG) — not
# "notes"/"car_types" as these field names suggest. This mismapping is
# inherited from the pre-existing (and already-reverted) importer this
# converter replaces, and was deliberately left as-is rather than fixed:
# see docs/superpowers/specs/2026-09-13-industry-db-json-conversion-design.md
# ("Known Caveats") for the full rationale.
_OPSIG_NOTES_COL = 7
_OPSIG_CAR_TYPES_COL = 9


def parse_opsig(filepath: Path) -> tuple[list[RawRow], int]:
    if filepath.suffix.lower() == ".xls":
        return _parse_xls(filepath)
    return _parse_txt(filepath)


def _parse_txt(filepath: Path) -> tuple[list[RawRow], int]:
    rows = []
    skipped = 0
    with open(filepath, encoding="latin-1", newline="") as f:
        for line in csv.reader(f, delimiter="\t"):
            row = parse_tab_line(
                line, notes_col=_OPSIG_NOTES_COL, source_ref_col=None,
                car_types_col=_OPSIG_CAR_TYPES_COL,
            )
            if row:
                rows.append(row)
            else:
                skipped += 1
    return rows, skipped


def _cell_to_str(value) -> str:
    """Convert Excel cell value to string, handling floats that represent whole numbers."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_xls(filepath: Path) -> tuple[list[RawRow], int]:
    import xlrd
    wb = xlrd.open_workbook(str(filepath))
    ws = wb.sheet_by_index(0)

    # Some real OpSIG .xls files (e.g. DHCanada.xls) have multiple sheets.
    # Only sheet 0 is read; warn if another sheet holds data we're silently
    # skipping, since that's exactly the kind of unvalidated-format
    # assumption that caused the 10-vs-11-column bug below.
    for i in range(1, wb.nsheets):
        other = wb.sheet_by_index(i)
        if other.nrows > 0:
            warnings.warn(
                f"{filepath.name}: workbook has {wb.nsheets} sheets; only "
                f"sheet 0 ({ws.name!r}) is read, but sheet {i} ({other.name!r}) "
                f"has {other.nrows} rows that will NOT be converted",
                stacklevel=2,
            )

    rows = []
    skipped = 0
    # DHCanada.xls / DHWest.xls have an extra leading "List" column (values
    # are only ever "C" or "W", a region tag) that OpSigCANADA.xls /
    # OpSigWEST.xls don't have, shifting every other column right by one.
    # DHWest.xls is a known full duplicate of DHCanada.xls's "W"-tagged rows
    # (see the design spec) — downstream consumers combining both files'
    # JSON output should dedupe on (name, city, state, railroad).
    if ws.ncols == 11:
        col_offset = 1
    elif ws.ncols == 10:
        col_offset = 0
    else:
        warnings.warn(
            f"{filepath.name}: expected 10 or 11 columns, found {ws.ncols}; "
            "falling back to the 10-column layout, which may misalign fields",
            stacklevel=2,
        )
        col_offset = 0
    has_list_column = col_offset == 1

    for i in range(1, ws.nrows):  # row 0 is a header in every real .xls source file
        list_tag = _cell_to_str(ws.cell_value(i, 0)) if has_list_column else ""
        line = [
            _cell_to_str(ws.cell_value(i, col_offset + j)) if (col_offset + j) < ws.ncols else ""
            for j in range(10)
        ]
        row = parse_tab_line(
            line, notes_col=_OPSIG_NOTES_COL, source_ref_col=None,
            car_types_col=_OPSIG_CAR_TYPES_COL,
        )
        if row is None:
            skipped += 1
            continue
        if list_tag:
            row.notes = f"[list: {list_tag}] {row.notes}".strip()
        rows.append(row)
    return rows, skipped
