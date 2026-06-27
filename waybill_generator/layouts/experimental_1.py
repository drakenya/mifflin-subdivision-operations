from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import black
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import (
    WaybillBase, WaybillType,
    LoadedWaybill, EmptyWaybill,
)

_BILL_TYPE_LABELS = {
    WaybillType.LOADED: "FREIGHT WAYBILL",
    WaybillType.EMPTY: "SLIP BILL FOR EMPTY CAR",
    WaybillType.DEADHEAD: "DEADHEAD ORDER",
    WaybillType.MOW: "M-O-W SERVICE BILL",
    WaybillType.HOLD: "HOLD ORDER",
    WaybillType.BAD_ORDER: "BAD ORDER CARD",
}


class Experimental1Layout(BaseLayout):

    # -- Private drawing helpers ----------------------------------------------

    def _label(self, canvas: Canvas, text: str, x: float, y: float) -> None:
        canvas.setFont("Helvetica-Bold", 3.8)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _value(
        self, canvas: Canvas, text: str, x: float, y: float, size: int = 9
    ) -> None:
        canvas.setFont("Courier-Bold", size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _value_wrap(
        self,
        canvas: Canvas,
        text: str,
        x: float,
        y: float,
        max_w: float,
        size: int,
        max_lines: int = 1,
        line_gap: int = 2,
    ) -> None:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        canvas.setFont("Courier-Bold", size)
        canvas.setFillColor(black)
        words = text.split()
        if not words:
            return
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if stringWidth(candidate, "Courier-Bold", size) <= max_w:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    break
        if current and len(lines) < max_lines:
            lines.append(current)
        consumed = " ".join(lines)
        for j, line in enumerate(lines):
            if (stringWidth(line, "Courier-Bold", size) > max_w
                    or (j == len(lines) - 1 and consumed != text.strip())):
                while line and stringWidth(line + "…", "Courier-Bold", size) > max_w:
                    line = line[:-1]
                lines[j] = (line + "…") if line else "…"
        for i, line in enumerate(lines):
            canvas.drawString(x, y - i * (size + line_gap), line)

    def _value_truncate(
        self, canvas: Canvas, text: str, x: float, y: float, max_w: float, size: int
    ) -> None:
        self._value_wrap(canvas, text, x, y, max_w=max_w, size=size, max_lines=1)

    def _hrule(self, canvas: Canvas, x: float, y: float, w: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)

    def _vcol(self, canvas: Canvas, x: float, y: float, h: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(x, y, x, y + h)

    def _section_header(
        self, canvas: Canvas, text: str, x: float, y: float, w: float
    ) -> None:
        """Centered section header (Helvetica-Bold 9pt) with double rules."""
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(black)
        canvas.drawCentredString(x + w / 2, y + 3, text)
        self._hrule(canvas, x, y + 14, w)
        self._hrule(canvas, x, y + 1, w)

    def _draw_generic_rows(
        self,
        canvas: Canvas,
        rows: list[tuple[str, str | None]],
        x: float, y: float, w: float, h: float,
    ) -> None:
        """Stack (label, value) pairs as 30pt rows with horizontal rules; skip None values."""
        cursor = y + h
        for label, value in rows:
            if value is None:
                continue
            if cursor - 30 < y:
                break
            cursor -= 30
            self._label(canvas, label, x + 2, cursor + 22)
            self._value_wrap(canvas, value, x + 2, cursor + 13, max_w=w - 4, size=9, max_lines=2)
            self._hrule(canvas, x, cursor, w)

    # -- Origination band -----------------------------------------------------

    def draw_origination_section(
        self,
        canvas: Canvas,
        railroad: Railroad,
        waybill: WaybillBase,
        x: float, y: float, w: float, h: float,
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)  # bottom separator rule

        canvas.setFillColor(black)

        # Form number top-left, waybill id top-right
        canvas.setFont("Helvetica", 5)
        canvas.drawString(x, y + h - 6, railroad.form_number)
        # Railroad name centered
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawCentredString(x + w / 2, y + h / 2 + 2, railroad.name.upper())

        # Bill type label centered below railroad name
        canvas.setFont("Helvetica", 6)
        canvas.drawCentredString(
            x + w / 2, y + 4, _BILL_TYPE_LABELS[waybill.waybill_type]
        )

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        mid = x + w / 2
        row_h = h / 2  # 25pt per row

        # Top row: CAR INITIALS & NUMBER (left) | KIND (right)
        self._label(canvas, "CAR INITIALS & NUMBER", x + 2, y + h - 8)
        self._label(canvas, "KIND", mid + 2, y + h - 8)
        self._value(canvas, f"{car.road} {car.car_number}", x + 2, y + h - 20, size=9)
        self._value(canvas, car.aar_code, mid + 2, y + h - 20, size=8)
        self._vcol(canvas, mid, y + row_h, row_h)
        self._hrule(canvas, x, y + row_h, w)

        # Bottom row: DATE (left, blank) | WAYBILL NO. (right, blank)
        self._label(canvas, "DATE", x + 2, y + row_h - 8)
        self._label(canvas, "WAYBILL NO.", mid + 2, y + row_h - 8)
        self._vcol(canvas, mid, y, row_h)
        self._hrule(canvas, x, y, w)

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        match waybill.waybill_type:
            case WaybillType.LOADED:
                self._draw_loaded(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.EMPTY:
                self._draw_empty(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.DEADHEAD:
                self._draw_generic_rows(canvas, [
                    ("FROM", waybill.from_location_id),  # type: ignore[attr-defined]
                    ("TO", waybill.to_location_id),  # type: ignore[attr-defined]
                    ("CONSIST", waybill.consist_note),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case WaybillType.MOW:
                self._draw_generic_rows(canvas, [
                    ("MATERIAL", waybill.commodity_desc),  # type: ignore[attr-defined]
                    ("FROM", waybill.from_location_id),  # type: ignore[attr-defined]
                    ("TO", waybill.to_location_id),  # type: ignore[attr-defined]
                    ("PROJECT", waybill.project),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case WaybillType.HOLD:
                self._draw_generic_rows(canvas, [
                    ("HOLD AT", waybill.industry_id),  # type: ignore[attr-defined]
                    ("WAITING FOR", waybill.waiting_for),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case WaybillType.BAD_ORDER:
                self._draw_generic_rows(canvas, [
                    ("FROM", waybill.from_location_id),  # type: ignore[attr-defined]
                    ("REPAIR SHOP", waybill.shop_location_id),  # type: ignore[attr-defined]
                    ("DEFECT", waybill.defect),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case _:
                raise ValueError(f"Unhandled waybill type: {waybill.waybill_type}")

    def _draw_loaded(
        self, canvas: Canvas, waybill: LoadedWaybill,
        x: float, y: float, w: float, h: float,
    ) -> None:
        cursor = y + h
        mid = x + w / 2
        col_w = mid - x - 4  # usable column width ≈ 81.5pt

        # TO STATION, STATE | FROM STATION, STATE (35pt, size=10, 2 lines)
        cursor -= 35
        self._label(canvas, "TO STATION, STATE", x + 2, cursor + 28)
        self._label(canvas, "FROM STATION, STATE", mid + 2, cursor + 28)
        to_val = f"{waybill.to_city}, {waybill.to_state}" if waybill.to_city else ""
        from_val = f"{waybill.from_city}, {waybill.from_state}" if waybill.from_city else ""
        self._value_wrap(canvas, to_val, x + 2, cursor + 17, max_w=col_w, size=10, max_lines=2)
        self._value_wrap(canvas, from_val, mid + 2, cursor + 17, max_w=col_w, size=10, max_lines=2)
        self._vcol(canvas, mid, cursor, 35)
        self._hrule(canvas, x, cursor, w)

        # CONSIGNEE | SHIPPER (28pt, size=7, 2 lines)
        cursor -= 28
        self._label(canvas, "CONSIGNEE", x + 2, cursor + 21)
        self._label(canvas, "SHIPPER", mid + 2, cursor + 21)
        self._value_wrap(canvas, waybill.consignee_name or "", x + 2, cursor + 12,
                         max_w=col_w, size=7, max_lines=2)
        self._value_wrap(canvas, waybill.shipper_name or "", mid + 2, cursor + 12,
                         max_w=col_w, size=7, max_lines=2)
        self._vcol(canvas, mid, cursor, 28)
        self._hrule(canvas, x, cursor, w)

        # ROUTE (20pt, size=7, single line — row too tight for a second)
        cursor -= 20
        self._label(canvas, "ROUTE — SHOW IN ROUTE ORDER", x + 2, cursor + 13)
        if waybill.routing:
            self._value_truncate(canvas, " - ".join(waybill.routing), x + 2, cursor + 4,
                                 max_w=w - 4, size=7)
        self._hrule(canvas, x, cursor, w)

        # DESCRIPTION OF ARTICLES header (10pt)
        cursor -= 10
        self._label(canvas, "DESCRIPTION OF ARTICLES", x + 2, cursor + 4)
        self._hrule(canvas, x, cursor, w)

        # Commodity — centered in remaining space (~69.5pt)
        remaining_h = cursor - y
        canvas.setFont("Courier-Bold", 12)
        canvas.setFillColor(black)
        canvas.drawCentredString(
            x + w / 2, y + remaining_h / 2 - 2, waybill.commodity_id.upper()
        )

    def _draw_empty(
        self, canvas: Canvas, waybill: EmptyWaybill,
        x: float, y: float, w: float, h: float,
    ) -> None:
        cursor = y + h
        mid = x + w / 2

        # FOR HOME section header (20pt)
        cursor -= 20
        self._section_header(canvas, "FOR HOME", x, cursor, w)

        # Billed from (10pt, single line)
        cursor -= 10
        self._label(canvas, "Billed from", x + 2, cursor + 4)
        if waybill.home_billed_from:
            self._value_truncate(canvas, waybill.home_billed_from, x + 38, cursor + 4,
                                 max_w=w - 40, size=7)
        self._hrule(canvas, x, cursor, w)

        # To or Via / R.R. (10pt, single line each)
        cursor -= 10
        col_rr = x + w * 3 / 4
        self._label(canvas, "To or Via", x + 2, cursor + 4)
        self._label(canvas, "R.R.", col_rr + 2, cursor + 4)
        if waybill.home_to_or_via:
            self._value_truncate(canvas, waybill.home_to_or_via, x + 30, cursor + 4,
                                 max_w=col_rr - x - 32, size=7)
        if waybill.home_rr:
            self._value_truncate(canvas, waybill.home_rr, col_rr + 10, cursor + 4,
                                 max_w=w - w * 3 / 4 - 12, size=7)
            self._vcol(canvas, col_rr, cursor, 10)
        self._hrule(canvas, x, cursor, w)

        # FOR LOADING section header (20pt)
        cursor -= 20
        self._section_header(canvas, "FOR LOADING", x, cursor, w)

        # Billed from (10pt, single line)
        cursor -= 10
        self._label(canvas, "Billed from", x + 2, cursor + 4)
        self._value_truncate(canvas, waybill.from_location_id, x + 38, cursor + 4,
                             max_w=w - 40, size=7)
        self._hrule(canvas, x, cursor, w)

        # To (10pt, single line)
        cursor -= 10
        self._label(canvas, "To", x + 2, cursor + 4)
        self._value_truncate(canvas, waybill.to_location_id, x + 12, cursor + 4,
                             max_w=w - 14, size=7)
        self._hrule(canvas, x, cursor, w)

        # Shipper / Spot (remaining ≈ 82.5pt, up to 3 lines each)
        self._label(canvas, "Shipper", x + 2, cursor - 6)
        self._label(canvas, "Spot", mid + 2, cursor - 6)
        if waybill.shipper_ordered_by:
            self._value_wrap(canvas, waybill.shipper_ordered_by, x + 2, cursor - 15,
                             max_w=w / 2 - 4, size=7, max_lines=3)
        if waybill.spot:
            self._value_wrap(canvas, waybill.spot, mid + 2, cursor - 15,
                             max_w=w / 2 - 4, size=7, max_lines=3)
        self._vcol(canvas, mid, y, cursor - y)
