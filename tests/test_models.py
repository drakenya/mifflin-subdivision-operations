import pytest
from pydantic import ValidationError, TypeAdapter
from waybill_generator.models.car import Car
from waybill_generator.models.location import Location, Industry
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.waybill import (
    WaybillType, LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill, Waybill,
)

_waybill_adapter = TypeAdapter(Waybill)


class TestCar:
    def test_basic_construction(self):
        car = Car(id="PRR-12345", road="PRR", car_number="12345", aar_code="XM", capacity_tons=50)
        assert car.id == "PRR-12345"
        assert car.active is True
        assert car.capacity_cuft is None

    def test_inactive_car(self):
        car = Car(id="NYC-99", road="NYC", car_number="99", aar_code="XM", capacity_tons=70, active=False)
        assert car.active is False

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Car(id="PRR-1", road="PRR", car_number="1", aar_code="XM")  # missing capacity_tons


class TestLocation:
    def test_location_with_industries(self):
        loc = Location(
            id="LEW", name="Lewistown", subdivision="Mifflin",
            industries=[
                Industry(
                    id="LEW-GRAIN", name="Grain Elevator", location_id="LEW",
                    ships=["grain"],
                )
            ],
        )
        assert len(loc.industries) == 1
        assert loc.industries[0].ships == ["grain"]

    def test_location_defaults(self):
        loc = Location(id="ALT", name="Altoona")
        assert loc.industries == []
        assert loc.subdivision is None


class TestCommodity:
    def test_basic_construction(self):
        c = Commodity(id="grain", name="Grain", acceptable_car_types=["XM"])
        assert c.aar_code is None
        assert c.acceptable_car_types == ["XM"]


class TestWaybillDiscrimination:
    def test_loaded_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "w-1", "waybill_type": "LOADED", "originating_railroad_id": "PRR",
            "commodity_id": "grain", "shipper_id": "LEW-GRAIN", "consignee_id": "ALT-MILL",
        })
        assert isinstance(w, LoadedWaybill)
        assert w.routing == []
        assert w.originating_railroad_id == "PRR"

    def test_empty_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "e-1", "waybill_type": "EMPTY", "originating_railroad_id": "PRR",
            "from_location_id": "ALT", "to_location_id": "LEW",
        })
        assert isinstance(w, EmptyWaybill)
        assert w.spot is None
        assert w.shipper_ordered_by is None

    def test_empty_waybill_optional_fields(self):
        w = _waybill_adapter.validate_python({
            "id": "e-2", "waybill_type": "EMPTY", "originating_railroad_id": "PRR",
            "from_location_id": "ALT", "to_location_id": "LEW",
            "spot": "Track 4", "shipper_ordered_by": "Standard Oil",
        })
        assert w.spot == "Track 4"
        assert w.shipper_ordered_by == "Standard Oil"

    def test_deadhead_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "d-1", "waybill_type": "DEADHEAD", "originating_railroad_id": "PRR",
            "from_location_id": "PHL", "to_location_id": "PGH",
            "consist_note": "PRR 4100",
        })
        assert isinstance(w, DeadheadWaybill)

    def test_mow_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "m-1", "waybill_type": "MOW", "originating_railroad_id": "PRR",
            "commodity_desc": "Ballast", "from_location_id": "ALT", "to_location_id": "LEW",
        })
        assert isinstance(w, MoWWaybill)

    def test_hold_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "h-1", "waybill_type": "HOLD", "originating_railroad_id": "PRR",
            "industry_id": "LEW-GRAIN", "waiting_for": "Load order",
        })
        assert isinstance(w, HoldWaybill)

    def test_bad_order_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "b-1", "waybill_type": "BAD_ORDER", "originating_railroad_id": "PRR",
            "from_location_id": "LEW", "shop_location_id": "ALT",
        })
        assert isinstance(w, BadOrderWaybill)
        assert w.defect is None

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            _waybill_adapter.validate_python({
                "id": "x-1", "waybill_type": "UNKNOWN", "originating_railroad_id": "PRR",
            })


from waybill_generator.models.railroad import Railroad


class TestRailroad:
    def test_basic_construction(self):
        r = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")
        assert r.id == "PRR"
        assert r.name == "Pennsylvania Railroad"
        assert r.form_number == "Form 1304"
        assert r.icon is None

    def test_with_icon(self):
        r = Railroad(id="NYC", name="New York Central", form_number="Form 200", icon="assets/nyc.png")
        assert r.icon == "assets/nyc.png"

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Railroad(id="PRR", name="Pennsylvania Railroad")
