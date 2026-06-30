from pydantic import BaseModel


class CatalogIndustry(BaseModel):
    id: str
    name: str
    city: str
    state: str = "PA"
    railroad_id: str | None = None
    source: str
    source_file: str
    source_ref: str | None = None
    ships: list[str] = []
    receives: list[str] = []
    car_types: list[str] = []
    notes: str | None = None
