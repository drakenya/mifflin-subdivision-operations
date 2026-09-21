import difflib

import pytest
import yaml

from waybill_generator.models.waybill import HoldWaybill, LoadedWaybill
from waybill_generator.web.working_copy import (
    DataError,
    DiskConflict,
    ReferenceBlocked,
    SaveIncomplete,
    ValidationBlocked,
    WorkingCopy,
    merge_raw,
)


def changed_lines(diff_text: str) -> list[str]:
    return [line for line in diff_text.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]


def new_loaded(**overrides) -> LoadedWaybill:
    fields = {"id": "waybill-2", "originating_railroad_id": "PRR", "commodity_id": "coal",
              "shipper_id": "ALT-SHOP", "consignee_id": "LEW-GRAIN"}
    return LoadedWaybill(**{**fields, **overrides})


def test_loads_fixtures_without_changes(data_dir):
    wc = WorkingCopy(data_dir)
    assert wc.change_count() == 0 and wc.dirty_kinds() == []
    assert len(wc.get_cars()) == 2 and len(wc.get_waybills()) == 6


def test_repository_contract(data_dir):
    wc = WorkingCopy(data_dir)
    assert wc.get_car("PRR-12345").road == "PRR"
    assert wc.get_location("LEW").name == "Lewistown"
    assert wc.get_industry("LEW-GRAIN").name == "Lewistown Grain Elevator"
    assert wc.get_commodity("grain").name == "Grain"
    assert wc.get_railroad("PRR").form_number == "Form 1304"
    assert wc.get_waybill("waybill-1").waybill_type == "LOADED"
    assert len(wc.get_locations()) == 2 and len(wc.get_commodities()) == 2 and len(wc.get_railroads()) == 1
    for getter, missing in [(wc.get_car, "NOPE"), (wc.get_location, "NOPE"), (wc.get_industry, "NOPE"),
                            (wc.get_commodity, "NOPE"), (wc.get_railroad, "NOPE"), (wc.get_waybill, "NOPE")]:
        with pytest.raises(KeyError):
            getter(missing)


def test_existing_broken_references_are_reported_but_do_not_block(data_dir):
    validation = WorkingCopy(data_dir).validate()      # fixture deadhead-1 points at PHL and PGH
    assert validation.blocking == []
    assert {r.value for r in validation.existing} == {"PHL", "PGH"}


def test_noop_save_writes_nothing(data_dir):
    wc = WorkingCopy(data_dir)
    before = {p.name: p.read_text() for p in data_dir.glob("*.yaml")}
    assert wc.save() == []
    assert {p.name: p.read_text() for p in data_dir.glob("*.yaml")} == before


def test_edit_car_changes_one_line(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "repainted"}))
    assert wc.status("cars", "PRR-12345") == "modified" and wc.change_count() == 1
    (diff,) = wc.diffs()
    assert diff.filename == "cars.yaml" and "+++ b/data/cars.yaml" in diff.diff
    assert changed_lines(diff.diff) == ["+  notes: repainted"]


def test_edit_industry_changes_one_line_and_keeps_omitted_defaults_absent(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply_industry("LEW", wc.get_industry("LEW-GRAIN").model_copy(update={"car_capacity": 5}))
    (diff,) = wc.diffs()
    assert changed_lines(diff.diff) == ["-      car_capacity: 3", "+      car_capacity: 5"]


def test_new_waybill_is_saved_grouped_with_its_type_and_reloads_equal(data_dir):
    wc = WorkingCopy(data_dir)
    waybill = new_loaded(notes="new one", routing=["ALT"])
    wc.apply("waybills", waybill)
    assert wc.status("waybills", "waybill-2") == "new"
    assert wc.save() == ["waybills.yaml"]
    assert wc.change_count() == 0
    saved = yaml.safe_load((data_dir / "waybills.yaml").read_text())
    assert [r["id"] for r in saved][:3] == ["waybill-1", "waybill-2", "empty-1"]
    assert saved[1] == {"id": "waybill-2", "waybill_type": "LOADED", "originating_railroad_id": "PRR",
                        "commodity_id": "coal", "shipper_id": "ALT-SHOP", "consignee_id": "LEW-GRAIN",
                        "routing": ["ALT"], "notes": "new one"}
    assert WorkingCopy(data_dir).get("waybills", "waybill-2") == waybill


def test_new_broken_reference_blocks_save(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("waybills", new_loaded(commodity_id="nope"))
    assert [r.value for r in wc.validate().blocking] == ["nope"]
    with pytest.raises(ValidationBlocked):
        wc.save()


def test_touching_a_record_that_already_has_a_broken_reference_still_saves(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("waybills", wc.get("waybills", "deadhead-1").model_copy(update={"notes": "touched"}))
    assert wc.validate().blocking == []
    assert wc.save() == ["waybills.yaml"]


def test_fixing_a_broken_reference_by_adding_the_target_clears_the_warning(data_dir):
    wc = WorkingCopy(data_dir)
    from waybill_generator.models.location import Location
    wc.apply("locations", Location(id="PHL", name="Philadelphia"))
    assert {r.value for r in wc.validate().existing} == {"PGH"}


def test_delete_blocked_while_referenced(data_dir):
    wc = WorkingCopy(data_dir)
    with pytest.raises(ReferenceBlocked) as blocked:
        wc.delete("commodities", "grain")
    assert {(r.kind, r.record_id) for r in blocked.value.refs} == {("waybills", "waybill-1"), ("industries", "LEW-GRAIN")}
    assert wc.has("commodities", "grain")


def test_delete_unreferenced_car_and_save(data_dir):
    wc = WorkingCopy(data_dir)
    wc.delete("cars", "PRR-67890")
    assert wc.deleted_ids("cars") == ["PRR-67890"] and wc.change_count() == 1
    assert wc.save() == ["cars.yaml"]
    assert [c["id"] for c in yaml.safe_load((data_dir / "cars.yaml").read_text())] == ["PRR-12345"]


def test_delete_location_blocked_when_its_industries_are_used(data_dir):
    with pytest.raises(ReferenceBlocked):
        WorkingCopy(data_dir).delete("locations", "LEW")      # LEW-GRAIN ships on waybill-1


def test_delete_unused_location_succeeds(data_dir):
    wc = WorkingCopy(data_dir)
    from waybill_generator.models.location import Location
    wc.apply("locations", Location(id="XYZ", name="Xyz"))
    wc.delete("locations", "XYZ")
    assert not wc.has("locations", "XYZ") and wc.change_count() == 0


def test_industry_add_and_delete(data_dir):
    from waybill_generator.models.location import Industry
    wc = WorkingCopy(data_dir)
    wc.apply_industry("LEW", Industry(id="LEW-NEW", name="New Co", location_id="ignored"))
    assert wc.get_industry("LEW-NEW").location_id == "LEW"
    with pytest.raises(ReferenceBlocked):
        wc.delete_industry("LEW", "LEW-GRAIN")
    wc.delete_industry("LEW", "LEW-NEW")
    assert wc.change_count() == 0


def test_conflict_is_detected_and_can_be_overridden(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    (data_dir / "cars.yaml").write_text((data_dir / "cars.yaml").read_text() + "\n# edited elsewhere\n")
    assert wc.conflicts() == ["cars.yaml"]
    with pytest.raises(DiskConflict) as conflict:
        wc.save()
    assert conflict.value.files == ["cars.yaml"]
    assert wc.save(overwrite=True) == ["cars.yaml"]


def test_reload_file_and_discard_drop_staged_edits(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    wc.delete("cars", "PRR-67890")
    wc.reload_file("cars")
    assert wc.change_count() == 0
    wc.delete("cars", "PRR-67890")
    wc.discard()
    assert wc.change_count() == 0 and wc.has("cars", "PRR-67890")


def test_unreadable_files_raise_data_error_naming_the_file(data_dir):
    (data_dir / "cars.yaml").write_text("- id: a\n  x: [unclosed\n")
    with pytest.raises(DataError, match="cars.yaml"):
        WorkingCopy(data_dir)
    (data_dir / "cars.yaml").write_text("- id: a\n  road: PRR\n")          # missing required fields
    with pytest.raises(DataError, match="cars.yaml: record 'a'"):
        WorkingCopy(data_dir)
    (data_dir / "cars.yaml").write_text("just: a mapping\n")
    with pytest.raises(DataError, match="cars.yaml"):
        WorkingCopy(data_dir)


def test_stage_failure_leaves_data_untouched(data_dir, monkeypatch):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    wc.apply("commodities", wc.get("commodities", "grain").model_copy(update={"name": "Grains"}))
    before = {p.name: p.read_text() for p in data_dir.glob("*.yaml")}
    calls = []
    original = type(wc._files["cars"]).stage

    def flaky(self, text):
        calls.append(self.path.name)
        if len(calls) == 2:
            raise OSError("disk full")
        return original(self, text)

    monkeypatch.setattr(type(wc._files["cars"]), "stage", flaky)
    with pytest.raises(OSError):
        wc.save()
    assert {p.name: p.read_text() for p in data_dir.glob("*.yaml")} == before
    assert not list(data_dir.glob("*.tmp"))


def test_commit_failure_reports_what_was_written_and_allows_retry(data_dir, monkeypatch):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    wc.apply("commodities", wc.get("commodities", "grain").model_copy(update={"name": "Grains"}))
    commodities_before = (data_dir / "commodities.yaml").read_text()
    yaml_file = type(wc._files["cars"])
    original = yaml_file.commit
    calls = []

    def flaky(self, tmp):
        calls.append(self.path.name)
        if len(calls) == 2:
            raise OSError("rename failed")
        return original(self, tmp)

    monkeypatch.setattr(yaml_file, "commit", flaky)
    with pytest.raises(SaveIncomplete) as incomplete:
        wc.save()
    assert incomplete.value.written == ["cars.yaml"]
    assert incomplete.value.failed == "commodities.yaml"
    assert incomplete.value.unwritten == []
    assert not list(data_dir.glob("*.tmp"))
    assert next(c for c in yaml.safe_load((data_dir / "cars.yaml").read_text()) if c["id"] == "PRR-12345")["notes"] == "mine"
    assert (data_dir / "commodities.yaml").read_text() == commodities_before
    assert wc.dirty_kinds() == ["commodities"]

    monkeypatch.setattr(yaml_file, "commit", original)
    assert wc.save() == ["commodities.yaml"]
    assert wc.change_count() == 0
    assert WorkingCopy(data_dir).get("commodities", "grain").name == "Grains"


def test_merge_raw_keeps_unchanged_keys_and_appends_new_ones():
    old_raw = {"id": "a", "name": "A", "icon": None}
    old_dump = {"id": "a", "name": "A", "icon": None, "state": "PA"}     # `state` is a default, absent in the file
    assert merge_raw(old_raw, old_dump, {**old_dump, "name": "B"}) == {"id": "a", "name": "B", "icon": None}
    assert merge_raw(old_raw, old_dump, {**old_dump, "state": "NY"}) == {"id": "a", "name": "A", "icon": None, "state": "NY"}
    assert merge_raw(old_raw, old_dump, {**old_dump, "icon": "x"})["icon"] == "x"
    assert "icon" not in merge_raw({"id": "a", "icon": "x"}, {"id": "a", "icon": "x"}, {"id": "a", "icon": None})


def test_merge_raw_for_a_new_record_drops_nones_and_puts_notes_last():
    dump = {"id": "a", "notes": "n", "x": None, "items": [{"id": "i", "notes": "m", "y": None, "z": 1}]}
    merged = merge_raw(None, {}, dump)
    assert list(merged) == ["id", "items", "notes"]
    assert merged["items"] == [{"id": "i", "z": 1, "notes": "m"}]


def test_hold_waybill_round_trip(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("waybills", HoldWaybill(id="hold-2", originating_railroad_id="PRR", industry_id="ALT-SHOP", waiting_for="parts"))
    wc.save()
    assert wc.get("waybills", "hold-2") == HoldWaybill(
        id="hold-2", originating_railroad_id="PRR", industry_id="ALT-SHOP", waiting_for="parts")


def test_diff_text_is_a_unified_diff(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "x"}))
    (diff,) = wc.diffs()
    assert list(difflib.unified_diff([], [])) == [] and diff.diff.startswith("--- a/data/cars.yaml")


@pytest.mark.parametrize("broken", ["- id: a\n  x: [unclosed\n", "- id: a\n  road: PRR\n"],
                         ids=["invalid-yaml", "invalid-record"])
def test_a_failed_reload_keeps_staged_edits_and_the_disk_conflict_guard(data_dir, broken):
    wc = WorkingCopy(data_dir)
    original = (data_dir / "cars.yaml").read_text()
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    (data_dir / "cars.yaml").write_text(broken)

    with pytest.raises(DataError):
        wc.reload_file("cars")
    assert wc.change_count() == 1                      # staged edit survives
    assert wc.conflicts() == ["cars.yaml"]             # still flagged as changed on disk
    with pytest.raises(DiskConflict):
        wc.save()
    assert (data_dir / "cars.yaml").read_text() == broken

    with pytest.raises(DataError):
        wc.discard()
    assert wc.conflicts() == ["cars.yaml"]
    assert (data_dir / "cars.yaml").read_text() == broken

    (data_dir / "cars.yaml").write_text(original)      # recovery: fix the file, reload works
    wc.reload_file("cars")
    assert wc.change_count() == 0 and wc.conflicts() == []


def test_duplicate_ids_in_a_data_file_refuse_to_load(data_dir):
    path = data_dir / "commodities.yaml"
    path.write_text(path.read_text() + "\n- id: grain\n  name: Grain again\n")
    with pytest.raises(DataError, match=r"commodities\.yaml.*duplicate"):
        WorkingCopy(data_dir)


@pytest.mark.parametrize("text", ["- code: XM\n  name: [unclosed\n", "- name: no code\n", "just: a mapping\n", "42\n"],
                         ids=["syntax-error", "row-without-code", "mapping", "scalar"])
def test_a_bad_aar_codes_file_raises_data_error(data_dir, text):
    (data_dir / "aar_codes.yaml").write_text(text)
    with pytest.raises(DataError, match="aar_codes.yaml"):
        WorkingCopy(data_dir)


def test_aar_codes_hand_added_on_disk_are_picked_up_by_discard_and_reload(data_dir):
    wc = WorkingCopy(data_dir)
    car = wc.get("cars", "PRR-12345").model_copy(update={"aar_code": "FM"})
    wc.apply("cars", car)
    assert [r.value for r in wc.validate().blocking] == ["FM"]           # not a known code yet
    path = data_dir / "aar_codes.yaml"
    path.write_text(path.read_text() + "- code: FM\n  name: Flat Car\n")
    assert [r.value for r in wc.validate().blocking] == ["FM"]           # still blocked until a refresh
    wc.discard()
    wc.apply("cars", car)
    assert wc.validate().blocking == []
    assert wc.save() == ["cars.yaml"]


def test_reload_file_also_refreshes_aar_codes(data_dir):
    wc = WorkingCopy(data_dir)
    path = data_dir / "aar_codes.yaml"
    path.write_text(path.read_text() + "- code: FM\n  name: Flat Car\n")
    wc.reload_file("cars")
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"aar_code": "FM"}))
    assert wc.validate().blocking == []


def test_a_bad_aar_codes_file_on_reload_keeps_the_old_codes(data_dir):
    wc = WorkingCopy(data_dir)
    (data_dir / "aar_codes.yaml").write_text("- name: no code\n")
    with pytest.raises(DataError, match="aar_codes.yaml"):
        wc.discard()
    with pytest.raises(DataError, match="aar_codes.yaml"):
        wc.reload_file("cars")
    assert ("XM", "Box Car") in wc.aar_codes


def _corrupt_render(monkeypatch):
    from waybill_generator.web.yaml_store import YamlFile
    real = YamlFile.render

    def corrupted(self, desired):
        return real(self, desired) + "\n- id: intruder\n  name: not intended\n"

    monkeypatch.setattr(YamlFile, "render", corrupted)


def test_save_refuses_rendered_text_that_does_not_match_the_intended_records(data_dir, monkeypatch):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    wc.apply("commodities", wc.get("commodities", "grain").model_copy(update={"name": "Grains"}))
    before = {p.name: p.read_text() for p in data_dir.glob("*.yaml")}
    _corrupt_render(monkeypatch)
    with pytest.raises(DataError, match=r"cars\.yaml: refusing to write"):
        wc.save()
    assert {p.name: p.read_text() for p in data_dir.glob("*.yaml")} == before
    assert not list(data_dir.glob("*.tmp"))
    assert wc.change_count() == 2
