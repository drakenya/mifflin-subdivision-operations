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

# Values: "Mom's Typewriter Actual" -- per Tony Thompson's own account of his
# waybill process (modelingthesp.blogspot.com, "Waybills, Part 3" and "Part 5"),
# he fills bills for non-SP/UP roads with one of a handful of typewriter-look
# faces (Bell Gothic is reserved for SP/UP specifically); this is also one of
# the fonts in his own font library, and empirically the closest visual match
# to the reference scan's "DAX" / "210" / "TPI" glyphs of the candidates tried.
_TYPEWRITER_FONT = "MomsTypewriterActual"
_FONT_FILE = Path(__file__).parent.parent / "fonts" / "Moms Typewriter Actual.ttf"

# Mom's Typewriter Actual has no U+2026 (…) glyph -- three periods truncate
# without a missing-glyph box.
_ELLIPSIS = "..."

# Field labels: Franklin Gothic Medium. Arial (used in Andrew Kroll's own
# Publisher waybill templates) tested too light and narrow against the
# reference scan's label weight. Tony Thompson's own typography post
# ("Type and Typography on the Layout") explicitly calls Helvetica-family
# faces anachronistic for pre-1960s modeling and recommends Franklin Gothic
# as the period-correct gothic sans -- and Franklin Gothic Medium, rendered
# at the reference's scale, matched its label weight and proportions closely.
_LABEL_FONT = "FranklinGothicMedium"
_LABEL_FONT_FILE = Path(__file__).parent.parent / "fonts" / "Franklin Gothic Medium.ttf"

# Railroad name + "AAR Form" corner text, and the "FREIGHT WAYBILL" headline:
# measured against the reference scan (width and cap-height as a fraction of
# card size), the base-14 Times family was a closer match than any bundled
# serif -- no font file needed.
_RAILROAD_NAME_FONT = "Times-Roman"
_HEADLINE_FONT = "Times-Bold"

# Subtitle line: bold condensed gothic.
_SUBTITLE_FONT = "Oswald"
_SUBTITLE_FONT_FILE = Path(__file__).parent.parent / "fonts" / "Oswald.ttf"

# "BAD ORDER" stripe text on the bad-order card: a heavy slab serif, closer
# to the reference SP card's blocky lettering than the Times family used
# for the origination headline elsewhere.
_STRIPE_FONT = "ArvoBold"
_STRIPE_FONT_FILE = Path(__file__).parent.parent / "fonts" / "Arvo Bold.ttf"

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


def _register_subtitle_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.getFont(_SUBTITLE_FONT)
    except KeyError:
        pdfmetrics.registerFont(TTFont(_SUBTITLE_FONT, str(_SUBTITLE_FONT_FILE)))


def _register_stripe_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.getFont(_STRIPE_FONT)
    except KeyError:
        pdfmetrics.registerFont(TTFont(_STRIPE_FONT, str(_STRIPE_FONT_FILE)))


class ModelingTheSpLayout(BaseLayout):
    value_font: str = _TYPEWRITER_FONT
    label_font: str = _LABEL_FONT
    railroad_name_font: str = _RAILROAD_NAME_FONT
    headline_font: str = _HEADLINE_FONT
    subtitle_font: str = _SUBTITLE_FONT
    stripe_font: str = _STRIPE_FONT
    origination_height_pt: float = 42.0

    def __init__(self) -> None:
        _register_typewriter_font()
        _register_label_font()
        _register_subtitle_font()
        _register_stripe_font()

    # -- Origination Band -----------------------------------------------------
    # Matched against a scanned AAR Form 98 freight waybill: AAR form number
    # top-right, railroad name centered, bold serif headline dominant,
    # bold condensed-gothic subtitle at the bottom of the band.

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

        canvas.setFillColor(black)

        bill_label = _BILL_TYPE_LABELS[waybill.waybill_type]

        # AAR form number -- small serif, top-right corner
        canvas.setFont(self.railroad_name_font, 4)
        canvas.drawRightString(x + w, y + h - 4, f"AAR {railroad.form_number}")

        # Railroad name -- serif, centered
        canvas.setFont(self.railroad_name_font, 9)
        canvas.drawCentredString(x + w / 2, y + h - 13, railroad.name.upper())

        # Bill type -- large bold serif, dominant element
        canvas.setFont(self.headline_font, 13)
        canvas.drawCentredString(x + w / 2, y + h - 27, bill_label)

        # Subtitle -- bold condensed gothic, LOADED waybills only
        if waybill.waybill_type == WaybillType.LOADED:
            canvas.setFont(self.subtitle_font, 5)
            canvas.drawCentredString(
                x + w / 2, y + 3,
                "TO BE USED FOR SINGLE CONSIGNMENTS, CARLOAD AND LESS CARLOAD",
            )

    # -- Car Section ----------------------------------------------------------
    # Row split (22pt / 14pt of the 36pt zone) and label wrapping matched
    # against the reference scan's proportions.

    car_height_pt: float = 38.0
    _CAR_ROW1_HEIGHT: float = 23.0

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setFillColor(_WHITE)
        canvas.rect(x, y, w, h, fill=1, stroke=0)

        mid = x + w / 2
        canvas.setFillColor(black)
        row_split = y + h - self._CAR_ROW1_HEIGHT

        # Row 1: CAR INITIAL | CAR NUMBER
        row1_top = y + h
        row1_rule = row_split
        self._label(canvas, "CAR INITIAL", x, row1_top, top_width=2.0)
        self._label(canvas, "CAR NUMBER", mid, row1_top, top_width=2.0, left_width=0.4)

        half_w = w / 2 - 6
        row1_label_bottom = self._label_bottom(row1_top, top_width=2.0)
        row1_value_y = self._centered_value_baseline(row1_label_bottom, row1_rule)
        self._value_fit(canvas, car.road, x + 3, row1_value_y, half_w)
        self._value_fit(canvas, car.car_number, mid + 3, row1_value_y, half_w)

        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(mid, row_split, mid, y + h)

        # Rule between rows
        canvas.setLineWidth(0.5)
        canvas.line(x, row_split, x + w, row_split)

        # Row 2: AAR CLASS OF / CAR ORDERED | LENGTH/CAPY OF / CAR ORDERED --
        # label wraps to two lines on the left of each half-column, value
        # sits to its right (not below -- the row is too short for that),
        # vertically centered on the full row height like the reference.
        row2_top = row_split
        row2_rule = y
        aar_label = ("AAR CLASS OF", "CAR ORDERED")
        len_label = ("LENGTH/CAPY OF", "CAR ORDERED")
        self._label_2line(canvas, *aar_label, x, row2_top)
        self._label_2line(canvas, *len_label, mid, row2_top, left_width=0.4)

        length_cap = f"{car.length_ft}'" if car.length_ft else ""
        if length_cap:
            length_cap += f" {car.capacity_tons}T"
        else:
            length_cap = f"{car.capacity_tons}T"
        if car.capacity_cuft:
            length_cap += f" {car.capacity_cuft}CF"
        aar_display = car.aar_code.upper()

        row2_value_y = row2_rule + (row2_top - row2_rule) / 2 - self._value_cap_height(9) / 2
        aar_offset = self._label_2line_width(*aar_label) + 6
        len_offset = self._label_2line_width(*len_label) + 6
        self._value_fit(canvas, aar_display, x + aar_offset, row2_value_y, half_w - aar_offset + 6, max_size=9)
        self._value_fit(canvas, length_cap, mid + len_offset, row2_value_y, half_w - len_offset + 6, max_size=9)

        canvas.setLineWidth(0.4)
        canvas.line(mid, y, mid, row_split)

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

    _LABEL_SIZE: float = 6.0
    _LABEL_INSET: float = 2.0

    def _label_cap_height(self) -> float:
        """Height of the tallest glyph above the baseline, in points, at _LABEL_SIZE."""
        from reportlab.pdfbase import pdfmetrics
        face = pdfmetrics.getFont(self.label_font).face
        return face.bbox[3] / face.unitsPerEm * self._LABEL_SIZE

    def _label_bottom(self, box_top: float, top_width: float = 0.5) -> float:
        """Baseline y of a label drawn at box_top -- the visual bottom of its text."""
        return box_top - top_width / 2 - self._LABEL_INSET - self._label_cap_height()

    _LABEL_TRACKING: float = 0.0

    def _draw_tracked_string(
        self, canvas: Canvas, x: float, y: float, text: str, font: str, size: float,
        tracking: float = 0.0,
    ) -> None:
        """drawString with letter tracking -- Canvas has no setCharSpace of
        its own, only text objects do."""
        t = canvas.beginText(x, y)
        t.setFont(font, size)
        t.setFillColor(black)
        t.setCharSpace(tracking)
        t.textOut(text)
        canvas.drawText(t)

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
        self._draw_tracked_string(
            canvas,
            box_left + left_width / 2 + self._LABEL_INSET,
            self._label_bottom(box_top, top_width),
            text, self.label_font, self._LABEL_SIZE, self._LABEL_TRACKING,
        )

    _LABEL_LINE_GAP: float = 0.75
    _LABEL_2LINE_SIZE: float = 4.5

    def _label_2line(
        self, canvas: Canvas, line1: str, line2: str, box_left: float, box_top: float,
        top_width: float = 0.5, left_width: float = 0.0,
    ) -> None:
        """Draw a two-line field label, line1 above line2, both left-aligned
        the same as _label. Matches the reference form's wrapped column
        headers (e.g. "AAR CLASS OF" / "CAR ORDERED") -- set a size step
        smaller than a single-line label so both lines fit the shorter row."""
        text_x = box_left + left_width / 2 + self._LABEL_INSET
        top_y = box_top - top_width / 2 - self._LABEL_INSET
        from reportlab.pdfbase import pdfmetrics
        face = pdfmetrics.getFont(self.label_font).face
        cap_height = face.bbox[3] / face.unitsPerEm * self._LABEL_2LINE_SIZE
        line1_baseline = top_y - cap_height
        self._draw_tracked_string(
            canvas, text_x, line1_baseline, line1,
            self.label_font, self._LABEL_2LINE_SIZE, self._LABEL_TRACKING,
        )
        line2_baseline = line1_baseline - self._LABEL_2LINE_SIZE - self._LABEL_LINE_GAP
        self._draw_tracked_string(
            canvas, text_x, line2_baseline, line2,
            self.label_font, self._LABEL_2LINE_SIZE, self._LABEL_TRACKING,
        )

    def _label_2line_bottom(self, box_top: float, top_width: float = 0.5) -> float:
        """Visual bottom baseline of a two-line label block started at box_top."""
        from reportlab.pdfbase import pdfmetrics
        face = pdfmetrics.getFont(self.label_font).face
        cap_height = face.bbox[3] / face.unitsPerEm * self._LABEL_2LINE_SIZE
        line1_baseline = (box_top - top_width / 2 - self._LABEL_INSET) - cap_height
        return line1_baseline - self._LABEL_2LINE_SIZE - self._LABEL_LINE_GAP

    def _label_2line_width(self, line1: str, line2: str) -> float:
        """Widest of the two label lines (including letter tracking), for
        placing a value clear of the label."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        tracking1 = max(len(line1) - 1, 0) * self._LABEL_TRACKING
        tracking2 = max(len(line2) - 1, 0) * self._LABEL_TRACKING
        return max(
            stringWidth(line1, self.label_font, self._LABEL_2LINE_SIZE) + tracking1,
            stringWidth(line2, self.label_font, self._LABEL_2LINE_SIZE) + tracking2,
        )

    def _value_cap_height(self, size: float = 8) -> float:
        """Height of the tallest glyph above the baseline, in points, at the given size."""
        from reportlab.pdfbase import pdfmetrics
        face = pdfmetrics.getFont(self.value_font).face
        return face.bbox[3] / face.unitsPerEm * size

    def _value_upper(self, text: str) -> str:
        """Uppercase for the value font, substituting characters it lacks
        (Mom's Typewriter Actual has no em/en dash, only a plain hyphen)."""
        return text.upper().replace("—", "-").replace("–", "-")

    def _will_wrap(self, text: str, max_width: float, size: float = 8) -> bool:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        return stringWidth(self._value_upper(text), self.value_font, size) > max_width

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
        canvas.drawString(x, y, self._value_upper(text))

    def _value_fit(
        self, canvas: Canvas, text: str, x: float, y: float, max_width: float, max_size: int = 8
    ) -> None:
        """Draw value font text at max_size, truncating with ellipsis if too wide."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        text = self._value_upper(text)
        if stringWidth(text, self.value_font, max_size) <= max_width:
            canvas.setFont(self.value_font, max_size)
            canvas.setFillColor(black)
            canvas.drawString(x, y, text)
            return
        truncated = text
        while truncated and stringWidth(truncated + _ELLIPSIS, self.value_font, max_size) > max_width:
            truncated = truncated[:-1]
        canvas.setFont(self.value_font, max_size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, truncated + (_ELLIPSIS if truncated != text else ""))

    def _value_wrap(
        self, canvas: Canvas, text: str, x: float, y: float, max_width: float,
        size: int = 8, line_gap: int = 2,
    ) -> None:
        """Wrap to a second line at the nearest word boundary; truncate line 2 with ellipsis if needed."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        text = self._value_upper(text)
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
            while line2 and stringWidth(line2 + _ELLIPSIS, self.value_font, size) > max_width:
                line2 = line2[:-1]
            canvas.drawString(x, y - size - line_gap, line2 + (_ELLIPSIS if " ".join(words[split_at:]) != line2 else ""))

    def _value_wrap_n(
        self, canvas: Canvas, text: str, x: float, y_top: float, max_width: float,
        max_lines: int, size: int = 8, line_gap: int = 2,
    ) -> None:
        """Word-wrap top-anchored (y_top is line 1's baseline) up to max_lines;
        truncate the final line with an ellipsis if content remains."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        text = self._value_upper(text)
        canvas.setFillColor(black)
        canvas.setFont(self.value_font, size)
        words = text.split()
        if not words:
            return
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if stringWidth(candidate, self.value_font, size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    break
        if current and len(lines) < max_lines:
            lines.append(current)
        if " ".join(lines) != text and lines:
            last = lines[-1]
            while last and stringWidth(last + _ELLIPSIS, self.value_font, size) > max_width:
                last = last[:-1]
            lines[-1] = last + _ELLIPSIS
        for i, line in enumerate(lines):
            canvas.drawString(x, y_top - i * (size + line_gap), line)

    def _value_wrap_hyphenated(
        self, canvas: Canvas, segments: list[str], x: float, y_top: float, max_width: float,
        max_lines: int, size: int = 8, line_gap: int = 2,
    ) -> None:
        """Top-anchored wrap for routing junctions, joined with '-' and broken
        at hyphens rather than spaces -- matches the reference form's
        "FP&E-NYC-STL-" / "SSW-COR-T&NO-" / "ELP-SP" style line breaks."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        canvas.setFillColor(black)
        canvas.setFont(self.value_font, size)
        tokens = [self._value_upper(s) + "-" for s in segments]
        if tokens:
            tokens[-1] = tokens[-1][:-1]
        lines: list[str] = []
        current = ""
        for tok in tokens:
            candidate = current + tok
            if not current or stringWidth(candidate, self.value_font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = tok
                if len(lines) >= max_lines:
                    current = ""
                    break
        if current and len(lines) < max_lines:
            lines.append(current)
        for i, line in enumerate(lines):
            canvas.drawString(x, y_top - i * (size + line_gap), line)

    def _section_header(self, canvas: Canvas, text: str, x: float, y: float, w: float) -> None:
        """Bold centered section header, no surrounding rules."""
        canvas.setFont(self.headline_font, 9)
        canvas.setFillColor(black)
        canvas.drawCentredString(x + w / 2, y + 3, text)

    # -- Waybill type renderers -----------------------------------------------

    # Row heights below are proportioned from the reference scan's own waybill
    # -section rows (measured as fractions of its total waybill-section height,
    # then applied to our fixed waybill zone) -- NOT the car-card block above,
    # whose size is standardized across layouts and untouched here.
    # TO/FROM STATION and CONSIGNEE/SHIPPER are kept equal height (averaging
    # the reference's own 22pt/40pt split) rather than following the
    # reference's asymmetry, per request.
    _ROW_TO_FROM: float = 31.0
    _ROW_CONSIGNEE_SHIPPER: float = 31.0
    _ROW_ROUTE_STOP: float = 38.0
    _ROW_CL_INSTRUCTIONS: float = 26.0

    def _draw_loaded(
        self, canvas: Canvas, w: LoadedWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        mid = x + ww / 2
        cursor = y + h
        col_w = mid - (x + 4)

        # TO STATION, STATE | FROM STATION, STATE (2-line capable, same as
        # CONSIGNEE/SHIPPER now that the rows are the same height)
        to_val = f"{w.to_city}, {w.to_state}" if w.to_city and w.to_state else (w.to_city or w.consignee_id)
        from_val = f"{w.from_city}, {w.from_state}" if w.from_city and w.from_state else (w.from_city or w.shipper_id)
        label_top = cursor
        rule_y = label_top - self._ROW_TO_FROM
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
        rule_y = label_top - self._ROW_CONSIGNEE_SHIPPER
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

        # ROUTE (up to 3 lines, hyphen-wrapped like the reference) |
        # weight-instructions boilerplate + STOP THIS CAR AT
        label_top = cursor
        rule_y = label_top - self._ROW_ROUTE_STOP
        self._label(canvas, "ROUTE Show in route order", x, label_top)
        label_bottom = self._label_bottom(label_top)
        if w.routing:
            self._value_wrap_hyphenated(
                canvas, w.routing, x + 2, label_bottom - 8, col_w, max_lines=3, size=8, line_gap=2,
            )

        instr_top = label_top - 1
        instr_size = 3.6
        for i, line in enumerate([
            "Indicate how weights were obtained",
            "for L.C.L. Shipments only.",
            "E-Estimated       S-Shipper's Tested Weights",
            "R-Railroad Scale   T-Tariff Classification",
        ]):
            self._draw_tracked_string(
                canvas, mid + 2, instr_top - (i + 1) * (instr_size + 1.2),
                line, self.label_font, instr_size,
            )
        stop_rule_y = instr_top - 4 * (instr_size + 1.2) - 2
        self._rule(canvas, mid, stop_rule_y, ww / 2, width=0.4)
        self._label_2line(canvas, "STOP THIS CAR", "AT", mid, stop_rule_y, top_width=0.4)
        if w.stop_at:
            # Same baseline as "AT" (line 2 of the label), to its right.
            stop_label_bottom = self._label_2line_bottom(stop_rule_y, top_width=0.4)
            at_width = self._label_2line_width("AT", "AT") + 4
            self._value_fit(
                canvas, w.stop_at, mid + self._LABEL_INSET + at_width, stop_label_bottom,
                ww / 2 - at_width - self._LABEL_INSET - 4, max_size=7,
            )

        self._vcol(canvas, mid, rule_y, label_top - rule_y)
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        # ON C.L. TRAFFIC-INSTRUCTIONS (Regarding Icing, Ventilation, Etc.) &
        # EXCEPTIONS -- fixed 3-line break exactly as printed on the reference,
        # at the smaller 2-line label size (the reference sets this notably
        # smaller than the other row labels to fit three lines).
        label_top = cursor
        rule_y = label_top - self._ROW_CL_INSTRUCTIONS
        cl_size = self._LABEL_2LINE_SIZE
        cl_line_gap = 0.75
        cl_lines = ["ON C.L. TRAFFIC-INSTRUCTIONS", "(Regarding Icing, Ventilation, Etc.)", "& EXCEPTIONS"]
        from reportlab.pdfbase import pdfmetrics
        cl_cap_height = pdfmetrics.getFont(self.label_font).face.bbox[3] / pdfmetrics.getFont(self.label_font).face.unitsPerEm * cl_size
        cl_top = label_top - self._LABEL_INSET - cl_cap_height
        for i, line in enumerate(cl_lines):
            self._draw_tracked_string(
                canvas, x + self._LABEL_INSET, cl_top - i * (cl_size + cl_line_gap),
                line, self.label_font, cl_size, self._LABEL_TRACKING,
            )
        if w.notes:
            notes_y = cl_top - len(cl_lines) * (cl_size + cl_line_gap) - 2
            if notes_y > rule_y + 2:
                self._value_fit(canvas, w.notes, x + 2, notes_y, ww - 4, max_size=7)

        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        # NO. PKGS. | DESCRIPTION OF ARTICLES column headers, commodity below
        pkgs_col = x + 32
        self._label(canvas, "NO. PKGS.", x, cursor)
        self._label(canvas, "DESCRIPTION OF ARTICLES", pkgs_col, cursor)
        cursor -= 10
        self._rule(canvas, x, cursor, ww)

        self._value_fit(canvas, w.commodity_id, pkgs_col + 3, cursor - 15, x + ww - pkgs_col - 5, max_size=10)

    def _draw_empty(
        self, canvas: Canvas, w: EmptyWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        # Matched against Southern Pacific's "Empty Car Bill" (Form 151):
        # FOR HOME (Billed from / To or Via + R.R.) then FOR LOADING (Billed
        # from / To), no Shipper/Spot row on the reference form, and the
        # exact instructions text -- reproduced verbatim below.
        cursor = y + h
        mid = x + ww / 2

        # ── FOR HOME ──────────────────────────────────────────────────────
        cursor -= 19
        self._section_header(canvas, "FOR HOME", x, cursor, ww)
        cursor -= 3

        label_top = cursor
        rule_y = label_top - 19
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
        rule_y = label_top - 19
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
        cursor = rule_y - 10

        # ── FOR LOADING ───────────────────────────────────────────────────
        cursor -= 12
        self._section_header(canvas, "FOR LOADING", x, cursor, ww)
        cursor -= 3

        label_top = cursor
        rule_y = label_top - 19
        self._label(canvas, "Billed from", x, label_top, top_width=0)
        label_bottom = self._label_bottom(label_top, top_width=0)
        self._value_fit(
            canvas, w.from_location_id, x + 30,
            self._centered_value_baseline(label_bottom, rule_y), ww - 32,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        label_top = cursor
        rule_y = label_top - 19
        self._label(canvas, "To", x, label_top)
        label_bottom = self._label_bottom(label_top)
        self._value_fit(
            canvas, w.to_location_id, x + 10,
            self._centered_value_baseline(label_bottom, rule_y), ww - 12,
        )
        self._rule(canvas, x, rule_y, ww)
        cursor = rule_y

        # Shipper/Spot -- not on the reference form, so only drawn (as a
        # compact extra row) when the data is actually present.
        if w.shipper_ordered_by or w.spot:
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
            cursor = rule_y

        # Instructions -- verbatim from the SP Form 151 reference.
        instr_size = 4.5
        for i, line in enumerate([
            "INSTRUCTIONS – This form must accompany all",
            "empty foreign cars and must be used in billing",
            "private line cars under General Order Ten.",
        ]):
            self._draw_tracked_string(
                canvas, x + 2, cursor - 8 - i * (instr_size + 2.5),
                line, self.label_font, instr_size,
            )

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
        """MOW loads get no distinct prototype form -- Tony Thompson's own
        examples (e.g. an SP ballast move to an outfit track) are filled out
        on the plain Freight Waybill, just like a LOADED shipment. Adapt the
        MOW fields onto a LoadedWaybill and reuse that renderer."""
        loaded_view = LoadedWaybill(
            id=w.id,
            originating_railroad_id=w.originating_railroad_id,
            notes=w.project,
            commodity_id=w.commodity_desc,
            shipper_id="",
            consignee_id="",
            to_city=w.to_location_id,
            consignee_name="TRACK FOREMAN, OUTFIT TRACK",
            from_city=w.from_location_id,
        )
        self._draw_loaded(canvas, loaded_view, x, y, ww, h)

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

    # Matched against the real SP "Bad Order" card (Form L-7017-A): a big
    # diagonal red stripe with "BAD ORDER" across it, dominating the card,
    # with REMOVED FROM TRAIN/DATE, TO/SHOP, DEFECT, CAR INITIALS/LOADED OR
    # EMPTY, and PLACE CARDED/INSPECTOR fields above and below.
    _STRIPE_COLOR = HexColor("#B7261E")
    _STRIPE_ANGLE = 9.0
    _STRIPE_HALF_HEIGHT = 15.0

    def _draw_bad_order(
        self, canvas: Canvas, w: BadOrderWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        mid = x + ww / 2
        cursor = y + h

        # REMOVED FROM TRAIN | DATE
        self._label(canvas, "REMOVED FROM TRAIN", x, cursor, top_width=2.0)
        self._label(canvas, "DATE", mid, cursor, top_width=2.0, left_width=0.4)
        cursor -= 13
        self._vcol(canvas, mid, cursor, 13)
        self._rule(canvas, x, cursor, ww)

        # TO | SHOP
        label_top = cursor
        self._label(canvas, "TO", x, label_top)
        self._label(canvas, "SHOP", mid, label_top, left_width=0.4)
        if w.shop_location_id:
            label_bottom = self._label_bottom(label_top)
            self._value_fit(canvas, w.shop_location_id, mid + 2, label_bottom - 9, ww / 2 - 4)
        cursor -= 20
        self._vcol(canvas, mid, cursor, 20)
        self._rule(canvas, x, cursor, ww)

        # Diagonal "BAD ORDER" stripe -- clipped to the card's own width so
        # the stripe never bleeds into neighboring cards on the printed page.
        from reportlab.pdfbase.pdfmetrics import stringWidth
        stripe_h = 48.0
        stripe_cy = cursor - stripe_h / 2
        canvas.saveState()
        clip = canvas.beginPath()
        clip.rect(x, y, ww, h)
        canvas.clipPath(clip, stroke=0, fill=0)
        canvas.translate(x + ww / 2, stripe_cy)
        canvas.rotate(self._STRIPE_ANGLE)
        span = ww * 1.5
        canvas.setFillColor(self._STRIPE_COLOR)
        canvas.rect(-span / 2, -self._STRIPE_HALF_HEIGHT, span, self._STRIPE_HALF_HEIGHT * 2, fill=1, stroke=0)
        canvas.setFillColor(black)
        stripe_size = 20.0
        while stripe_size > 8 and stringWidth("BAD ORDER", self.stripe_font, stripe_size) > ww - 6:
            stripe_size -= 1
        canvas.setFont(self.stripe_font, stripe_size)
        canvas.drawCentredString(0, -stripe_size * 0.32, "BAD ORDER")
        canvas.restoreState()
        cursor -= stripe_h

        # DEFECT
        label_top = cursor
        self._label(canvas, "DEFECT", x, label_top)
        cursor -= 11
        if w.defect:
            self._value_wrap(canvas, w.defect, x + 2, cursor - 8, ww - 4, size=7, line_gap=2)
        cursor -= 16
        self._rule(canvas, x, cursor, ww)

        # CAR INITIALS | LOADED OR EMPTY
        self._label(canvas, "CAR INITIALS", x, cursor)
        self._label(canvas, "LOADED OR EMPTY", mid, cursor, left_width=0.4)
        cursor -= 13
        self._vcol(canvas, mid, cursor, 13)
        self._rule(canvas, x, cursor, ww)

        # PLACE CARDED | INSPECTOR
        label_top = cursor
        self._label(canvas, "PLACE CARDED", x, label_top)
        self._label(canvas, "INSPECTOR", mid, label_top, left_width=0.4)
        if w.from_location_id:
            label_bottom = self._label_bottom(label_top)
            self._value_fit(canvas, w.from_location_id, x + 2, label_bottom - 9, mid - x - 4)
        cursor -= 20
        self._vcol(canvas, mid, cursor, 20)
        self._rule(canvas, x, cursor, ww)
