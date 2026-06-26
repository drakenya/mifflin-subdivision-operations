from pathlib import Path
import yaml
from pydantic import TypeAdapter
from waybill_generator.repository.base import BaseRepository
from waybill_generator.models.car import Car
from waybill_generator.models.location import Location, Industry
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.waybill import WaybillBase, Waybill
from waybill_generator.models.railroad import Railroad

_waybill_adapter = TypeAdapter(Waybill)


class YamlRepository(BaseRepository):
    def __init__(self, data_path: str | Path) -> None:
        self._path = Path(data_path)
        self._cars: dict[str, Car] | None = None
        self._locations: dict[str, Location] | None = None
        self._commodities: dict[str, Commodity] | None = None
        self._waybills: dict[str, WaybillBase] | None = None
        self._railroads: dict[str, Railroad] | None = None

    def _load(self, filename: str) -> list[dict]:
        return yaml.safe_load((self._path / filename).read_text()) or []

    def _ensure_cars(self) -> dict[str, Car]:
        if self._cars is None:
            self._cars = {c.id: c for c in [Car(**r) for r in self._load("cars.yaml")]}
        return self._cars

    def _ensure_locations(self) -> dict[str, Location]:
        if self._locations is None:
            self._locations = {
                loc.id: loc for loc in [Location(**r) for r in self._load("locations.yaml")]
            }
        return self._locations

    def _ensure_commodities(self) -> dict[str, Commodity]:
        if self._commodities is None:
            self._commodities = {
                c.id: c for c in [Commodity(**r) for r in self._load("commodities.yaml")]
            }
        return self._commodities

    def _ensure_waybills(self) -> dict[str, WaybillBase]:
        if self._waybills is None:
            self._waybills = {
                w.id: w
                for w in [_waybill_adapter.validate_python(r) for r in self._load("waybills.yaml")]
            }
        return self._waybills

    def get_cars(self) -> list[Car]:
        return list(self._ensure_cars().values())

    def get_car(self, id: str) -> Car:
        cars = self._ensure_cars()
        if id not in cars:
            raise KeyError(f"Car not found: {id!r}")
        return cars[id]

    def get_locations(self) -> list[Location]:
        return list(self._ensure_locations().values())

    def get_location(self, id: str) -> Location:
        locs = self._ensure_locations()
        if id not in locs:
            raise KeyError(f"Location not found: {id!r}")
        return locs[id]

    def get_commodities(self) -> list[Commodity]:
        return list(self._ensure_commodities().values())

    def get_commodity(self, id: str) -> Commodity:
        commodities = self._ensure_commodities()
        if id not in commodities:
            raise KeyError(f"Commodity not found: {id!r}")
        return commodities[id]

    def get_waybills(self) -> list[WaybillBase]:
        return list(self._ensure_waybills().values())

    def get_waybill(self, id: str) -> WaybillBase:
        waybills = self._ensure_waybills()
        if id not in waybills:
            raise KeyError(f"Waybill not found: {id!r}")
        return waybills[id]

    def _ensure_railroads(self) -> dict[str, Railroad]:
        if self._railroads is None:
            self._railroads = {
                r.id: r for r in [Railroad(**row) for row in self._load("railroads.yaml")]
            }
        return self._railroads

    def get_railroads(self) -> list[Railroad]:
        return list(self._ensure_railroads().values())

    def get_railroad(self, id: str) -> Railroad:
        railroads = self._ensure_railroads()
        if id not in railroads:
            raise KeyError(f"Railroad not found: {id!r}")
        return railroads[id]

    def get_industry(self, id: str) -> Industry:
        for loc in self._ensure_locations().values():
            for industry in loc.industries:
                if industry.id == id:
                    return industry
        raise KeyError(f"Industry not found: {id!r}")
