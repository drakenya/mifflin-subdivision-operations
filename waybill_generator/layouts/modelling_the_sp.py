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
# Other value-font candidates tried and kept in fonts/ for comparison:
# Underwood Quiet Tab.ttf (original), Special Elite.ttf, Courier Prime Bold.ttf,
# Courier Prime Regular.ttf, OCR-A.ttf. Revisit if OCR-B doesn't hold up.
_TYPEWRITER_FONT = "OCR-B"
_FONT_FILE = Path(__file__).parent.parent / "fonts" / "OCR-B.ttf"

# Other label-font candidates tried and kept in fonts/ for comparison:
# Arial.ttf (original), League Gothic.ttf (ruled out -- too hard to read),
# Oswald.ttf, Fjalla One.ttf. Revisit if News Cycle doesn't hold up.
_LABEL_FONT = "NewsCycle"
_LABEL_FONT_FILE = Path(__file__).parent.parent / "fonts" / "News Cycle.ttf"

_RAILROAD_NAME_FONT = "PTSans"
_RAILROAD_NAME_FONT_FILE = Path(__file__).parent.parent / "fonts" / "PT Sans.ttf"

# Other headline-font candidates tried and kept in fonts/ for comparison:
# Old Standard TT Bold.ttf. Revisit if Arvo doesn't hold up.
_HEADLINE_FONT = "Arvo-Bold"
_HEADLINE_FONT_FILE = Path(__file__).parent.parent / "fonts" / "Arvo Bold.ttf"

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


def _register_label_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.getFont(_LABEL_FONT)
    except KeyError:
        pdfmetrics.registerFont(TTFont(_LABEL_FONT, str(_LABEL_FONT_FILE)))


def _register_railroad_name_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.getFont(_RAILROAD_NAME_FONT)
    except KeyError:
        pdfmetrics.registerFont(TTFont(_RAILROAD_NAME_FONT, str(_RAILROAD_NAME_FONT_FILE)))


def _register_headline_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.getFont(_HEADLINE_FONT)
    except KeyError:
        pdfmetrics.registerFont(TTFont(_HEADLINE_FONT, str(_HEADLINE_FONT_FILE)))


class ModellingTheSpLayout(BaseLayout):
    value_font: str = _TYPEWRITER_FONT
    label_font: str = _LABEL_FONT
    railroad_name_font: str = _RAILROAD_NAME_FONT
    headline_font: str = _HEADLINE_FONT
    origination_height_pt: float = 42.0

    def __init__(self) -> None:
        _register_typewriter_font()
        _register_label_font()
        _register_railroad_name_font()
        _register_headline_font()
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
        canvas.setFont(self.railroad_name_font, 7)
        canvas.drawCentredString(x + w / 2, y + h - 15, railroad.name)

        # Bill type -- large bold, dominant element
        canvas.setFont(self.headline_font, 12)
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
        canvas.rect(x, y, w, h, fill=1, stroke=0)

        mid = x + w / 2
        canvas.setFillColor(black)

        # Row 1: CAR INITIAL | CAR NUMBER
        row1_top = y + h
        row1_rule = y + h - 24
        self._label(canvas, "CAR INITIAL", x, row1_top, top_width=2.0)
        self._label(canvas, "CAR NUMBER", mid, row1_top, top_width=2.0, left_width=0.4)

        half_w = w / 2 - 6
        row1_label_bottom = self._label_bottom(row1_top, top_width=2.0)
        row1_value_y = self._centered_value_baseline(row1_label_bottom, row1_rule)
        self._value_fit(canvas, car.road, x + 3, row1_value_y, half_w)
        self._value_fit(canvas, car.car_number, mid + 3, row1_value_y, half_w)

        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(mid, y + h - 24, mid, y + h)

        # Rule between rows
        canvas.setLineWidth(0.5)
        canvas.line(x, y + h - 24, x + w, y + h - 24)

        # Row 2: AAR CLASS OF CAR ORDERED | LENGTH/CAPY OF CAR ORDERED
        row2_top = y + h - 24
        row2_rule = y
        self._label(canvas, "AAR CLASS OF CAR ORDERED", x, row2_top)
        self._label(canvas, "LENGTH/CAPY OF CAR ORDERED", mid, row2_top, left_width=0.4)

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
        row2_label_bottom = self._label_bottom(row2_top)
        row2_value_y = self._centered_value_baseline(row2_label_bottom, row2_rule, rule_width=2.0)
        self._value_fit(canvas, aar_display, x + 3, row2_value_y, half_w)
        self._value_fit(canvas, length_cap, mid + 3, row2_value_y, half_w)

        canvas.setLineWidth(0.4)
        canvas.line(mid, y, mid, y + h - 24)

    # -- Waybill Section ------------------------------------------------------

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        self._rule(canvas, x, y + h, w, width=2.0)

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

    def _rule(self, canvas: Canvas, x: float, y: float, w: float, width: float = 0.5) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(width)
        canvas.line(x, y, x + w, y)

    def _vcol(self, canvas: Canvas, x: float, y: float, h: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(x, y, x, y + h)

    _LABEL_SIZE: float = 4.5
    _LABEL_INSET: float = 2.5

    def _label_cap_height(self) -> float:
        """Height of the tallest glyph above the baseline, in points, at _LABEL_SIZE."""
        from reportlab.pdfbase import pdfmetrics
        face = pdfmetrics.getFont(self.label_font).face
        return face.bbox[3] / face.unitsPerEm * self._LABEL_SIZE

    def _label_bottom(self, box_top: float, top_width: float = 0.5) -> float:
        """Baseline y of a label drawn at box_top -- the visual bottom of its text."""
        return box_top - top_width / 2 - self._LABEL_INSET - self._label_cap_height()

    def _label(
        self, canvas: Canvas, text: str, box_left: float, box_top: float,
        top_width: float = 0.5, left_width: float = 0.0,
    ) -> None:
        """Draw a field label so the visual top of the text and its left edge
        are inset equally from the top and left of its box.

        top_width/left_width are the stroke widths of the rule above and the
        divider to the left (0 if there is no divider) -- a stroked line is
        centered on its coordinate, so half its width eats into the visible
        gap and must be added back for the two gaps to look equal.
        """
        canvas.setFont(self.label_font, self._LABEL_SIZE)
        canvas.setFillColor(black)
        canvas.drawString(
            box_left + left_width / 2 + self._LABEL_INSET,
            self._label_bottom(box_top, top_width),
            text,
        )

    def _value_cap_height(self, size: float = 8) -> float:
        """Height of the tallest glyph above the baseline, in points, at the given size."""
        from reportlab.pdfbase import pdfmetrics
        face = pdfmetrics.getFont(self.value_font).face
        return face.bbox[3] / face.unitsPerEm * size

    def _will_wrap(self, text: str, max_width: float, size: float = 8) -> bool:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        return stringWidth(text.upper(), self.value_font, size) > max_width

    def _centered_value_baseline(
        self, label_bottom: float, rule_y: float, rule_width: float = 0.5, size: float = 8,
    ) -> float:
        """Baseline for a single-line value centered between a rule and the label above it."""
        cap = self._value_cap_height(size)
        midpoint = (rule_y + rule_width / 2 + label_bottom) / 2
        return midpoint - cap / 2

    def _centered_wrap_baseline(
        self, label_bottom: float, rule_y: float, text: str, max_width: float,
        rule_width: float = 0.5, size: float = 8, line_gap: float = 2,
    ) -> float:
        """Baseline for a value (1 or 2 lines, whichever _value_wrap will use)
        centered as a whole between a rule and the label above it."""
        cap = self._value_cap_height(size)
        midpoint = (rule_y + rule_width / 2 + label_bottom) / 2
        if self._will_wrap(text, max_width, size):
            return midpoint + (size + line_gap - cap) / 2
        return midpoint - cap / 2

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
        """Bold centered section header, no surrounding rules."""
        canvas.setFont(self.headline_font, 9)
        canvas.setFillColor(black)
        canvas.drawCentredString(x + w / 2, y + 3, text)

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
        label_top = cursor
        rule_y = label_top - 35
        self._label(canvas, "TO STATION, STATE", x, label_top, top_width=2.0)
        self._label(canvas, "FROM STATION, STATE", mid, label_top, top_width=2.0, left_width=0.4)
        label_bottom = self._label_bottom(label_top, top_width=2.0)
        self._value_wrap(
            canvas, to_val, x + 2,
            self._centered_wrap_baseline(label_bottom, rule_y, to_val, col_w, line_gap=2),
            col_w, line_gap=2,
        )
        self._value_wrap(
            canvas, from_val, mid + 2,
            self._centered_wrap_baseline(label_bottom, rule_y, from_val, col_w, line_gap=2),
            col_w, line_gap=2,
        )
        self._vcol(canvas, mid, rule_y, label_top - rule_y)
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        # CONSIGNEE AND ADDRESS | SHIPPER (2-line, second line truncates)
        consignee_val = w.consignee_name or w.consignee_id
        shipper_val = w.shipper_name or w.shipper_id
        label_top = cursor
        rule_y = label_top - 32
        self._label(canvas, "CONSIGNEE AND ADDRESS", x, label_top)
        self._label(canvas, "SHIPPER", mid, label_top, left_width=0.4)
        label_bottom = self._label_bottom(label_top)
        self._value_wrap(
            canvas, consignee_val, x + 2,
            self._centered_wrap_baseline(label_bottom, rule_y, consignee_val, col_w),
            col_w,
        )
        self._value_wrap(
            canvas, shipper_val, mid + 2,
            self._centered_wrap_baseline(label_bottom, rule_y, shipper_val, col_w),
            col_w,
        )
        self._vcol(canvas, mid, rule_y, label_top - rule_y)
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        # ROUTE | STOP THIS CAR AT
        label_top = cursor
        rule_y = label_top - 22
        self._label(canvas, "ROUTE Show in route order", x, label_top)
        self._label(canvas, "STOP THIS CAR AT", mid, label_top, left_width=0.4)
        label_bottom = self._label_bottom(label_top)
        value_y = self._centered_value_baseline(label_bottom, rule_y)
        if w.routing:
            self._value_fit(canvas, " - ".join(w.routing), x + 2, value_y, ww / 2 - 4)
        if w.stop_at:
            self._value_fit(canvas, w.stop_at, mid + 2, value_y, ww / 2 - 4)
        self._vcol(canvas, mid, rule_y, label_top - rule_y)
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        # ON C.L. TRAFFIC INSTRUCTIONS
        label_top = cursor
        rule_y = label_top - 21
        self._label(canvas, "ON C.L. TRAFFIC INSTRUCTIONS (Regarding Icing, Ventilation, Etc.) & EXCEPTIONS", x, label_top)
        if w.notes:
            label_bottom = self._label_bottom(label_top)
            self._value_fit(canvas, w.notes, x + 2, self._centered_value_baseline(label_bottom, rule_y), ww - 4)

        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        # NO. PKGS. | DESCRIPTION OF ARTICLES column headers
        pkgs_col = x + 32
        self._label(canvas, "NO. PKGS.", x, cursor)
        self._label(canvas, "DESCRIPTION OF ARTICLES", pkgs_col, cursor)
        cursor -= 10

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

        label_top = cursor
        rule_y = label_top - 16
        self._label(canvas, "Billed from", x, label_top, top_width=0)
        if w.home_billed_from:
            label_bottom = self._label_bottom(label_top, top_width=0)
            self._value_fit(
                canvas, w.home_billed_from, x + 33,
                self._centered_value_baseline(label_bottom, rule_y), ww - 35,
            )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        col_rr = x + ww * 3 / 4
        label_top = cursor
        rule_y = label_top - 16
        self._label(canvas, "To or Via", x, label_top)
        self._label(canvas, "R.R.", col_rr, label_top, left_width=0.4)
        self._vcol(canvas, col_rr, rule_y, label_top - rule_y)
        label_bottom = self._label_bottom(label_top)
        value_y = self._centered_value_baseline(label_bottom, rule_y, rule_width=0.85)
        if w.home_to_or_via:
            self._value_fit(canvas, w.home_to_or_via, x + 28, value_y, col_rr - x - 30)
        if w.home_rr:
            self._value_fit(canvas, w.home_rr, col_rr + 2, value_y, ww / 4 - 4)
        self._rule(canvas, x, rule_y, ww, width=0.85)
        cursor = rule_y - 8

        # ── FOR LOADING ───────────────────────────────────────────────────
        cursor -= 10
        self._section_header(canvas, "FOR LOADING", x, cursor, ww)
        cursor -= 3

        label_top = cursor
        rule_y = label_top - 16
        self._label(canvas, "Billed from", x, label_top, top_width=0)
        label_bottom = self._label_bottom(label_top, top_width=0)
        self._value_fit(
            canvas, w.from_location_id, x + 30,
            self._centered_value_baseline(label_bottom, rule_y), ww - 32,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        label_top = cursor
        rule_y = label_top - 16
        self._label(canvas, "To", x, label_top)
        label_bottom = self._label_bottom(label_top)
        self._value_fit(
            canvas, w.to_location_id, x + 10,
            self._centered_value_baseline(label_bottom, rule_y), ww - 12,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        label_top = cursor
        rule_y = label_top - 16
        self._label(canvas, "Shipper", x, label_top)
        self._label(canvas, "Spot", mid, label_top, left_width=0.4)
        label_bottom = self._label_bottom(label_top)
        value_y = self._centered_value_baseline(label_bottom, rule_y)
        if w.shipper_ordered_by:
            self._value_fit(canvas, w.shipper_ordered_by, x + 2, value_y, mid - x - 4)
        if w.spot:
            self._value_fit(canvas, w.spot, mid + 2, value_y, x + ww - mid - 4)
        self._vcol(canvas, mid, rule_y, label_top - rule_y)
        self._rule(canvas, x, rule_y, ww)

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
        cursor = y + h

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "FROM", x, label_top, top_width=2.0)
        label_bottom = self._label_bottom(label_top, top_width=2.0)
        self._value_fit(
            canvas, w.from_location_id, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "TO", x, label_top)
        label_bottom = self._label_bottom(label_top)
        self._value_fit(
            canvas, w.to_location_id, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        if w.consist_note:
            self._label(canvas, "CONSIST", x, cursor)
            cursor -= 10
            self._value_wrap(canvas, w.consist_note, x + 2, cursor - 9, ww - 4, line_gap=2)

    def _draw_mow(
        self, canvas: Canvas, w: MoWWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "MATERIAL", x, label_top, top_width=2.0)
        label_bottom = self._label_bottom(label_top, top_width=2.0)
        self._value_fit(
            canvas, w.commodity_desc, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "FROM", x, label_top)
        label_bottom = self._label_bottom(label_top)
        self._value_fit(
            canvas, w.from_location_id, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "TO", x, label_top)
        label_bottom = self._label_bottom(label_top)
        self._value_fit(
            canvas, w.to_location_id, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        if w.project:
            self._label(canvas, "PROJECT", x, cursor)
            cursor -= 10
            self._value_wrap(canvas, w.project, x + 2, cursor - 9, ww - 4, line_gap=2)

    def _draw_hold(
        self, canvas: Canvas, w: HoldWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "HOLD AT", x, label_top, top_width=2.0)
        label_bottom = self._label_bottom(label_top, top_width=2.0)
        self._value_fit(
            canvas, w.industry_id, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        self._label(canvas, "WAITING FOR", x, cursor)
        cursor -= 10
        self._value_wrap(canvas, w.waiting_for, x + 2, cursor - 9, ww - 4, line_gap=2)

    def _draw_bad_order(
        self, canvas: Canvas, w: BadOrderWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "FROM", x, label_top, top_width=2.0)
        label_bottom = self._label_bottom(label_top, top_width=2.0)
        self._value_fit(
            canvas, w.from_location_id, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        label_top = cursor
        rule_y = label_top - 24
        self._label(canvas, "REPAIR SHOP", x, label_top)
        label_bottom = self._label_bottom(label_top)
        self._value_fit(
            canvas, w.shop_location_id, x + 2,
            self._centered_value_baseline(label_bottom, rule_y), ww - 4,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        if w.defect:
            self._label(canvas, "DEFECT", x, cursor)
            cursor -= 10
            self._value_wrap(canvas, w.defect, x + 2, cursor - 9, ww - 4, line_gap=2)
