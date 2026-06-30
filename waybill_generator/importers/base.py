import hashlib
from dataclasses import dataclass


@dataclass
class ImportedRow:
    year: str
    name: str
    city: str
    state: str
    railroad: str
    direction: str        # "S", "R", or ""
    commodity: str
    notes: str
    car_types: list[str]  # raw source codes; empty for JBritton
    source_ref: str


def group_rows(rows: list[ImportedRow]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for row in rows:
        key = (row.name.strip(), row.city.strip(), row.state.strip(), row.railroad.strip())
        if key not in groups:
            groups[key] = {
                "name": row.name.strip(),
                "city": row.city.strip(),
                "state": row.state.strip(),
                "railroad": row.railroad.strip(),
                "ships": [],
                "receives": [],
                "notes": "",
                "raw_car_types": [],
                "source_ref": row.source_ref.strip(),
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
        for ct in row.car_types:
            ct = ct.strip()
            if ct and ct not in g["raw_car_types"]:
                g["raw_car_types"].append(ct)
    return list(groups.values())


def make_catalog_id(source_file: str, name: str, city: str, state: str, railroad: str) -> str:
    key = f"{source_file}|{name}|{city}|{state}|{railroad}"
    return "cat-" + hashlib.sha256(key.encode()).hexdigest()[:8]
