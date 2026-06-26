from enum import Enum
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class WaybillType(str, Enum):
    LOADED = "LOADED"
    EMPTY = "EMPTY"
    DEADHEAD = "DEADHEAD"
    MOW = "MOW"
    HOLD = "HOLD"
    BAD_ORDER = "BAD_ORDER"


class WaybillBase(BaseModel):
    id: str
    waybill_type: WaybillType
    originating_railroad_id: str
    notes: str | None = None


class LoadedWaybill(WaybillBase):
    waybill_type: Literal["LOADED"] = "LOADED"
    commodity_id: str
    shipper_id: str
    consignee_id: str
    routing: list[str] = []
    stop_at: str | None = None
    # Resolved display fields (populated at render time, not stored in YAML)
    to_city: str | None = None
    to_state: str | None = None
    consignee_name: str | None = None
    from_city: str | None = None
    from_state: str | None = None
    shipper_name: str | None = None


class EmptyWaybill(WaybillBase):
    waybill_type: Literal["EMPTY"] = "EMPTY"
    from_location_id: str
    to_location_id: str
    spot: str | None = None
    shipper_ordered_by: str | None = None
    home_billed_from: str | None = None
    home_to_or_via: str | None = None
    home_rr: str | None = None


class DeadheadWaybill(WaybillBase):
    waybill_type: Literal["DEADHEAD"] = "DEADHEAD"
    from_location_id: str
    to_location_id: str
    consist_note: str | None = None


class MoWWaybill(WaybillBase):
    waybill_type: Literal["MOW"] = "MOW"
    commodity_desc: str
    from_location_id: str
    to_location_id: str
    project: str | None = None


class HoldWaybill(WaybillBase):
    waybill_type: Literal["HOLD"] = "HOLD"
    industry_id: str
    waiting_for: str


class BadOrderWaybill(WaybillBase):
    waybill_type: Literal["BAD_ORDER"] = "BAD_ORDER"
    from_location_id: str
    shop_location_id: str
    defect: str | None = None


Waybill = Annotated[
    Union[
        LoadedWaybill, EmptyWaybill, DeadheadWaybill,
        MoWWaybill, HoldWaybill, BadOrderWaybill,
    ],
    Field(discriminator="waybill_type"),
]
