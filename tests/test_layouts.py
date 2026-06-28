import io
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.modelling_the_sp import ModellingTheSpLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import (
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

CAR = Car(id="PRR-12345", road="PRR", car_number="12345", aar_code="XM", capacity_tons=50)

RR = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")

WAYBILLS = [
    LoadedWaybill(id="w-1", originating_railroad_id="PRR",
                  commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP"),
    EmptyWaybill(id="e-1", originating_railroad_id="PRR",
                 from_location_id="ALT", to_location_id="LEW"),
    DeadheadWaybill(id="d-1", originating_railroad_id="PRR",
                    from_location_id="PHL", to_location_id="PGH"),
    MoWWaybill(id="m-1", originating_railroad_id="PRR",
               commodity_desc="Ballast", from_location_id="ALT", to_location_id="LEW"),
    HoldWaybill(id="h-1", originating_railroad_id="PRR",
                industry_id="LEW-GRAIN", waiting_for="Load order"),
    BadOrderWaybill(id="b-1", originating_railroad_id="PRR",
                    from_location_id="LEW", shop_location_id="ALT"),
]


def test_value_wrap_short_text_draws_once():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    layout._value_wrap(canvas, "short", x=0, y=100, max_w=200, size=9)
    assert canvas.drawString.call_count == 1
    assert canvas.drawString.call_args_list[0].args[1] == 100  # y unchanged


def test_value_wrap_long_text_wraps_to_two_lines():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    # Courier-Bold 9pt: each char ≈ 5.4pt. "hello"=27pt fits in 30, "hello world"=59.4pt does not.
    layout._value_wrap(canvas, "hello world", x=0, y=100, max_w=30, size=9, max_lines=2)
    assert canvas.drawString.call_count == 2
    assert canvas.drawString.call_args_list[0].args[1] == 100       # line 1 at y
    assert canvas.drawString.call_args_list[1].args[1] == 100 - (9 + 2)  # line 2 at y - (size+gap)


def test_value_wrap_overflow_truncates_with_ellipsis():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    # max_lines=1, "hello world" can't fit in 30pt on one line → truncate with "…"
    layout._value_wrap(canvas, "hello world", x=0, y=100, max_w=30, size=9, max_lines=1)
    assert canvas.drawString.call_count == 1
    drawn = canvas.drawString.call_args_list[0].args[2]
    assert drawn.endswith("…"), f"Expected truncation with '…', got: {drawn!r}"


def test_value_wrap_single_oversized_word_truncates():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    # "superlongword" is 13 chars × 5.4pt ≈ 70pt in Courier-Bold 9pt; max_w=30 forces truncation
    layout._value_wrap(canvas, "superlongword", x=0, y=100, max_w=30, size=9, max_lines=1)
    assert canvas.drawString.call_count == 1
    drawn = canvas.drawString.call_args_list[0].args[2]
    assert drawn.endswith("…"), f"Expected truncation with '…', got: {drawn!r}"


def test_experimental1_layout_is_registered():
    from waybill_generator.cli import _LAYOUTS
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    assert "experimental_1" in _LAYOUTS
    assert _LAYOUTS["experimental_1"] is Experimental1Layout


def test_experimental1_layout_instantiates():
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    assert layout.card_width_pt == 180.0
    assert layout.card_height_pt == 252.0
    assert layout.origination_height_pt == 35.0
    assert layout.car_height_pt == 50.0


def test_layout_constants():
    layout = ModellingTheSpLayout()
    assert layout.card_width_pt == 180.0
    assert layout.card_height_pt == 252.0
    assert layout.origination_height_pt == 35.0
    assert layout.car_height_pt == 50.0
    assert layout.gutter_pt == 0.0
    assert layout.content_inset_pt == 4.5


def test_draw_card_all_waybill_types():
    layout = ModellingTheSpLayout()
    for waybill in WAYBILLS:
        buf = io.BytesIO()
        canvas = Canvas(buf, pagesize=letter)
        layout.draw_card(canvas, CAR, waybill, RR, x=0, y=0)
        canvas.save()
        content = buf.getvalue()
        assert b"%PDF" in content
        assert len(content) > 500, f"Card for {waybill.waybill_type} produced suspiciously small PDF"


def test_experimental1_origination_draws_railroad_name():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    rr = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")
    waybill = WAYBILLS[0]  # LoadedWaybill
    layout.draw_origination_section(canvas, rr, waybill, x=4.5, y=217.0, w=171.0, h=30.5)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("PENNSYLVANIA RAILROAD" in c for c in calls), (
        "Expected railroad name (uppercased) in origination section draw calls"
    )
    assert any("FREIGHT WAYBILL" in c for c in calls), (
        "Expected bill type label in origination section draw calls"
    )


def test_experimental1_car_section_draws_car_identity():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    layout.draw_car_section(canvas, CAR, x=4.5, y=167.0, w=171.0, h=50.0)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("PRR 12345" in c for c in calls), (
        "Expected 'PRR 12345' (road + car_number) in car section draw calls"
    )
    assert any("XM" in c for c in calls), (
        "Expected aar_code 'XM' (KIND field) in car section draw calls"
    )


def test_experimental1_waybill_section_loaded_draws_commodity():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    waybill = LoadedWaybill(
        id="w-1", originating_railroad_id="PRR",
        commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP",
        to_city="Altoona", to_state="PA", consignee_name="Steel Shop",
        from_city="Lewistown", from_state="PA", shipper_name="Grain Co",
    )
    layout.draw_waybill_section(canvas, waybill, x=4.5, y=4.5, w=171.0, h=162.5)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("GRAIN" in c for c in calls), (
        "Expected commodity_id (uppercased) in waybill section draw calls"
    )
    assert any("Altoona, PA" in c for c in calls), (
        "Expected to_city+to_state in waybill section draw calls"
    )


def test_experimental1_waybill_section_empty_draws_for_home():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    waybill = EmptyWaybill(
        id="e-1", originating_railroad_id="PRR",
        from_location_id="ALT", to_location_id="LEW",
        home_billed_from="PHL", home_to_or_via="ENOLA", home_rr="PRR",
    )
    layout.draw_waybill_section(canvas, waybill, x=4.5, y=4.5, w=171.0, h=162.5)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("FOR HOME" in c for c in calls), (
        "Expected 'FOR HOME' section header in EMPTY waybill draw calls"
    )
    assert any("FOR LOADING" in c for c in calls), (
        "Expected 'FOR LOADING' section header in EMPTY waybill draw calls"
    )
    assert any("ALT" in c for c in calls), (
        "Expected from_location_id in EMPTY waybill draw calls"
    )


def test_experimental1_draw_card_all_waybill_types():
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    for waybill in WAYBILLS:
        buf = io.BytesIO()
        canvas = Canvas(buf, pagesize=letter)
        layout.draw_card(canvas, CAR, waybill, RR, x=0, y=0)
        canvas.save()
        content = buf.getvalue()
        assert b"%PDF" in content
        assert len(content) > 500, (
            f"Card for {waybill.waybill_type} produced suspiciously small PDF"
        )


def test_loaded_long_values_render_without_error():
    """Long station/consignee/routing values must not raise and must produce a valid PDF."""
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    waybill = LoadedWaybill(
        id="w-long", originating_railroad_id="PRR",
        commodity_id="coal", shipper_id="s-long", consignee_id="c-long",
        to_city="West Pittsburgh and Allegheny Terminal Junction", to_state="PA",
        from_city="New Cumberland Freight Yard and Classification Center", from_state="PA",
        consignee_name="Pittsburgh Steel Manufacturing Company Incorporated",
        shipper_name="Appalachian Mining and Extraction Cooperative",
        routing=["PRR", "B&O", "C&O", "N&W", "L&N", "Southern Railway Lines"],
    )
    buf = io.BytesIO()
    canvas = Canvas(buf, pagesize=letter)
    layout.draw_card(canvas, CAR, waybill, RR, x=0, y=0)
    canvas.save()
    assert b"%PDF" in buf.getvalue()
