from abc import ABC, abstractmethod
from waybill_generator.models.car import Car
from waybill_generator.models.location import Location
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.waybill import WaybillBase


class BaseRepository(ABC):
    @abstractmethod
    def get_cars(self) -> list[Car]: ...

    @abstractmethod
    def get_car(self, id: str) -> Car: ...

    @abstractmethod
    def get_locations(self) -> list[Location]: ...

    @abstractmethod
    def get_location(self, id: str) -> Location: ...

    @abstractmethod
    def get_commodities(self) -> list[Commodity]: ...

    @abstractmethod
    def get_commodity(self, id: str) -> Commodity: ...

    @abstractmethod
    def get_waybills(self) -> list[WaybillBase]: ...

    @abstractmethod
    def get_waybill(self, id: str) -> WaybillBase: ...
