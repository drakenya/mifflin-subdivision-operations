from pydantic import BaseModel


class Industry(BaseModel):
    id: str
    name: str
    location_id: str
    track: str | None = None
    car_capacity: int | None = None
    ships: list[str] = []
    receives: list[str] = []


class Location(BaseModel):
    id: str
    name: str
    state: str = "PA"
    railroad_id: str | None = None
    on_layout: bool = False
    industries: list[Industry] = []
