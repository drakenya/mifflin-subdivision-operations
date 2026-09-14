from dataclasses import dataclass


@dataclass
class RawRow:
    year: str
    name: str
    city: str
    state: str
    railroad: str
    direction: str        # "S", "R", or ""
    commodity: str
    notes: str
    car_types: list[str]  # raw source codes; empty when the format has no car-type column
    source_ref: str


def parse_tab_line(
    line: list[str],
    *,
    notes_col: int,
    source_ref_col: int | None,
    car_types_col: int | None,
) -> RawRow | None:
    while len(line) < 10:
        line.append("")

    name = line[1].strip()
    if not name:
        return None

    car_types = []
    if car_types_col is not None:
        car_types = [c.strip() for c in line[car_types_col].split(",") if c.strip()]

    source_ref = line[source_ref_col].strip() if source_ref_col is not None else ""

    return RawRow(
        year=line[0].strip(),
        name=name,
        city=line[2].strip(),
        state=line[3].strip(),
        railroad=line[4].strip(),
        direction=line[5].strip(),
        commodity=line[6].strip(),
        notes=line[notes_col].strip(),
        car_types=car_types,
        source_ref=source_ref,
    )


def group_by_industry(rows: list[RawRow]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for row in rows:
        key = (row.name.strip(), row.city.strip(), row.state.strip(), row.railroad.strip())
        if key not in groups:
            groups[key] = {
                "name": row.name.strip(),
                "city": row.city.strip(),
                "state": row.state.strip(),
                "railroad": row.railroad.strip(),
                "year": row.year.strip(),
                "ships": [],
                "receives": [],
                "notes": "",
                "car_types": [],
                "source_ref": "",
            }
        g = groups[key]

        commodity = row.commodity.strip()
        direction = row.direction.strip().upper()
        if commodity:
            if direction == "S":
                if commodity not in g["ships"]:
                    g["ships"].append(commodity)
            elif direction == "R":
                if commodity not in g["receives"]:
                    g["receives"].append(commodity)
            else:
                if commodity not in g["ships"]:
                    g["ships"].append(commodity)
                if commodity not in g["receives"]:
                    g["receives"].append(commodity)

        if not g["notes"] and row.notes.strip():
            g["notes"] = row.notes.strip()
        if not g["source_ref"] and row.source_ref.strip():
            g["source_ref"] = row.source_ref.strip()

        for ct in row.car_types:
            ct = ct.strip()
            if ct and ct not in g["car_types"]:
                g["car_types"].append(ct)

    return list(groups.values())


def to_json_records(groups: list[dict], source: str, source_file: str) -> list[dict]:
    records = []
    for g in groups:
        records.append({
            "name": g["name"],
            "city": g["city"],
            "state": g["state"],
            "railroad": g["railroad"],
            "year": g["year"],
            "ships": g["ships"],
            "receives": g["receives"],
            "car_types": g["car_types"],
            "source_ref": g["source_ref"],
            "notes": g["notes"],
            "source": source,
            "source_file": source_file,
        })
    return records
