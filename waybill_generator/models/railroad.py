from pydantic import BaseModel


class Railroad(BaseModel):
    id: str
    name: str
    form_number: str
    icon: str | None = None
