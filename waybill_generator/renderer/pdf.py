from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import WaybillBase

_COLS = 3
_ROWS = 3
_PER_PAGE = _COLS * _ROWS
_PAGE_W, _PAGE_H = letter   # 612, 792 pt
_LEFT_MARGIN = 36.0          # 0.5 in — outer left/right margin; cut line is at this edge
_TOP_MARGIN = 18.0           # 0.25 in — outer top/bottom margin; cut line is at this edge


def render_pdf(
    triples: list[tuple[Car, WaybillBase, Railroad]],
    layout: BaseLayout,
    output_path: str | Path,
) -> None:
    canvas = Canvas(str(output_path), pagesize=letter)

    if not triples:
        canvas.save()
        return

    cw = layout.card_width_pt
    ch = layout.card_height_pt

    for page_idx, page_triples in enumerate(_chunks(triples, _PER_PAGE)):
        if page_idx > 0:
            canvas.showPage()

        for card_idx, (car, waybill, railroad) in enumerate(page_triples):
            col = card_idx % _COLS
            row = card_idx // _COLS

            x = _LEFT_MARGIN + col * cw
            y = _PAGE_H - _TOP_MARGIN - (row + 1) * ch

            layout.draw_card(canvas, car, waybill, railroad, x, y)

        _draw_page_crop_marks(canvas, _COLS, _ROWS, cw, ch)

    canvas.save()


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _draw_page_crop_marks(
    canvas: Canvas,
    cols: int,
    rows: int,
    cw: float,
    ch: float,
) -> None:
    """Draw cut lines in the outer margins only.

    Vertical lines run from the paper edge into the top/bottom margins at each
    column boundary.  Horizontal lines run from the paper edge into the
    left/right margins at each row boundary.  Nothing is drawn over the card
    area, so cut guides never obscure card content.
    """
    canvas.setStrokeColorRGB(0.6, 0.6, 0.6)
    canvas.setLineWidth(0.25)

    # x positions of vertical cuts (column boundaries)
    x_cuts = [_LEFT_MARGIN + col * cw for col in range(cols + 1)]

    # y positions of horizontal cuts (row boundaries), ReportLab y-up
    y_cuts = [_PAGE_H - _TOP_MARGIN - row * ch for row in range(rows + 1)]

    right_x = _LEFT_MARGIN + cols * cw   # left edge of right margin
    top_y = _PAGE_H - _TOP_MARGIN         # bottom edge of top margin

    # Left margin: horizontal lines at each row boundary
    for yc in y_cuts:
        canvas.line(0, yc, _LEFT_MARGIN, yc)

    # Right margin: horizontal lines at each row boundary
    for yc in y_cuts:
        canvas.line(right_x, yc, _PAGE_W, yc)

    # Bottom margin: vertical lines at each column boundary
    for xc in x_cuts:
        canvas.line(xc, 0, xc, _TOP_MARGIN)

    # Top margin: vertical lines at each column boundary
    for xc in x_cuts:
        canvas.line(xc, top_y, xc, _PAGE_H)
