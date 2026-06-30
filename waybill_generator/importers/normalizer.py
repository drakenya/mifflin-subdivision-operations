import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from waybill_generator.models.catalog import CatalogIndustry
from waybill_generator.importers.base import make_catalog_id


@dataclass
class NormReport:
    map_count: int = 0
    auto_count: int = 0
    free_count: int = 0
    unmatched: dict[str, int] = field(default_factory=dict)
    unknown_car_codes: list[str] = field(default_factory=list)


def load_commodity_map(path: Path) -> dict[str, str | None]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or []
    result = {}
    for entry in raw:
        key = entry.get("source_text")
        if not key:
            continue
        result[key.lower()] = entry.get("commodity_id")
    return result


def build_auto_map(commodities_path: Path) -> dict[str, str]:
    if not commodities_path.exists():
        return {}
    raw = yaml.safe_load(commodities_path.read_text()) or []
    return {c["name"].lower(): c["id"] for c in raw}


def load_opsig_car_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    return {k.upper(): v for k, v in raw.items()}


def _normalize_commodity(
    source_text: str,
    commodity_map: dict[str, str | None],
    auto_map: dict[str, str],
) -> tuple[str, str]:
    lower = source_text.lower()
    if lower in commodity_map:
        mapped = commodity_map[lower]
        return (source_text if mapped is None else mapped, "map")
    for name, cid in auto_map.items():
        if name in lower or re.search(r'\b' + re.escape(lower) + r'\b', name):
            return (cid, "auto")
    return (source_text, "free")


def normalize_entries(
    grouped: list[dict],
    source: str,
    source_file: str,
    commodity_map_path: Path,
    opsig_car_map_path: Path,
    commodities_path: Path,
) -> tuple[list[CatalogIndustry], NormReport]:
    commodity_map = load_commodity_map(commodity_map_path)
    auto_map = build_auto_map(commodities_path)
    opsig_car_map = load_opsig_car_map(opsig_car_map_path)
    raw_commodities = (yaml.safe_load(commodities_path.read_text()) or []) if commodities_path.exists() else []
    commodities_by_id = {c["id"]: c for c in raw_commodities}

    report = NormReport()
    entries = []

    for g in grouped:
        norm_ships, resolved_ship_ids, ship_best = _normalize_list(
            g["ships"], commodity_map, auto_map
        )
        norm_receives, resolved_recv_ids, recv_best = _normalize_list(
            g["receives"], commodity_map, auto_map
        )

        best = "free"
        for b in [ship_best, recv_best]:
            if b == "map":
                best = "map"
                break
            if b == "auto":
                best = "auto"
        if best == "map":
            report.map_count += 1
        elif best == "auto":
            report.auto_count += 1
        else:
            report.free_count += 1

        all_source = list(dict.fromkeys(g["ships"] + g["receives"]))
        for commodity in all_source:
            if not commodity:
                continue
            lower = commodity.lower()
            if lower in commodity_map and commodity_map[lower] is None:
                continue
            _, mt = _normalize_commodity(commodity, commodity_map, auto_map)
            if mt == "free":
                report.unmatched[commodity] = report.unmatched.get(commodity, 0) + 1

        resolved_ids = list(dict.fromkeys(resolved_ship_ids + resolved_recv_ids))
        if source == "opsig" and g["raw_car_types"]:
            car_types = []
            for code in g["raw_car_types"]:
                aar = opsig_car_map.get(code.upper())
                if aar:
                    if aar not in car_types:
                        car_types.append(aar)
                elif code not in report.unknown_car_codes:
                    report.unknown_car_codes.append(code)
        else:
            car_types = []
            for cid in resolved_ids:
                if cid in commodities_by_id:
                    for ct in commodities_by_id[cid].get("acceptable_car_types", []):
                        if ct not in car_types:
                            car_types.append(ct)

        entries.append(CatalogIndustry(
            id=make_catalog_id(source_file, g["name"], g["city"], g["state"], g["railroad"]),
            name=g["name"],
            city=g["city"],
            state=g["state"],
            railroad_id=g["railroad"] or None,
            source=source,
            source_file=source_file,
            source_ref=g["source_ref"] or None,
            ships=norm_ships,
            receives=norm_receives,
            car_types=car_types,
            notes=g["notes"] or None,
        ))

    return entries, report


def _normalize_list(
    commodities: list[str],
    commodity_map: dict[str, str | None],
    auto_map: dict[str, str],
) -> tuple[list[str], list[str], str]:
    """Returns (normalized_list, resolved_ids, best_match_type)."""
    normalized = []
    resolved_ids = []
    best = "free"
    for commodity in commodities:
        if not commodity:
            continue
        norm, mt = _normalize_commodity(commodity, commodity_map, auto_map)
        normalized.append(norm)
        if mt == "map":
            best = "map"
            mapped_id = commodity_map.get(commodity.lower())
            if mapped_id is not None and mapped_id not in resolved_ids:
                resolved_ids.append(mapped_id)
        elif mt == "auto":
            if best == "free":
                best = "auto"
            if norm not in resolved_ids:
                resolved_ids.append(norm)
    return normalized, resolved_ids, best
