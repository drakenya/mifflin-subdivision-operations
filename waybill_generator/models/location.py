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
    subdivision: str | None = None
    industries: list[Industry] = []
