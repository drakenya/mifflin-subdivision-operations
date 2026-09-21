from waybill_generator.models.car import Car
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.location import Industry, Location
from waybill_generator.models.railroad import Railroad
from waybill_generator.web.references import (
    NOT_REFERENCES,
    REFERENCES,
    SUGGESTIONS,
    WAYBILL_CLASSES,
    iter_refs,
)
from waybill_generator.web.working_copy import KINDS, WorkingCopy


def test_every_waybill_type_is_registered():
    assert set(WAYBILL_CLASSES) == {
        "LOADED", "EMPTY", "DEADHEAD", "MOW", "HOLD", "BAD_ORDER",
        "STOP_OFF", "TEMPORARY", "PERISHABLE", "LIVESTOCK",
    }


def test_every_id_like_field_is_classified():
    """A new *_id field (or routing list) must be added to REFERENCES / NOT_REFERENCES / SUGGESTIONS."""
    for cls in [Car, Commodity, Railroad, Location, Industry, *WAYBILL_CLASSES.values()]:
        for name in cls.model_fields:
            key = (cls.__name__, name)
            if name != "id" and name.endswith("_id"):
                assert key in REFERENCES or key in NOT_REFERENCES, f"unclassified id field {key}"
            if name == "routing" and cls.__name__ != "TemporaryWaybill":
                assert key in SUGGESTIONS, f"unclassified list field {key}"


def test_iter_refs_covers_waybills_and_nested_industries(data_dir):
    wc = WorkingCopy(data_dir)
    refs = list(iter_refs({kind: {r.id: r for r in wc.records(kind)} for kind in KINDS}))
    assert ("waybills", "waybill-1", "shipper_id", "industries", "LEW-GRAIN") in refs
    assert ("waybills", "hold-1", "industry_id", "industries", "LEW-GRAIN") in refs
    assert ("industries", "LEW-GRAIN", "ships", "commodities", "grain") in refs
    assert ("waybills", "waybill-1", "originating_railroad_id", "railroads", "PRR") in refs
    assert ("cars", "PRR-12345", "aar_code", "aar_codes", "XM") in refs
    # free-text fields are not references
    assert not any(r.field in ("routing", "stop_at") for r in refs)
