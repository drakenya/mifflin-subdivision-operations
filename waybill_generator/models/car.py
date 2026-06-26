from pydantic import BaseModel


class Car(BaseModel):
    id: str
    road: str
    car_number: str
    aar_code: str
    capacity_tons: int
    capacity_cuft: int | None = None
    length_ft: int | None = None
    active: bool = True
    notes: str | None = None
