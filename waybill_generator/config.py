import tomllib

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    layout: str = "ak_main"
    data_source: str = "yaml"
    data_path: str = "./data"
    output_dir: str = "./output"


_FIELDS = {f for f in Config.__dataclass_fields__}


def load_config(config_path: str | Path = "waybill.toml") -> Config:
    path = Path(config_path)
    if not path.exists():
        return Config()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    defaults = {k: v for k, v in data.get("defaults", {}).items() if k in _FIELDS}
    return Config(**defaults)
