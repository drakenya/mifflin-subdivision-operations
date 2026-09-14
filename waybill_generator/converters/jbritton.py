import csv
from pathlib import Path
from waybill_generator.converters.base import RawRow, parse_tab_line


def parse_jbritton(filepath: Path) -> tuple[list[RawRow], int]:
    rows = []
    skipped = 0
    with open(filepath, encoding="latin-1", newline="") as f:
        for line in csv.reader(f, delimiter="\t"):
            row = parse_tab_line(line, notes_col=8, source_ref_col=9, car_types_col=None)
            if row:
                rows.append(row)
            else:
                skipped += 1
    return rows, skipped
