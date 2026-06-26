from pathlib import Path
from waybill_generator.renderer.pdf import render_pdf
from waybill_generator.layouts.modelling_the_sp import StandardPrrLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import LoadedWaybill, EmptyWaybill

CAR_A = Car(id="PRR-1", road="PRR", car_number="1", aar_code="XM", capacity_tons=50)
CAR_B = Car(id="PRR-2", road="PRR", car_number="2", aar_code="HM", capacity_tons=70)
RR = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")
LOADED = LoadedWaybill(id="w-1", originating_railroad_id="PRR",
                       commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP")
EMPTY = EmptyWaybill(id="e-1", originating_railroad_id="PRR",
                     from_location_id="ALT", to_location_id="LEW")


def test_render_creates_pdf(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED, RR)], StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_pdf_header(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED, RR)], StandardPrrLayout(), out)
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_multiple_triples(tmp_path):
    out = tmp_path / "multi.pdf"
    triples = [(CAR_A, LOADED, RR), (CAR_B, EMPTY, RR)] * 5  # 10 cards = 2 pages
    render_pdf(triples, StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 1000


def test_render_empty_list(tmp_path):
    out = tmp_path / "empty.pdf"
    render_pdf([], StandardPrrLayout(), out)
    assert out.exists()
