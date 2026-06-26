from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import black, HexColor
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import (
    WaybillBase, WaybillType,
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

_PRR_TUSCAN = HexColor("#7B1113")
_WHITE = HexColor("#FFFFFF")
_TYPEWRITER_FONT = "UnderwoodQuietTab"
_FONT_FILE = Path(__file__).parent.parent / "fonts" / "Underwood Quiet Tab.ttf"

_BILL_TYPE_LABELS: dict[WaybillType, str] = {
    WaybillType.LOADED: "FREIGHT WAYBILL",
    WaybillType.EMPTY: "EMPTY CAR BILL",
    WaybillType.DEADHEAD: "DEADHEAD ORDER",
    WaybillType.MOW: "M-O-W SERVICE BILL",
    WaybillType.HOLD: "HOLD ORDER",
    WaybillType.BAD_ORDER: "BAD ORDER CARD",
}


def _register_typewriter_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.getFont(_TYPEWRITER_FONT)
    except KeyError:
        pdfmetrics.registerFont(TTFont(_TYPEWRITER_FONT, str(_FONT_FILE)))


class StandardPrrLayout(BaseLayout):
    value_font: str = _TYPEWRITER_FONT

    def __init__(self) -> None:
        _register_typewriter_font()

    # -- Origination Band -----------------------------------------------------

    def draw_origination_section(
        self,
        canvas: Canvas,
        railroad: Railroad,
        waybill: WaybillBase,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)  # bottom rule

        # Herald icon -- left-aligned if path exists
        icon_right = x
        if railroad.icon:
            icon_path = Path(railroad.icon)
            if icon_path.exists():
                icon_size = h - 4
                canvas.drawImage(
                    str(icon_path), x + 2, y + 2,
                    width=icon_size, height=icon_size,
                    preserveAspectRatio=True, mask="auto",
                )
                icon_right = x + icon_size + 4

        bill_label = _BILL_TYPE_LABELS[waybill.waybill_type]

        # Form number -- top-left corner
        canvas.setFont(self.label_font, 5)
        canvas.setFillColor(black)
        canvas.drawString(icon_right + 2, y + h - 7, railroad.form_number)
        canvas.drawRightString(x + w, y + h - 7, railroad.form_number)

        # Railroad name -- centered
        canvas.setFont(self.label_font, 8)
        canvas.drawCentredString(x + w / 2, y + h / 2 + 1, railroad.name)

        # Bill type -- centered below railroad name
        canvas.setFont(self.label_font, 6)
        canvas.drawCentredString(x + w / 2, y + 4, bill_label)

    # -- Car Section ----------------------------------------------------------

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setFillColor(_WHITE)
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.rect(x, y, w, h, fill=1)

        mid = x + w / 2
        canvas.setFillColor(black)

        # Row 1: CAR INITIAL | CAR NUMBER
        canvas.setFont(self.label_font, 5)
        canvas.drawString(x + 3, y + h - 8, "CAR INITIAL")
        canvas.drawString(mid + 3, y + h - 8, "CAR NUMBER")

        canvas.setFont(self.value_font, 10)
        canvas.drawString(x + 3, y + h - 20, car.road)
        canvas.drawString(mid + 3, y + h - 20, car.car_number)

        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(mid, y + h - 6, mid, y + h - 22)

        # Rule between rows
        canvas.setLineWidth(0.5)
        canvas.line(x, y + h - 24, x + w, y + h - 24)

        # Row 2: AAR CLASS | CAPACITY
        canvas.setFont(self.label_font, 5)
        canvas.drawString(x + 3, y + h - 31, "AAR CLASS")
        canvas.drawString(mid + 3, y + h - 31, "CAPACITY")

        cap = f"{car.capacity_tons}T"
        if car.capacity_cuft:
            cap += f"  {car.capacity_cuft} CF"
        canvas.setFont(self.value_font, 8)
        canvas.drawString(x + 3, y + h - 42, car.aar_code)
        canvas.drawString(mid + 3, y + h - 42, cap)

        canvas.setLineWidth(0.4)
        canvas.line(mid, y + h - 29, mid, y + h - 44)

    # -- Waybill Section ------------------------------------------------------

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
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

    # -- Shared drawing primitives --------------------------------------------

    def _rule(self, canvas: Canvas, x: float, y: float, w: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)

    def _vcol(self, canvas: Canvas, x: float, y: float, h: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(x, y, x, y + h)

    def _label(self, canvas: Canvas, text: str, x: float, y: float) -> None:
        canvas.setFont(self.label_font, 5)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _value(self, canvas: Canvas, text: str, x: float, y: float, size: int = 9) -> None:
        canvas.setFont(self.value_font, size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _value_fit(
        self, canvas: Canvas, text: str, x: float, y: float, max_width: float, max_size: int = 7
    ) -> None:
        """Draw value font text, shrinking then truncating to stay within max_width."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        for size in range(max_size, 3, -1):
            if stringWidth(text, self.value_font, size) <= max_width:
                canvas.setFont(self.value_font, size)
                canvas.setFillColor(black)
                canvas.drawString(x, y, text)
                return
        size = 4
        truncated = text
        while truncated and stringWidth(truncated + "…", self.value_font, size) > max_width:
            truncated = truncated[:-1]
        canvas.setFont(self.value_font, size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, truncated + ("…" if truncated != text else ""))

    def _value_wrap(
        self, canvas: Canvas, text: str, x: float, y: float, max_width: float,
        size: int = 9, line_gap: int = 2,
    ) -> None:
        """Draw value font text, wrapping to a second line at the nearest word boundary."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        canvas.setFillColor(black)
        if stringWidth(text, self.value_font, size) <= max_width:
            canvas.setFont(self.value_font, size)
            canvas.drawString(x, y, text)
            return
        words = text.split()
        line1 = ""
        split_at = len(words)
        for i, word in enumerate(words):
            candidate = (line1 + " " + word).strip()
            if stringWidth(candidate, self.value_font, size) > max_width:
                split_at = i
                break
            line1 = candidate
        if not line1:
            line1 = words[0]
            split_at = 1
        line2 = " ".join(words[split_at:])
        canvas.setFont(self.value_font, size)
        canvas.drawString(x, y, line1)
        if line2:
            canvas.drawString(x, y - size - line_gap, line2)

    def _section_header(self, canvas: Canvas, text: str, x: float, y: float, w: float) -> None:
        """Bold centered section header with double rules above and below."""
        canvas.setFont("Times-Bold", 9)
        canvas.setFillColor(black)
        canvas.drawCentredString(x + w / 2, y + 3, text)
        self._rule(canvas, x, y + 14, w)
        self._rule(canvas, x, y + 1, w)

    # -- Waybill type renderers -----------------------------------------------

    def _draw_loaded(
        self, canvas: Canvas, w: LoadedWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        mid = x + ww / 2
        col3 = x + ww * 2 / 3
        cursor = y + h

        # TO STATION, STATE | FROM STATION, STATE — large, most prominent row (2-line capable)
        to_val = f"{w.to_city}, {w.to_state}" if w.to_city else w.consignee_id
        from_val = f"{w.from_city}, {w.from_state}" if w.from_city else w.shipper_id
        col_w = mid - (x + 4)
        cursor -= 4
        self._label(canvas, "TO STATION, STATE", x + 2, cursor - 5)
        self._label(canvas, "FROM STATION, STATE", mid + 2, cursor - 5)
        cursor -= 7
        self._value_wrap(canvas, to_val, x + 2, cursor - 10, col_w, size=10, line_gap=2)
        self._value_wrap(canvas, from_val, mid + 2, cursor - 10, col_w, size=10, line_gap=2)
        self._vcol(canvas, mid, cursor - 24, 30)
        cursor -= 26
        self._rule(canvas, x, cursor, ww)

        # CONSIGNEE AND ADDRESS | SHIPPER (2-line capable)
        consignee_val = w.consignee_name or w.consignee_id
        shipper_val = w.shipper_name or w.shipper_id
        cursor -= 3
        self._label(canvas, "CONSIGNEE AND ADDRESS", x + 2, cursor - 5)
        self._label(canvas, "SHIPPER", mid + 2, cursor - 5)
        cursor -= 7
        self._value_wrap(canvas, consignee_val, x + 2, cursor - 9, col_w, size=7, line_gap=2)
        self._value_wrap(canvas, shipper_val, mid + 2, cursor - 9, col_w, size=7, line_gap=2)
        self._vcol(canvas, mid, cursor - 20, 25)
        cursor -= 22
        self._rule(canvas, x, cursor, ww)

        # ROUTE | STOP THIS CAR AT
        cursor -= 3
        self._label(canvas, "ROUTE — SHOW IN ROUTE ORDER", x + 2, cursor - 5)
        self._label(canvas, "STOP THIS CAR AT", col3 + 2, cursor - 5)
        cursor -= 7
        if w.routing:
            self._value(canvas, " - ".join(w.routing), x + 2, cursor - 8, size=7)
        if w.stop_at:
            self._value_fit(canvas, w.stop_at, col3 + 2, cursor - 8, ww - (col3 - x) - 4, max_size=7)
        self._vcol(canvas, col3, cursor - 11, 18)
        cursor -= 12
        self._rule(canvas, x, cursor, ww)

        # LCL TRAFFIC INSTRUCTIONS
        cursor -= 3
        self._label(canvas, "LCL TRAFFIC INSTRUCTIONS", x + 2, cursor - 5)
        cursor -= 7
        if w.notes:
            canvas.setFont("Times-Roman", 6)
            canvas.setFillColor(black)
            canvas.drawString(x + 2, cursor - 7, w.notes[:55])
        cursor -= 11
        self._rule(canvas, x, cursor, ww)

        # NO. PKGS. | DESCRIPTION OF ARTICLES column headers
        pkgs_col = x + 22
        cursor -= 2
        self._label(canvas, "NO. PKGS.", x + 2, cursor - 5)
        self._label(canvas, "DESCRIPTION OF ARTICLES", pkgs_col + 3, cursor - 5)
        cursor -= 6
        self._vcol(canvas, pkgs_col, cursor, 8)
        self._rule(canvas, x, cursor, ww)

        # Commodity
        cursor -= 4
        self._value(canvas, w.commodity_id.upper(), pkgs_col + 3, cursor - 9, size=8)

    def _draw_empty(
        self, canvas: Canvas, w: EmptyWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h
        mid = x + ww / 2

        # ── FOR HOME ──────────────────────────────────────────────────────
        cursor -= 17
        self._section_header(canvas, "FOR HOME", x, cursor, ww)
        cursor -= 3

        self._label(canvas, "Billed from", x + 2, cursor - 6)
        if w.home_billed_from:
            self._value(canvas, w.home_billed_from, x + 33, cursor - 7, size=7)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 10

        col_rr = x + ww * 3 / 4
        self._label(canvas, "To or Via", x + 2, cursor - 6)
        self._label(canvas, "R.R.", col_rr + 2, cursor - 6)
        if w.home_to_or_via:
            self._value_fit(canvas, w.home_to_or_via, x + 28, cursor - 7, col_rr - x - 30, max_size=7)
        if w.home_rr:
            self._value(canvas, w.home_rr, col_rr + 2, cursor - 7, size=7)
            self._vcol(canvas, col_rr, cursor - 9, 11)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 8

        # ── FOR LOADING ───────────────────────────────────────────────────
        cursor -= 10
        self._section_header(canvas, "FOR LOADING", x, cursor, ww)
        cursor -= 3

        self._label(canvas, "Billed from", x + 2, cursor - 6)
        self._value(canvas, w.from_location_id, x + 30, cursor - 7, size=9)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 8

        self._label(canvas, "To", x + 2, cursor - 6)
        self._value(canvas, w.to_location_id, x + 10, cursor - 7, size=9)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 8

        self._label(canvas, "Shipper", x + 2, cursor - 6)
        self._label(canvas, "Spot", mid + 2, cursor - 6)
        if w.shipper_ordered_by or w.spot:
            self._value(canvas, w.shipper_ordered_by or "", x + 2, cursor - 14, size=7)
            self._value(canvas, w.spot or "", mid + 2, cursor - 14, size=7)
        cursor -= 14
        self._vcol(canvas, mid, cursor, 16)
        self._rule(canvas, x, cursor, ww)

        # Instructions
        canvas.setFont(self.label_font, 4)
        canvas.setFillColor(black)
        canvas.drawString(x + 2, y + 20,
            "INSTRUCTIONS – This form must accompany all empty foreign cars,")
        canvas.drawString(x + 2, y + 14,
            "and System empty cars intended for loading, per General Order Ten.")

    def _draw_deadhead(
        self, canvas: Canvas, w: DeadheadWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.from_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "TO", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.to_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.consist_note:
            cursor -= 2
            self._label(canvas, "CONSIST", x + 2, cursor - 6)
            cursor -= 8
            self._value_wrap(canvas, w.consist_note, x + 2, cursor - 9, ww - 4, size=7, line_gap=2)

    def _draw_mow(
        self, canvas: Canvas, w: MoWWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "MATERIAL", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.commodity_desc, x + 2, cursor - 10, ww - 4, max_size=9)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.from_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "TO", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.to_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.project:
            cursor -= 2
            self._label(canvas, "PROJECT", x + 2, cursor - 6)
            cursor -= 8
            self._value_wrap(canvas, w.project, x + 2, cursor - 9, ww - 4, size=6, line_gap=2)

    def _draw_hold(
        self, canvas: Canvas, w: HoldWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "HOLD AT", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.industry_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "WAITING FOR", x + 2, cursor - 6)
        cursor -= 8
        self._value_wrap(canvas, w.waiting_for, x + 2, cursor - 9, ww - 4, size=7, line_gap=2)

    def _draw_bad_order(
        self, canvas: Canvas, w: BadOrderWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.from_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "REPAIR SHOP", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.shop_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.defect:
            cursor -= 2
            self._label(canvas, "DEFECT", x + 2, cursor - 6)
            cursor -= 8
            self._value_wrap(canvas, w.defect, x + 2, cursor - 9, ww - 4, size=7, line_gap=2)
