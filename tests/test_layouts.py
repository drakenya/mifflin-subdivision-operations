import io
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.standard_prr import StandardPrrLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import (
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

CAR = Car(
    id="PRR-12345", road="PRR", car_number="12345",
    car_type="X29", aar_code="XM", capacity_tons=50,
)

WAYBILLS = [
    LoadedWaybill(id="w-1", commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP"),
    EmptyWaybill(id="e-1", from_location_id="ALT", to_location_id="LEW"),
    DeadheadWaybill(id="d-1", from_location_id="PHL", to_location_id="PGH"),
    MoWWaybill(id="m-1", commodity_desc="Ballast", from_location_id="ALT", to_location_id="LEW"),
    HoldWaybill(id="h-1", industry_id="LEW-GRAIN", waiting_for="Load order"),
    BadOrderWaybill(id="b-1", from_location_id="LEW", shop_location_id="ALT"),
]


def _make_canvas():
    buf = io.BytesIO()
    return Canvas(buf, pagesize=letter)


def test_layout_constants():
    layout = StandardPrrLayout()
    assert layout.card_width_pt == 180.0
    assert layout.card_height_pt == 252.0
    assert layout.gutter_pt == 9.0
    assert layout.content_inset_pt == 4.0


def test_draw_card_all_waybill_types():
    layout = StandardPrrLayout()
    for waybill in WAYBILLS:
        buf = io.BytesIO()
        canvas = Canvas(buf, pagesize=letter)
        layout.draw_card(canvas, CAR, waybill, x=0, y=0)
        canvas.save()
        content = buf.getvalue()
        assert b"%PDF" in content
        assert len(content) > 500, f"Card for {waybill.waybill_type} produced suspiciously small PDF"
