import difflib

import pytest
import yaml

from waybill_generator.web.yaml_store import UnsupportedLayout, YamlFile, dump_record

SAMPLE = """\
# Sample data
# second header line

# ── SECTION A ──

- id: a1
  kind: A
  code: "01110"
  tags: [x, y]
  # what it ships
  ships:
    - p
    - q
  label: "Track 1"

- id: a2
  kind: A

# ── SECTION B ──

- id: b1
  kind: B
  label: hello
"""


def changed_lines(before: str, after: str) -> list[str]:
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
    return [line for line in diff if line[:1] in "+-" and not line.startswith(("+++", "---"))]


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "sample.yaml"
    path.write_text(SAMPLE)
    return YamlFile(path, group_key=lambda r: r.get("kind"))


def ids(text: str) -> list[str]:
    return [r["id"] for r in yaml.safe_load(text)]


def test_noop_render_is_byte_identical(sample):
    assert sample.render(sample.records()) == SAMPLE


def test_records_are_deep_copies(sample):
    records = sample.records()
    records[0]["ships"].append("z")
    assert sample.records()[0]["ships"] == ["p", "q"]


def test_edit_touches_only_the_changed_line(sample):
    records = sample.records()
    records[0]["label"] = "Yard"
    out = sample.render(records)
    assert changed_lines(SAMPLE, out) == ['-  label: "Track 1"', "+  label: Yard"]
    assert "tags: [x, y]" in out and "# what it ships" in out


def test_changed_list_is_reemitted_but_keeps_its_comment_and_neighbours(sample):
    records = sample.records()
    records[0]["ships"] = ["p", "q", "r"]
    out = sample.render(records)
    assert changed_lines(SAMPLE, out) == ["+    - r"]
    assert "# what it ships" in out and "tags: [x, y]" in out


def test_new_record_goes_after_the_last_of_its_group(sample):
    records = sample.records() + [{"id": "a3", "kind": "A", "label": "z"}]
    out = sample.render(records)
    assert ids(out) == ["a1", "a2", "a3", "b1"]
    assert "# ── SECTION B ──\n\n- id: b1" in out          # section header still heads its section
    assert all(line.startswith("+") for line in changed_lines(SAMPLE, out))


def test_new_record_without_matching_group_is_appended(sample):
    out = sample.render(sample.records() + [{"id": "c1", "kind": "C"}])
    assert ids(out)[-1] == "c1"
    assert all(line.startswith("+") for line in changed_lines(SAMPLE, out))


def test_delete_removes_only_that_record_and_keeps_section_comments(sample):
    out = sample.render([r for r in sample.records() if r["id"] != "a2"])
    assert ids(out) == ["a1", "b1"]
    assert out.count("# ── SECTION") == 2
    assert all(line.startswith("-") for line in changed_lines(SAMPLE, out))


def test_delete_last_record_keeps_the_section_comment(sample):
    out = sample.render([r for r in sample.records() if r["id"] != "b1"])
    assert ids(out) == ["a1", "a2"]
    assert "# ── SECTION B ──" in out and out.endswith("\n")


def test_delete_first_record(sample):
    out = sample.render([r for r in sample.records() if r["id"] != "a1"])
    assert ids(out) == ["a2", "b1"] and out.startswith("# Sample data")


def test_append_into_header_only_and_empty_files(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("# just a header\n")
    assert YamlFile(path).render([{"id": "a", "name": "A"}]) == "# just a header\n\n- id: a\n  name: A\n"
    path.write_text("")
    assert YamlFile(path).render([{"id": "a", "name": "A"}]) == "- id: a\n  name: A\n"


def test_missing_file_is_treated_as_empty(tmp_path):
    file = YamlFile(tmp_path / "nope.yaml")
    assert file.records() == []
    assert file.render([{"id": "a"}]) == "- id: a\n"


@pytest.mark.parametrize("text", ["key: value\n", "- just\n- scalars\n", "- name: no id\n", "42\n"])
def test_unsupported_layouts_are_rejected(tmp_path, text):
    path = tmp_path / "x.yaml"
    path.write_text(text)
    with pytest.raises(UnsupportedLayout):
        YamlFile(path)


def test_duplicate_ids_are_rejected_rather_than_collapsed(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("- id: a\n  name: first\n- id: b\n- id: a\n  name: second\n")
    with pytest.raises(UnsupportedLayout, match=r"duplicate id.*\['a'\]"):
        YamlFile(path)


def test_non_ascii_text_and_box_drawing_comments_round_trip_as_utf8(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("# ── SECTION ──\n\n- id: a\n  name: Café Käse\n", encoding="utf-8")
    file = YamlFile(path)
    assert file.records()[0]["name"] == "Café Käse" and not file.changed_on_disk()
    records = file.records()
    records[0]["notes"] = "Grüße"
    file.commit(file.stage(file.render(records)))
    text = path.read_bytes().decode("utf-8")
    assert "# ── SECTION ──" in text and "name: Café Käse" in text and "notes: Grüße" in text
    assert not file.changed_on_disk()


def test_conflict_detection_stage_and_commit(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("- id: a\n  name: A\n")
    file = YamlFile(path)
    assert not file.changed_on_disk()
    path.write_text("- id: a\n  name: B\n")
    assert file.changed_on_disk()
    tmp = file.stage("- id: a\n  name: C\n")
    assert tmp != path and path.read_text() == "- id: a\n  name: B\n"
    file.commit(tmp)
    assert path.read_text() == "- id: a\n  name: C\n"
    assert not tmp.exists() and not file.changed_on_disk() and file.records()[0]["name"] == "C"


def test_dump_record_house_style():
    assert dump_record({"id": "x", "ships": ["a", "b"], "none": None, "empty": [], "active": True}) == (
        "- id: x\n  ships:\n    - a\n    - b\n  none: null\n  empty: []\n  active: true\n"
    )


def test_dump_record_quotes_numeric_looking_strings():
    out = dump_record({"id": "x", "code": "01110", "n": "12345", "w": "36,200", "price": "112.40", "word": "Track 1"})
    assert 'code: "01110"' in out and 'n: "12345"' in out and 'w: "36,200"' in out and 'price: "112.40"' in out
    assert "word: Track 1" in out
    assert yaml.safe_load(out)[0]["n"] == "12345"
