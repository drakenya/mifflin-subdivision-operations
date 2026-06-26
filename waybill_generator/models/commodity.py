from pydantic import BaseModel


class Commodity(BaseModel):
    id: str
    name: str
    aar_code: str | None = None
    acceptable_car_types: list[str] = []
