import tomllib

from pathlib import Path
from waybill_generator.config import Config, load_config


def test_load_config_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.layout == "modelling_the_sp"
    assert cfg.data_source == "yaml"
    assert cfg.data_path == "./data"
    assert cfg.output_dir == "./output"


def test_load_config_from_toml(tmp_path):
    toml_file = tmp_path / "waybill.toml"
    toml_file.write_text(
        '[defaults]\nlayout = "custom"\ndata_path = "/my/data"\n'
    )
    cfg = load_config(toml_file)
    assert cfg.layout == "custom"
    assert cfg.data_path == "/my/data"
    assert cfg.output_dir == "./output"  # not in file, uses default


def test_load_config_ignores_unknown_keys(tmp_path):
    toml_file = tmp_path / "waybill.toml"
    toml_file.write_text('[defaults]\nunknown_key = "value"\nlayout = "modelling_the_sp"\n')
    cfg = load_config(toml_file)
    assert cfg.layout == "modelling_the_sp"
