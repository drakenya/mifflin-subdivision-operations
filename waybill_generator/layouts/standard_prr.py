from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import black, HexColor
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import (
    WaybillBase, WaybillType,
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

_PRR_TUSCAN = HexColor("#7B1113")
_LIGHT_GRAY = HexColor("#EEEEEE")


class StandardPrrLayout(BaseLayout):

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.setFillColor(_PRR_TUSCAN)
        canvas.rect(x, y, w, h, fill=1)

        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(x + 3, y + h - 11, car.road)

        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(x + w / 2, y + h - 11, car.car_type)
        canvas.drawRightString(x + w - 3, y + h - 11, car.car_number)

        canvas.setFont("Helvetica", 7)
        capacity = f"{car.capacity_tons}T"
        if car.capacity_cuft:
            capacity += f"  {car.capacity_cuft} cu ft"
        canvas.drawString(x + 3, y + 3, capacity)

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.setFillColor(black)
        canvas.rect(x, y, w, h)

        match waybill.waybill_type:
            case WaybillType.LOADED:
                self._draw_loaded(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.EMPTY:
                self._draw_empty(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.DEADHEAD:
                self._draw_deadhead(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.MOW:
                self._draw_mow(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.HOLD:
                self._draw_hold(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.BAD_ORDER:
                self._draw_bad_order(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"Unhandled waybill type: {waybill.waybill_type}")

    def _label(self, canvas: Canvas, text: str, x: float, y: float, w: float) -> None:
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(HexColor("#666666"))
        canvas.drawString(x, y, text.upper())

    def _value(self, canvas: Canvas, text: str, x: float, y: float, size: int = 8) -> None:
        canvas.setFont("Helvetica-Bold", size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _type_badge(self, canvas: Canvas, text: str, x: float, y: float, w: float, color: HexColor) -> None:
        canvas.setFillColor(color)
        canvas.rect(x, y, w, 10, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawCentredString(x + w / 2, y + 2, text)

    def _draw_loaded(self, canvas: Canvas, w: LoadedWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "LOADED", x, y + h - 11, ww, _PRR_TUSCAN)
        self._label(canvas, "Commodity", x + 2, y + h - 22, ww)
        self._value(canvas, w.commodity_id, x + 2, y + h - 31)
        self._label(canvas, "From (Shipper)", x + 2, y + h - 44, ww)
        self._value(canvas, w.shipper_id, x + 2, y + h - 53)
        self._label(canvas, "To (Consignee)", x + 2, y + h - 66, ww)
        self._value(canvas, w.consignee_id, x + 2, y + h - 75)
        if w.routing:
            self._label(canvas, "Via", x + 2, y + h - 88, ww)
            self._value(canvas, " → ".join(w.routing), x + 2, y + h - 97, size=7)

    def _draw_empty(self, canvas: Canvas, w: EmptyWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "EMPTY", x, y + h - 11, ww, HexColor("#4A4A4A"))
        self._label(canvas, "From", x + 2, y + h - 22, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 31)
        self._label(canvas, "To", x + 2, y + h - 44, ww)
        self._value(canvas, w.to_location_id, x + 2, y + h - 53)

    def _draw_deadhead(self, canvas: Canvas, w: DeadheadWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "DEADHEAD", x, y + h - 11, ww, HexColor("#2B5EA7"))
        self._label(canvas, "From", x + 2, y + h - 22, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 31)
        self._label(canvas, "To", x + 2, y + h - 44, ww)
        self._value(canvas, w.to_location_id, x + 2, y + h - 53)
        if w.consist_note:
            self._label(canvas, "Consist", x + 2, y + h - 66, ww)
            self._value(canvas, w.consist_note, x + 2, y + h - 75, size=7)

    def _draw_mow(self, canvas: Canvas, w: MoWWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "M-O-W", x, y + h - 11, ww, HexColor("#5A7A2E"))
        self._label(canvas, "Material", x + 2, y + h - 22, ww)
        self._value(canvas, w.commodity_desc, x + 2, y + h - 31)
        self._label(canvas, "From", x + 2, y + h - 44, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 53)
        self._label(canvas, "To", x + 2, y + h - 66, ww)
        self._value(canvas, w.to_location_id, x + 2, y + h - 75)
        if w.project:
            self._label(canvas, "Project", x + 2, y + h - 88, ww)
            self._value(canvas, w.project, x + 2, y + h - 97, size=6)

    def _draw_hold(self, canvas: Canvas, w: HoldWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "HOLD", x, y + h - 11, ww, HexColor("#996633"))
        self._label(canvas, "Hold At", x + 2, y + h - 22, ww)
        self._value(canvas, w.industry_id, x + 2, y + h - 31)
        self._label(canvas, "Waiting For", x + 2, y + h - 44, ww)
        self._value(canvas, w.waiting_for, x + 2, y + h - 53, size=7)

    def _draw_bad_order(self, canvas: Canvas, w: BadOrderWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "BAD ORDER", x, y + h - 11, ww, HexColor("#CC0000"))
        self._label(canvas, "From", x + 2, y + h - 22, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 31)
        self._label(canvas, "Shop", x + 2, y + h - 44, ww)
        self._value(canvas, w.shop_location_id, x + 2, y + h - 53)
        if w.defect:
            self._label(canvas, "Defect", x + 2, y + h - 66, ww)
            self._value(canvas, w.defect, x + 2, y + h - 75, size=7)
