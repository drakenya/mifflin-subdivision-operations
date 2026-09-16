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
    STOP_OFF = "STOP_OFF"
    TEMPORARY = "TEMPORARY"
    PERISHABLE = "PERISHABLE"
    LIVESTOCK = "LIVESTOCK"


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


class StopOffWaybill(WaybillBase):
    """AAR Form AD-142 "Stop Off" pouch -- an overlay card that rides atop
    the regular waybill in the sleeve, flagging a car that must stop
    en route to partially unload or complete loading."""
    waybill_type: Literal["STOP_OFF"] = "STOP_OFF"
    at_location: str
    for_reason: str
    contents: str
    waybilled_from: str


class TemporaryWaybill(WaybillBase):
    """SP Form 704, "Conductor's Memorandum Waybill" -- used when a car
    must move before its regular waybill is ready (e.g. a non-agency
    station pickup). Part 2 of the four-part form travels with the car."""
    waybill_type: Literal["TEMPORARY"] = "TEMPORARY"
    waybill_no: str
    from_location_id: str
    to_location_id: str
    shipper_name: str
    consignee_address: str
    commodity_desc: str
    routing: str | None = None
    weight: str | None = None
    amount_collected: str | None = None


class PerishableWaybill(WaybillBase):
    """Perishable Freight Waybill (pink stock) -- a LOADED variant with
    icing/reconsignment/weight fields, simplified from the AAR original
    the same way Tony Thompson simplified his own model version."""
    waybill_type: Literal["PERISHABLE"] = "PERISHABLE"
    commodity_id: str
    shipper_name: str
    consignee_name: str
    to_city: str
    to_state: str
    from_city: str
    from_state: str
    routing: list[str] = []
    stop_at: str | None = None
    reconsigned_to: str | None = None
    icing_instructions: str | None = None
    pre_ice: str | None = None
    initial_ice: str | None = None
    weighed_note: str | None = None


class LivestockWaybill(WaybillBase):
    """Live Stock Freight Waybill -- shares the Perishable form's skeleton,
    swapping commodity for head count/description and icing fields for
    loading/bedding/feeding questions."""
    waybill_type: Literal["LIVESTOCK"] = "LIVESTOCK"
    description_of_stock: str
    no_head: str
    shipper_name: str
    consignee_name: str
    to_city: str
    to_state: str
    from_city: str
    from_state: str
    routing: list[str] = []
    stop_at: str | None = None
    attendant_in_charge: bool = False
    car_bedded_by_carrier: bool = False
    bedding_furnished_by_carrier: bool = False
    hour_request_signed: bool = False
    time_loaded: str | None = None
    feeding_place: str | None = None


Waybill = Annotated[
    Union[
        LoadedWaybill, EmptyWaybill, DeadheadWaybill,
        MoWWaybill, HoldWaybill, BadOrderWaybill,
        StopOffWaybill, TemporaryWaybill, PerishableWaybill, LivestockWaybill,
    ],
    Field(discriminator="waybill_type"),
]
