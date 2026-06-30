import csv
from pathlib import Path
from waybill_generator.importers.base import ImportedRow


def parse_jbritton(filepath: Path) -> list[ImportedRow]:
    rows = []
    with open(filepath, encoding="latin-1", newline="") as f:
        for line in csv.reader(f, delimiter="\t"):
            row = _parse_line(line)
            if row:
                rows.append(row)
    return rows


def _parse_line(line: list[str]) -> ImportedRow | None:
    while len(line) < 10:
        line.append("")
    name = line[1].strip()
    if not name:
        return None
    return ImportedRow(
        year=line[0].strip(),
        name=name,
        city=line[2].strip(),
        state=line[3].strip(),
        railroad=line[4].strip(),
        direction=line[5].strip(),
        commodity=line[6].strip(),
        notes=line[8].strip(),
        car_types=[],
        source_ref=line[9].strip(),
    )
