import pytest

from waybill_generator.web.entities import clean_id, id_error, suggest_id
from waybill_generator.web.working_copy import WorkingCopy


@pytest.mark.parametrize("record_id", ["PRR-12345", "LEW-GRAIN", "waybill-1", "iron-ore", "PRR.1-x_2", "B&O-486321"])
def test_id_error_accepts_ids_that_work_in_a_url_path(record_id):
    assert id_error(record_id) is None


@pytest.mark.parametrize("record_id", ["", "new", "fields", "suggest-id", "a/b", "a#b", "a?b", "a b", "a%2Fb", "PRR/999"])
def test_id_error_rejects_reserved_and_url_unsafe_ids(record_id):
    assert "Use only letters, digits" in id_error(record_id)


@pytest.mark.parametrize("raw, cleaned", [
    ("PRR-12345", "PRR-12345"), ("B&O-486", "B&O-486"), ("LEW-BOB'S", "LEW-BOBS"),
    ("St. Mary's", "St.Marys"), ("a/b?c#d e", "abcde"),
])
def test_clean_id_drops_characters_that_would_break_a_url(raw, cleaned):
    assert clean_id(raw) == cleaned


def test_suggest_id_follows_the_typed_fields_and_stays_url_safe(data_dir):
    wc = WorkingCopy(data_dir)
    assert suggest_id(wc, "cars", {"road": "PRR", "car_number": "555"}) == "PRR-555"
    assert suggest_id(wc, "cars", {"road": "PRR"}) == ""                       # nothing sensible yet
    assert suggest_id(wc, "commodities", {"name": "Iron Ore"}) == "iron-ore"
    assert suggest_id(wc, "locations", {"name": "Philadelphia"}) == "PHI"
    assert suggest_id(wc, "locations", {"name": "Lewistown"}) == "LEW2"        # LEW is taken
    assert suggest_id(wc, "locations", {"name": "St. Mary's"}) == "ST."        # first three letters, cleaned
    assert suggest_id(wc, "railroads", {"name": "Pennsylvania Railroad"}) == "PR"
    assert suggest_id(wc, "railroads", {"name": ""}) == ""
    assert suggest_id(wc, "waybills", {}) == "waybill-2"
