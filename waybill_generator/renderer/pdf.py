from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import WaybillBase

_COLS = 3
_ROWS = 3
_PER_PAGE = _COLS * _ROWS
_PAGE_W, _PAGE_H = letter  # 612, 792


def render_pdf(
    pairs: list[tuple[Car, WaybillBase]],
    layout: BaseLayout,
    output_path: str | Path,
) -> None:
    canvas = Canvas(str(output_path), pagesize=letter)

    if not pairs:
        canvas.save()
        return

    g = layout.gutter_pt
    cw = layout.card_width_pt
    ch = layout.card_height_pt

    left_margin = (_PAGE_W - (_COLS * cw + (_COLS + 1) * g)) / 2
    bottom_margin = (_PAGE_H - (_ROWS * ch + (_ROWS + 1) * g)) / 2

    for page_idx, page_pairs in enumerate(_chunks(pairs, _PER_PAGE)):
        if page_idx > 0:
            canvas.showPage()

        for card_idx, (car, waybill) in enumerate(page_pairs):
            col = card_idx % _COLS
            row = card_idx // _COLS

            x = left_margin + g + col * (cw + g)
            y = _PAGE_H - bottom_margin - g - (row + 1) * ch - row * g

            layout.draw_card(canvas, car, waybill, x, y)
            _draw_crop_marks(canvas, x, y, cw, ch, g)

    canvas.save()


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _draw_crop_marks(
    canvas: Canvas, x: float, y: float, w: float, h: float, gutter: float
) -> None:
    mark = min(gutter * 0.5, 4.5)
    canvas.setStrokeColorRGB(0.6, 0.6, 0.6)
    canvas.setLineWidth(0.25)

    # Bottom-left
    canvas.line(x - mark, y, x, y)
    canvas.line(x, y - mark, x, y)
    # Bottom-right
    canvas.line(x + w, y, x + w + mark, y)
    canvas.line(x + w, y - mark, x + w, y)
    # Top-left
    canvas.line(x - mark, y + h, x, y + h)
    canvas.line(x, y + h, x, y + h + mark)
    # Top-right
    canvas.line(x + w, y + h, x + w + mark, y + h)
    canvas.line(x + w, y + h, x + w, y + h + mark)
