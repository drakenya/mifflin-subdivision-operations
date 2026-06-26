import pytest
from pathlib import Path
from waybill_generator.repository.yaml_repo import YamlRepository
from waybill_generator.models.waybill import LoadedWaybill, EmptyWaybill, BadOrderWaybill

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo():
    return YamlRepository(FIXTURES)


class TestYamlRepositoryCars:
    def test_get_cars_returns_all(self, repo):
        cars = repo.get_cars()
        assert len(cars) == 2

    def test_get_car_by_id(self, repo):
        car = repo.get_car("PRR-12345")
        assert car.road == "PRR"
        assert car.car_type == "X29"
        assert car.capacity_tons == 50

    def test_get_car_missing_raises(self, repo):
        with pytest.raises(KeyError):
            repo.get_car("MISSING-0")

    def test_inactive_car_included(self, repo):
        car = repo.get_car("PRR-67890")
        assert car.active is False


class TestYamlRepositoryLocations:
    def test_get_locations_returns_all(self, repo):
        locs = repo.get_locations()
        assert len(locs) == 2

    def test_get_location_with_industries(self, repo):
        loc = repo.get_location("LEW")
        assert loc.name == "Lewistown"
        assert len(loc.industries) == 1
        assert loc.industries[0].id == "LEW-GRAIN"

    def test_get_location_missing_raises(self, repo):
        with pytest.raises(KeyError):
            repo.get_location("MISSING")


class TestYamlRepositoryCommodities:
    def test_get_commodities(self, repo):
        commodities = repo.get_commodities()
        assert len(commodities) == 2

    def test_get_commodity_by_id(self, repo):
        c = repo.get_commodity("grain")
        assert c.name == "Grain"


class TestYamlRepositoryWaybills:
    def test_get_waybills_returns_all(self, repo):
        waybills = repo.get_waybills()
        assert len(waybills) == 6  # was 3

    def test_loaded_waybill_deserialized(self, repo):
        w = repo.get_waybill("waybill-1")
        assert isinstance(w, LoadedWaybill)
        assert w.commodity_id == "grain"

    def test_empty_waybill_deserialized(self, repo):
        w = repo.get_waybill("empty-1")
        assert isinstance(w, EmptyWaybill)

    def test_bad_order_waybill_deserialized(self, repo):
        w = repo.get_waybill("badorder-1")
        assert isinstance(w, BadOrderWaybill)
        assert w.defect == "Broken coupler"

    def test_get_waybill_missing_raises(self, repo):
        with pytest.raises(KeyError):
            repo.get_waybill("MISSING")

    def test_deadhead_waybill_deserialized(self, repo):
        from waybill_generator.models.waybill import DeadheadWaybill
        w = repo.get_waybill("deadhead-1")
        assert isinstance(w, DeadheadWaybill)

    def test_mow_waybill_deserialized(self, repo):
        from waybill_generator.models.waybill import MoWWaybill
        w = repo.get_waybill("mow-1")
        assert isinstance(w, MoWWaybill)

    def test_hold_waybill_deserialized(self, repo):
        from waybill_generator.models.waybill import HoldWaybill
        w = repo.get_waybill("hold-1")
        assert isinstance(w, HoldWaybill)
