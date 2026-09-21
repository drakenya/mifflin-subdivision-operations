import yaml
from fastapi.testclient import TestClient

from tests.web.conftest import CAR_FORM, follow
from waybill_generator.web.app import create_app
from waybill_generator.web.working_copy import FileDiff, WorkingCopy
from waybill_generator.web.yaml_store import YamlFile


def stage_a_car_edit(client, notes="mine"):
    client.post("/cars/PRR-12345", data={"road": "PRR", "car_number": "12345", "aar_code": "XM",
                                          "capacity_tons": "50", "notes": notes})


def test_review_with_nothing_staged(client):
    assert "No unsaved changes." in client.get("/review").text


def test_review_shows_diff_validation_and_existing_warnings(client):
    stage_a_car_edit(client)
    page = client.get("/review").text
    assert "data/cars.yaml" in page and "+  notes: mine" in page
    assert "No new broken references" in page and "Save 1 file to YAML" in page
    assert "pre-existing broken reference" in page and "PHL" in page          # fixture deadhead-1


def test_new_broken_reference_blocks_saving(client):
    follow(client, client.post("/waybills/new", data={
        "waybill_type": "HOLD", "id": "hold-9", "originating_railroad_id": "PRR",
        "industry_id": "NOPE-IND", "waiting_for": "x"}))
    page = client.get("/review").text
    assert "Can't save" in page and "NOPE-IND" in page and "disabled" in page
    assert "Not saved" in follow(client, client.post("/save", data={})).text


def test_save_writes_and_clears_the_unsaved_banner(client, data_dir):
    stage_a_car_edit(client)
    assert "Saved cars.yaml" in follow(client, client.post("/save", data={})).text
    assert "notes: mine" in (data_dir / "cars.yaml").read_text()
    assert "unsaved" not in client.get("/cars").text
    assert "Nothing to save" in follow(client, client.post("/save", data={})).text


def test_disk_conflict_offers_reload_or_overwrite(client, data_dir):
    stage_a_car_edit(client)
    (data_dir / "cars.yaml").write_text((data_dir / "cars.yaml").read_text() + "\n# edited elsewhere\n")
    page = client.get("/review").text
    assert "Changed on disk" in page and "Reload cars.yaml from disk" in page and "Overwrite" in page
    assert "Not saved" in follow(client, client.post("/save", data={})).text
    assert "edited elsewhere" in (data_dir / "cars.yaml").read_text()
    assert "Saved cars.yaml" in follow(client, client.post("/save", data={"overwrite": "on"})).text
    assert "edited elsewhere" not in (data_dir / "cars.yaml").read_text()


def test_reload_drops_that_files_staged_edits(client):
    stage_a_car_edit(client)
    assert "Reloaded cars.yaml" in follow(client, client.post("/reload/cars")).text
    assert "unsaved" not in client.get("/cars").text
    assert client.post("/reload/nope").status_code == 404


def test_discard_drops_everything_staged(client):
    stage_a_car_edit(client)
    client.post("/cars/PRR-67890/delete")
    assert "Discarded all unsaved changes" in follow(client, client.post("/discard")).text
    assert "unsaved" not in client.get("/cars").text and "PRR-67890" in client.get("/cars").text


def test_unreadable_file_on_disk_is_reported_on_reload(client, data_dir):
    (data_dir / "cars.yaml").write_text("- id: a\n  x: [unclosed\n")
    assert "Reload failed" in follow(client, client.post("/reload/cars")).text
    assert "Reload failed" in follow(client, client.post("/discard")).text


def test_edit_car_is_visible_in_review_and_saves_to_yaml(client, data_dir):
    follow(client, client.post("/cars/PRR-12345", data={**CAR_FORM, "notes": "repainted"}))
    assert "+  notes: repainted" in client.get("/review").text
    assert "Saved cars.yaml" in follow(client, client.post("/save", data={})).text
    assert yaml.safe_load((data_dir / "cars.yaml").read_text())[0]["notes"] == "repainted"
    assert "unsaved" not in client.get("/cars").text




def test_a_value_missing_from_the_data_survives_an_edit(data_dir):
    (data_dir / "waybills.yaml").write_text((data_dir / "waybills.yaml").read_text() + """
- id: perishable-1
  waybill_type: PERISHABLE
  originating_railroad_id: PRR
  commodity_id: produce
  shipper_name: Growers Assoc.
  consignee_name: Fresh Foods
  to_city: New York
  to_state: NY
  from_city: Lewistown
  from_state: PA
  routing: [PRR, NYC, NH]
""")
    client = TestClient(create_app(data_dir), follow_redirects=False)
    page = client.get("/waybills/perishable-1").text
    assert 'value="produce"' in page and "not in data" in page
    form = {"originating_railroad_id": "PRR", "commodity_id": "produce", "shipper_name": "Growers Assoc.",
            "consignee_name": "Fresh Foods", "to_city": "New York", "to_state": "NY", "from_city": "Lewistown",
            "from_state": "PA", "routing": ["PRR", "NYC", "NH"], "notes": "checked"}
    follow(client, client.post("/waybills/perishable-1", data=form))
    assert "Saved waybills.yaml" in follow(client, client.post("/save", data={})).text
    text = (data_dir / "waybills.yaml").read_text()
    assert "commodity_id: produce" in text and "routing: [PRR, NYC, NH]" in text   # untouched keys keep their form
    assert text.rstrip().endswith("notes: checked")


def test_a_failed_rename_partway_reports_what_was_and_was_not_saved(client, data_dir, monkeypatch):
    stage_a_car_edit(client)
    client.post("/commodities/grain", data={"name": "Grains"})
    before = {name: (data_dir / name).read_text() for name in ("cars.yaml", "commodities.yaml")}

    real_commit = YamlFile.commit
    calls = []

    def flaky_commit(self, tmp):
        calls.append(self.path.name)
        if len(calls) == 2:
            raise OSError("disk full")
        real_commit(self, tmp)

    monkeypatch.setattr(YamlFile, "commit", flaky_commit)
    response = client.post("/save", data={})
    assert response.status_code == 303 and response.headers["location"].startswith("/review")
    page = client.get(response.headers["location"]).text
    assert "Save incomplete" in page
    assert f"saved {calls[0]}" in page and f"failed on {calls[1]}" in page
    assert sorted(calls) == ["cars.yaml", "commodities.yaml"]

    written, failed = calls
    assert (data_dir / written).read_text() != before[written]
    assert (data_dir / failed).read_text() == before[failed]
    assert list(data_dir.glob("*.tmp")) == [] and list(data_dir.glob("**/*.tmp")) == []


def test_a_failed_reload_does_not_let_save_overwrite_the_file_silently(client, data_dir):
    stage_a_car_edit(client)
    (data_dir / "cars.yaml").write_text("- id: a\n  x: [unclosed\n")
    assert "Reload failed" in follow(client, client.post("/reload/cars")).text
    assert "Changed on disk" in client.get("/review").text
    assert "Not saved" in follow(client, client.post("/save", data={})).text
    assert (data_dir / "cars.yaml").read_text() == "- id: a\n  x: [unclosed\n"
    assert "Saved cars.yaml" in follow(client, client.post("/save", data={"overwrite": "on"})).text
    assert "notes: mine" in (data_dir / "cars.yaml").read_text()


def test_a_rendered_file_that_fails_the_parse_check_is_reported_not_written(client, data_dir, monkeypatch):
    stage_a_car_edit(client)
    before = (data_dir / "cars.yaml").read_text()
    real = YamlFile.render
    monkeypatch.setattr(YamlFile, "render", lambda self, desired: real(self, desired) + "- id: intruder\n")
    page = follow(client, client.post("/save", data={})).text
    assert "Not saved" in page and "refusing to write" in page
    assert (data_dir / "cars.yaml").read_text() == before and list(data_dir.glob("*.tmp")) == []


def test_a_read_only_data_dir_is_reported_not_a_500(client, data_dir, monkeypatch):
    stage_a_car_edit(client)
    before = (data_dir / "cars.yaml").read_text()

    def deny(self, text):
        raise PermissionError("read-only")

    monkeypatch.setattr(YamlFile, "stage", deny)
    page = follow(client, client.post("/save", data={})).text
    assert "Not saved" in page and "read-only" in page
    assert (data_dir / "cars.yaml").read_text() == before and list(data_dir.glob("*.tmp")) == []
    assert "1 unsaved change" in client.get("/cars").text


def test_review_shows_content_lines_that_start_with_dashes_or_pluses(client, monkeypatch):
    diff = ("--- a/data/cars.yaml\n+++ b/data/cars.yaml\n@@ -1,2 +1,2 @@\n"
            "--- removed line\n+++ added line\n context\n")
    monkeypatch.setattr(WorkingCopy, "diffs", lambda self: [FileDiff("cars", "cars.yaml", diff)])
    page = client.get("/review").text
    assert "--- removed line" in page and "+++ added line" in page
    assert "--- a/data/cars.yaml" not in page and "+++ b/data/cars.yaml" not in page
