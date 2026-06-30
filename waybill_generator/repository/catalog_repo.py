from pathlib import Path
import yaml
from waybill_generator.models.catalog import CatalogIndustry


class CatalogRepository:
    def __init__(self, catalog_path: str | Path) -> None:
        self._path = Path(catalog_path)
        self._entries: dict[str, CatalogIndustry] | None = None

    def _ensure_entries(self) -> dict[str, CatalogIndustry]:
        if self._entries is None:
            raw = yaml.safe_load(self._path.read_text()) or []
            self._entries = {e.id: e for e in [CatalogIndustry(**r) for r in raw]}
        return self._entries

    def get(self, id: str) -> CatalogIndustry:
        entries = self._ensure_entries()
        if id not in entries:
            raise KeyError(f"Catalog entry not found: {id!r}")
        return entries[id]

    def search(
        self,
        keyword: str | None = None,
        commodity: str | None = None,
        car_type: str | None = None,
        railroad: str | None = None,
        ships: bool = False,
        receives: bool = False,
        source: str | None = None,
        limit: int = 20,
    ) -> list[CatalogIndustry]:
        results = list(self._ensure_entries().values())

        if keyword:
            kw = keyword.lower()
            results = [
                e for e in results
                if kw in e.name.lower()
                or kw in e.city.lower()
                or (e.notes and kw in e.notes.lower())
            ]

        if commodity:
            comm = commodity.lower()
            if ships:
                results = [e for e in results if any(comm in s.lower() for s in e.ships)]
            elif receives:
                results = [e for e in results if any(comm in r.lower() for r in e.receives)]
            else:
                results = [
                    e for e in results
                    if any(comm in s.lower() for s in e.ships)
                    or any(comm in r.lower() for r in e.receives)
                ]

        if car_type:
            ct = car_type.upper()
            results = [e for e in results if ct in [c.upper() for c in e.car_types]]

        if railroad:
            rr = railroad.upper()
            results = [e for e in results if e.railroad_id and e.railroad_id.upper() == rr]

        if source:
            results = [e for e in results if e.source.lower() == source.lower()]

        return results[:limit]

    def replace_from_source(
        self,
        source_file: str,
        new_entries: list[CatalogIndustry],
    ) -> tuple[int, int]:
        raw = yaml.safe_load(self._path.read_text()) if self._path.exists() else None
        existing = [CatalogIndustry(**r) for r in (raw or [])]

        old_ids = {e.id for e in existing if e.source_file == source_file}
        new_ids = {e.id for e in new_entries}

        replaced = len(old_ids & new_ids)
        added = len(new_ids - old_ids)

        kept = [e for e in existing if e.source_file != source_file]
        merged = kept + new_entries

        self._path.write_text(
            yaml.dump(
                [e.model_dump(exclude_none=True) for e in merged],
                default_flow_style=False,
                allow_unicode=True,
            )
        )
        self._entries = None
        return replaced, added
