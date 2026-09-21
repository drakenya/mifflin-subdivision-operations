import pytest

from tests.web.conftest import CAR_FORM, follow


def test_new_waybill_form_suggests_the_next_id_and_is_wired_for_type_swaps(client):
    page = client.get("/waybills/new").text
    assert 'value="waybill-2"' in page                       # fixtures hold waybill-1 only
    assert 'hx-get="/waybills/fields"' in page and 'name="waybill_type"' in page
    assert "data-picker" in page and 'data-rank-field="commodity_id"' in page
    assert "commodity_id" in client.get("/waybills/new?waybill_type=LOADED").text
    assert "from_location_id" in client.get("/waybills/new?waybill_type=EMPTY").text


def test_type_fragment_swaps_fields_and_keeps_typed_values(client):
    fragment = client.get("/waybills/fields?waybill_type=EMPTY&id=waybill-9&notes=hello")
    assert fragment.status_code == 200 and "<html" not in fragment.text
    assert "from_location_id" in fragment.text and "commodity_id" not in fragment.text
    assert 'value="waybill-9"' in fragment.text and "hello" in fragment.text
    assert client.get("/waybills/fields?waybill_type=NOPE").status_code == 422
    assert client.get("/cars/fields").status_code == 404


def test_create_waybill_is_staged_and_marked_new(client):
    response = client.post("/waybills/new", data={
        "waybill_type": "LOADED", "id": "waybill-2", "originating_railroad_id": "PRR", "commodity_id": "coal",
        "shipper_id": "ALT-SHOP", "consignee_id": "LEW-GRAIN", "routing": ["ALT", "LJ"]})
    page = follow(client, response).text
    assert "Applied waybill waybill-2" in page and "1 unsaved change" in page and "NEW" in page
    assert client.get("/waybills/waybill-2").status_code == 200


def test_create_waybill_reports_missing_required_and_duplicate_ids(client):
    response = client.post("/waybills/new", data={"waybill_type": "LOADED", "id": "waybill-2",
                                                   "originating_railroad_id": "PRR", "commodity_id": "coal",
                                                   "shipper_id": "ALT-SHOP"})
    assert response.status_code == 422 and "Required" in response.text and 'value="waybill-2"' in response.text
    response = client.post("/waybills/new", data={"waybill_type": "HOLD", "id": "waybill-1",
                                                   "originating_railroad_id": "PRR", "industry_id": "LEW-GRAIN",
                                                   "waiting_for": "x"})
    assert response.status_code == 422 and "Already exists" in response.text
    assert client.post("/waybills/new", data={"waybill_type": "NOPE"}).status_code == 422


def test_editing_a_waybill_keeps_its_type_and_id(client):
    page = client.get("/waybills/hold-1").text
    assert 'value="HOLD"' in page and "readonly" in page and 'hx-get' not in page
    response = client.post("/waybills/hold-1", data={"originating_railroad_id": "PRR", "industry_id": "LEW-GRAIN",
                                                      "waiting_for": "Empty car", "id": "ignored"})
    assert "Applied waybill hold-1" in follow(client, response).text
    assert "Empty car" in client.get("/waybills").text


def test_car_form_reports_non_numeric_input(client):
    response = client.post("/cars/PRR-12345", data={**CAR_FORM, "capacity_tons": "fifty"})
    assert response.status_code == 422 and "Must be a whole number" in response.text


def test_new_car_id_is_derived_when_left_blank(client):
    response = client.post("/cars/new", data={**CAR_FORM, "car_number": "777"})
    assert "Applied car PRR-777" in follow(client, response).text


def test_new_commodity_and_location_ids_are_generated_from_the_name(client):
    assert "Applied commodity iron-ore" in follow(client, client.post("/commodities/new", data={"name": "Iron Ore"})).text
    assert "Applied location PHI" in follow(client, client.post("/locations/new", data={"name": "Philadelphia"})).text
    assert "Applied railroad NP" in follow(client, client.post("/railroads/new", data={"name": "Nickel Plate", "form_number": "F1"})).text


def test_editing_a_location_keeps_its_industries(client):
    follow(client, client.post("/locations/LEW", data={"name": "Lewistown", "state": "PA", "on_layout": "on"}))
    assert "LEW-GRAIN" in client.get("/locations/LEW").text


def test_delete_is_blocked_while_referenced_and_allowed_otherwise(client):
    blocked = client.post("/commodities/grain/delete")
    assert blocked.headers["location"].startswith("/commodities/grain?flash=")
    assert "waybill-1" in follow(client, blocked).text
    assert "Deleted PRR-67890" in follow(client, client.post("/cars/PRR-67890/delete")).text
    assert "DELETED" in client.get("/cars").text
    assert client.post("/cars/NOPE/delete").status_code == 404


def test_the_picker_script_is_served(client):
    assert client.get("/static/pickers.js").status_code == 200
    assert client.get("/static/ids.js").status_code == 200
    assert "/static/pickers.js" in client.get("/waybills/new").text


@pytest.mark.parametrize("bad_id", ["new", "fields", "a#b", "a?b", "a/b"])
def test_new_record_ids_must_be_url_safe(client, bad_id):
    response = client.post("/cars/new", data={**CAR_FORM, "id": bad_id, "car_number": "888"})
    assert response.status_code == 422 and "Use only letters, digits" in response.text
    assert "Applied" not in response.text and "1 unsaved change" not in client.get("/cars").text
    assert "888" not in client.get("/cars").text            # nothing was staged under that (or any) id


def test_a_url_safe_id_is_accepted_and_reachable(client):
    response = client.post("/cars/new", data={**CAR_FORM, "id": "PRR.1-x_2", "car_number": "888"})
    assert "Applied car PRR.1-x_2" in follow(client, response).text
    assert client.get("/cars/PRR.1-x_2").status_code == 200


def test_a_generated_id_with_an_ampersand_is_valid_and_reachable(client):
    response = client.post("/cars/new", data={**CAR_FORM, "road": "B&O", "car_number": "486"})
    assert "Applied car B&amp;O-486" in follow(client, response).text          # the flash is HTML-escaped
    assert client.get("/cars/B&O-486").status_code == 200
    assert client.post("/cars/B&O-486", data={**CAR_FORM, "road": "B&O", "car_number": "486"}).status_code == 303


def test_suggest_id_route_answers_from_the_fields_typed_so_far(client):
    assert client.get("/cars/suggest-id?road=PRR&car_number=555").json() == {"id": "PRR-555"}
    assert client.get("/cars/suggest-id?road=PRR").json() == {"id": ""}
    assert client.get("/commodities/suggest-id?name=Iron%20Ore").json() == {"id": "iron-ore"}
    assert client.get("/locations/suggest-id?name=Lewistown").json() == {"id": "LEW2"}
    assert client.get("/railroads/suggest-id?name=Nickel%20Plate").json() == {"id": "NP"}
    assert client.get("/waybills/suggest-id").json() == {"id": "waybill-2"}
    assert client.get("/nope/suggest-id").status_code == 404


def test_suggest_id_is_not_usable_as_a_record_id(client):
    response = client.post("/cars/new", data={**CAR_FORM, "id": "suggest-id"})
    assert response.status_code == 422 and "Use only letters" in response.text


def test_a_new_record_shows_a_locked_generated_id_with_an_edit_button(client):
    page = client.get("/cars/new").text
    assert 'data-id-field' in page and 'data-suggest-url="/cars/suggest-id"' in page
    assert 'id="f-id" name="id"' in page and "readonly" in page and 'class="locked"' in page
    assert 'name="id_manual" value="0"' in page and "id-toggle" in page and "✎ Edit" in page
    assert "Generated from the other fields" in page
    waybill = client.get("/waybills/new").text
    assert 'value="waybill-2"' in waybill and "id-toggle" in waybill


def test_an_existing_record_shows_a_locked_id_without_an_edit_button(client):
    page = client.get("/cars/PRR-12345").text
    assert 'id="f-id" name="id"' in page and "readonly" in page
    assert "id-toggle" not in page and "id_manual" not in page and "data-suggest-url" not in page
    assert "can&#39;t be renamed" in page or "can't be renamed" in page


def test_a_manually_typed_id_stays_editable_after_a_validation_error(client):
    response = client.post("/cars/new", data={**CAR_FORM, "id": "MY-OWN", "id_manual": "1", "capacity_tons": "fifty"})
    assert response.status_code == 422 and "Must be a whole number" in response.text
    assert 'value="MY-OWN"' in response.text and 'name="id_manual" value="1"' in response.text
    assert "↺ Auto" in response.text and 'class="locked"' not in response.text


def test_a_locked_id_stays_locked_after_a_validation_error(client):
    response = client.post("/cars/new", data={**CAR_FORM, "id": "PRR-12345x", "id_manual": "0", "capacity_tons": "fifty"})
    assert response.status_code == 422
    assert 'name="id_manual" value="0"' in response.text and 'class="locked"' in response.text


def test_the_type_swap_fragment_keeps_the_id_mode(client):
    locked = client.get("/waybills/fields?waybill_type=EMPTY&id=waybill-9&id_manual=0").text
    assert 'class="locked"' in locked and 'name="id_manual" value="0"' in locked
    manual = client.get("/waybills/fields?waybill_type=EMPTY&id=mine&id_manual=1").text
    assert 'name="id_manual" value="1"' in manual and 'class="locked"' not in manual and 'value="mine"' in manual
