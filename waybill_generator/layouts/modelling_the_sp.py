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

_ARIAL_FONT = "Arial"
_ARIAL_FILE = Path(__file__).parent.parent / "fonts" / "Arial.ttf"

_AAR_CODES_FILE = Path(__file__).parent.parent.parent / "data" / "aar_codes.yaml"


def _load_aar_codes() -> dict[str, str]:
    import yaml
    if not _AAR_CODES_FILE.exists():
        return {}
    with _AAR_CODES_FILE.open() as f:
        entries = yaml.safe_load(f) or []
    return {e["code"]: e["name"] for e in entries}

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


def _register_arial_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.getFont(_ARIAL_FONT)
    except KeyError:
        pdfmetrics.registerFont(TTFont(_ARIAL_FONT, str(_ARIAL_FILE)))


class ModellingTheSpLayout(BaseLayout):
    value_font: str = _TYPEWRITER_FONT
    label_font: str = _ARIAL_FONT
    origination_height_pt: float = 42.0

    def __init__(self) -> None:
        _register_typewriter_font()
        _register_arial_font()
        self._aar_codes = _load_aar_codes()

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

        # Railroad name -- small, centered
        canvas.setFont(self.label_font, 7)
        canvas.drawCentredString(x + w / 2, y + h - 15, railroad.name)

        # Bill type -- large bold, dominant element
        canvas.setFont("Times-Bold", 12)
        canvas.drawCentredString(x + w / 2, y + h - 28, bill_label)

        # Subtitle -- small, LOADED waybills only
        if waybill.waybill_type == WaybillType.LOADED:
            canvas.setFont(self.label_font, 4)
            canvas.drawCentredString(
                x + w / 2, y + 4,
                "TO BE USED FOR SINGLE CONSIGNMENTS, CARLOAD AND LESS CARLOAD",
            )

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
        canvas.setFont(self.label_font, 4.5)
        canvas.drawString(x + 3, y + h - 8, "CAR INITIAL")
        canvas.drawString(mid + 3, y + h - 8, "CAR NUMBER")

        half_w = w / 2 - 6
        self._value_fit(canvas, car.road, x + 3, y + h - 20, half_w)
        self._value_fit(canvas, car.car_number, mid + 3, y + h - 20, half_w)

        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(mid, y + h - 6, mid, y + h - 22)

        # Rule between rows
        canvas.setLineWidth(0.5)
        canvas.line(x, y + h - 24, x + w, y + h - 24)

        # Row 2: AAR CLASS OF CAR ORDERED | LENGTH/CAPY OF CAR ORDERED
        canvas.setFont(self.label_font, 4.5)
        canvas.drawString(x + 3, y + h - 29, "AAR CLASS OF")
        canvas.drawString(x + 3, y + h - 35, "CAR ORDERED")
        canvas.drawString(mid + 3, y + h - 29, "LENGTH/CAPY OF")
        canvas.drawString(mid + 3, y + h - 35, "CAR ORDERED")

        length_cap = f"{car.length_ft}'" if car.length_ft else ""
        if length_cap:
            length_cap += f"  {car.capacity_tons}T"
        else:
            length_cap = f"{car.capacity_tons}T"
        if car.capacity_cuft:
            length_cap += f"  {car.capacity_cuft} CF"
        aar_display = car.aar_code.upper()
        aar_name = self._aar_codes.get(car.aar_code)
        if aar_name:
            aar_display += f" {aar_name.upper()}"
        self._value_fit(canvas, aar_display, x + 3, y + h - 44, half_w)
        self._value_fit(canvas, length_cap, mid + 3, y + h - 44, half_w)

        canvas.setLineWidth(0.4)
        canvas.line(mid, y + h - 25, mid, y + h - 46)

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
        canvas.setFont(self.label_font, 4.5)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _value(self, canvas: Canvas, text: str, x: float, y: float, size: int = 8) -> None:
        canvas.setFont(self.value_font, size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text.upper())

    def _value_fit(
        self, canvas: Canvas, text: str, x: float, y: float, max_width: float, max_size: int = 8
    ) -> None:
        """Draw value font text at max_size, truncating with ellipsis if too wide."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        text = text.upper()
        if stringWidth(text, self.value_font, max_size) <= max_width:
            canvas.setFont(self.value_font, max_size)
            canvas.setFillColor(black)
            canvas.drawString(x, y, text)
            return
        truncated = text
        while truncated and stringWidth(truncated + "…", self.value_font, max_size) > max_width:
            truncated = truncated[:-1]
        canvas.setFont(self.value_font, max_size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, truncated + ("…" if truncated != text else ""))

    def _value_wrap(
        self, canvas: Canvas, text: str, x: float, y: float, max_width: float,
        size: int = 8, line_gap: int = 2,
    ) -> None:
        """Wrap to a second line at the nearest word boundary; truncate line 2 with ellipsis if needed."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        text = text.upper()
        canvas.setFillColor(black)
        canvas.setFont(self.value_font, size)
        if stringWidth(text, self.value_font, size) <= max_width:
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
        canvas.drawString(x, y, line1)
        if line2:
            while line2 and stringWidth(line2 + "…", self.value_font, size) > max_width:
                line2 = line2[:-1]
            canvas.drawString(x, y - size - line_gap, line2 + ("…" if " ".join(words[split_at:]) != line2 else ""))

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
        cursor = y + h

        # TO STATION, STATE | FROM STATION, STATE — large, most prominent row (2-line capable)
        to_val = f"{w.to_city}, {w.to_state}" if w.to_city else w.consignee_id
        from_val = f"{w.from_city}, {w.from_state}" if w.from_city else w.shipper_id
        col_w = mid - (x + 4)
        cursor -= 4
        self._label(canvas, "TO STATION, STATE", x + 2, cursor - 5)
        self._label(canvas, "FROM STATION, STATE", mid + 2, cursor - 5)
        cursor -= 7
        self._value_wrap(canvas, to_val, x + 2, cursor - 10, col_w, line_gap=2)
        self._value_wrap(canvas, from_val, mid + 2, cursor - 10, col_w, line_gap=2)
        self._vcol(canvas, mid, cursor - 22, 28)
        cursor -= 24
        self._rule(canvas, x, cursor, ww)

        # CONSIGNEE AND ADDRESS | SHIPPER (2-line, second line truncates)
        consignee_val = w.consignee_name or w.consignee_id
        shipper_val = w.shipper_name or w.shipper_id
        cursor -= 3
        self._label(canvas, "CONSIGNEE AND ADDRESS", x + 2, cursor - 5)
        self._label(canvas, "SHIPPER", mid + 2, cursor - 5)
        cursor -= 7
        self._value_wrap(canvas, consignee_val, x + 2, cursor - 9, col_w)
        self._value_wrap(canvas, shipper_val, mid + 2, cursor - 9, col_w)
        self._vcol(canvas, mid, cursor - 22, 26)
        cursor -= 22
        self._rule(canvas, x, cursor, ww)

        # ROUTE | STOP THIS CAR AT
        cursor -= 3
        self._label(canvas, "ROUTE Show in route order", x + 2, cursor - 5)
        self._label(canvas, "STOP THIS CAR AT", mid + 2, cursor - 5)
        cursor -= 7
        if w.routing:
            self._value_fit(canvas, " - ".join(w.routing), x + 2, cursor - 8, ww / 2 - 4)
        if w.stop_at:
            self._value_fit(canvas, w.stop_at, mid + 2, cursor - 8, ww / 2 - 4)
        self._vcol(canvas, mid, cursor - 11, 18)
        cursor -= 12
        self._rule(canvas, x, cursor, ww)

        # ON C.L. TRAFFIC INSTRUCTIONS
        cursor -= 3
        canvas.setFont(self.label_font, 4.5)
        canvas.setFillColor(black)
        canvas.drawString(x + 2, cursor - 5, "ON C.L. TRAFFIC INSTRUCTIONS (Regarding Icing, Ventilation, Etc.)")
        canvas.drawString(x + 2, cursor - 11, "& EXCEPTIONS")
        cursor -= 6
        cursor -= 7
        if w.notes:
            self._value_fit(canvas, w.notes, x + 2, cursor - 7, ww - 4)

        cursor -= 11
        self._rule(canvas, x, cursor, ww)

        # NO. PKGS. | DESCRIPTION OF ARTICLES column headers
        pkgs_col = x + 32
        cursor -= 2
        self._label(canvas, "NO. PKGS.", x + 2, cursor - 5)
        self._label(canvas, "DESCRIPTION OF ARTICLES", pkgs_col + 3, cursor - 5)
        cursor -= 8

        # Commodity
        self._value_fit(canvas, w.commodity_id, pkgs_col + 3, cursor - 9, x + ww - pkgs_col - 5)

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
            self._value_fit(canvas, w.home_billed_from, x + 33, cursor - 7, ww - 35)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 10

        col_rr = x + ww * 3 / 4
        self._label(canvas, "To or Via", x + 2, cursor - 6)
        self._label(canvas, "R.R.", col_rr + 2, cursor - 6)
        self._vcol(canvas, col_rr, cursor - 9, 11)
        if w.home_to_or_via:
            self._value_fit(canvas, w.home_to_or_via, x + 28, cursor - 7, col_rr - x - 30)
        if w.home_rr:
            self._value_fit(canvas, w.home_rr, col_rr + 2, cursor - 7, ww / 4 - 4)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 8

        # ── FOR LOADING ───────────────────────────────────────────────────
        cursor -= 10
        self._section_header(canvas, "FOR LOADING", x, cursor, ww)
        cursor -= 3

        self._label(canvas, "Billed from", x + 2, cursor - 6)
        self._value_fit(canvas, w.from_location_id, x + 30, cursor - 7, ww - 32)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 8

        self._label(canvas, "To", x + 2, cursor - 6)
        self._value_fit(canvas, w.to_location_id, x + 10, cursor - 7, ww - 12)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)
        cursor -= 4

        self._label(canvas, "Shipper", x + 2, cursor - 5)
        self._label(canvas, "Spot", mid + 2, cursor - 5)
        if w.shipper_ordered_by:
            self._value_fit(canvas, w.shipper_ordered_by, x + 2, cursor - 13, mid - x - 4)
        if w.spot:
            self._value_fit(canvas, w.spot, mid + 2, cursor - 13, x + ww - mid - 4)
        cursor -= 16
        self._vcol(canvas, mid, cursor, 17)
        self._rule(canvas, x, cursor, ww)

        # Instructions
        canvas.setFont(self.label_font, 4.5)
        canvas.setFillColor(black)
        canvas.drawString(x + 2, y + 26,
            "INSTRUCTIONS – This form must accompany all empty foreign cars,")
        canvas.drawString(x + 2, y + 20,
            "and System empty cars intended for loading, and must be used in")
        canvas.drawString(x + 2, y + 14,
            "billing private line cars under General Order Ten.")

    def _draw_deadhead(
        self, canvas: Canvas, w: DeadheadWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.from_location_id, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "TO", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.to_location_id, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.consist_note:
            cursor -= 2
            self._label(canvas, "CONSIST", x + 2, cursor - 6)
            cursor -= 8
            self._value_wrap(canvas, w.consist_note, x + 2, cursor - 9, ww - 4, line_gap=2)

    def _draw_mow(
        self, canvas: Canvas, w: MoWWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "MATERIAL", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.commodity_desc, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.from_location_id, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "TO", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.to_location_id, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.project:
            cursor -= 2
            self._label(canvas, "PROJECT", x + 2, cursor - 6)
            cursor -= 8
            self._value_wrap(canvas, w.project, x + 2, cursor - 9, ww - 4, line_gap=2)

    def _draw_hold(
        self, canvas: Canvas, w: HoldWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "HOLD AT", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.industry_id, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "WAITING FOR", x + 2, cursor - 6)
        cursor -= 8
        self._value_wrap(canvas, w.waiting_for, x + 2, cursor - 9, ww - 4, line_gap=2)

    def _draw_bad_order(
        self, canvas: Canvas, w: BadOrderWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.from_location_id, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "REPAIR SHOP", x + 2, cursor - 6)
        cursor -= 8
        self._value_fit(canvas, w.shop_location_id, x + 2, cursor - 10, ww - 4)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.defect:
            cursor -= 2
            self._label(canvas, "DEFECT", x + 2, cursor - 6)
            cursor -= 8
            self._value_wrap(canvas, w.defect, x + 2, cursor - 9, ww - 4, line_gap=2)
