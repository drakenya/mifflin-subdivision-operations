from waybill_generator.models.car import Car
from waybill_generator.models.location import Industry
from waybill_generator.models.waybill import LoadedWaybill, TemporaryWaybill
from waybill_generator.web.forms import (
    build_fields,
    build_model,
    build_options,
    initial_values,
    parse_form,
)
from waybill_generator.web.references import REFERENCES, WAYBILL_CLASSES
from waybill_generator.web.working_copy import WorkingCopy


class FakeForm(dict):
    """Just enough of Starlette's FormData for parse_form."""

    def getlist(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else [value]


def fields_by_name(model_cls, data_dir, values=None, errors=None, editing=False):
    options = build_options(WorkingCopy(data_dir))
    return {f.name: f for f in build_fields(model_cls, values or {}, errors or {}, options, editing=editing)}


def test_build_options_has_searchable_context(data_dir):
    options = build_options(WorkingCopy(data_dir))
    industry = next(o for o in options["industries"] if o["value"] == "LEW-GRAIN")
    assert industry["text"] == "Lewistown Grain Elevator"
    assert industry["meta"] == "LEW-GRAIN · Lewistown, PA · track 1"
    assert industry["ships"] == "grain" and industry["receives"] == ""
    assert next(o for o in options["commodities"] if o["value"] == "coal")["meta"] == "coal · AAR 01210 · cars: HM, GB"
    assert {"value": "XM", "text": "XM — Box Car", "meta": ""} in options["aar_codes"]
    assert options["railroads"] == [{"value": "PRR", "text": "Pennsylvania Railroad", "meta": "PRR"}]
    assert {o["value"] for o in options["locations"]} == {"LEW", "ALT"}


def test_every_waybill_type_builds_a_form_with_pickers_for_its_references(data_dir):
    options = build_options(WorkingCopy(data_dir))
    for wtype, cls in WAYBILL_CLASSES.items():
        fields = build_fields(cls, initial_values(cls), {}, options, editing=False)
        names = {f.name for f in fields}
        assert "id" in names and "waybill_type" not in names, wtype
        for f in fields:
            if (cls.__name__, f.name) in REFERENCES:
                assert f.kind in ("select", "multiselect"), (wtype, f.name)


def test_loaded_form_hides_display_only_fields_and_ranks_industries(data_dir):
    fields = fields_by_name(LoadedWaybill, data_dir)
    assert "to_city" not in fields and "shipper_name" not in fields
    assert fields["shipper_id"].rank == ("commodity_id", "ships")
    assert fields["consignee_id"].rank == ("commodity_id", "receives")
    assert fields["routing"].kind == "tags" and fields["notes"].kind == "textarea"
    assert fields["commodity_id"].required and not fields["stop_at"].required


def test_temporary_waybill_locations_are_free_text(data_dir):
    fields = fields_by_name(TemporaryWaybill, data_dir)
    assert fields["from_location_id"].kind == "text" and fields["to_location_id"].kind == "text"


def test_a_value_missing_from_the_data_stays_selectable(data_dir):
    fields = fields_by_name(LoadedWaybill, data_dir, values={"commodity_id": "produce", "routing": ["NYC"]})
    assert {"value": "produce", "text": "produce", "meta": "not in data"} in fields["commodity_id"].options
    assert fields["commodity_id"].selected == {"produce"}
    assert {"value": "NYC", "text": "NYC", "meta": "not in data"} in fields["routing"].options


def test_id_is_read_only_only_when_editing(data_dir):
    assert fields_by_name(Car, data_dir, editing=True)["id"].readonly
    assert not fields_by_name(Car, data_dir, editing=False)["id"].readonly


def test_industry_form_hides_its_parent_location(data_dir):
    fields = fields_by_name(Industry, data_dir)
    assert "location_id" not in fields and fields["ships"].kind == "multiselect"


def test_initial_values_use_model_defaults():
    assert initial_values(Car) == {"active": True}
    assert initial_values(LoadedWaybill)["routing"] == []


def test_parse_form_reports_blank_required_and_bad_numbers():
    values, errors = parse_form(Car, FakeForm({"road": "PRR", "car_number": "1", "aar_code": "XM",
                                               "capacity_tons": "", "capacity_cuft": "abc", "length_ft": "40"}))
    assert errors == {"id": "Required", "capacity_tons": "Required", "capacity_cuft": "Must be a whole number"}
    assert values["length_ft"] == 40 and values["notes"] is None and values["active"] is False


def test_parse_form_reads_checkboxes_lists_and_strips_blanks():
    values, errors = parse_form(Industry, FakeForm({"id": " X ", "name": "Xco", "ships": ["grain", " ", "coal"], "track": ""}))
    assert errors == {} and values["id"] == "X"
    assert values["ships"] == ["grain", "coal"] and values["receives"] == [] and values["track"] is None
    values, _ = parse_form(Car, FakeForm({"active": "on"}))
    assert values["active"] is True


def test_build_model_maps_pydantic_errors_to_fields():
    model, errors = build_model(Car, {"id": "a", "road": "PRR", "car_number": "1", "aar_code": "XM", "capacity_tons": "x"})
    assert model is None and "capacity_tons" in errors
    model, errors = build_model(Car, {"id": "a", "road": "PRR", "car_number": "1", "aar_code": "XM", "capacity_tons": 50})
    assert errors == {} and model.capacity_tons == 50
