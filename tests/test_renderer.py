from pathlib import Path
from waybill_generator.renderer.pdf import render_pdf
from waybill_generator.layouts.standard_prr import StandardPrrLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import LoadedWaybill, EmptyWaybill

CAR_A = Car(id="PRR-1", road="PRR", car_number="1", car_type="X29", aar_code="XM", capacity_tons=50)
CAR_B = Car(id="PRR-2", road="PRR", car_number="2", car_type="H21a", aar_code="HM", capacity_tons=70)
LOADED = LoadedWaybill(id="w-1", commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP")
EMPTY = EmptyWaybill(id="e-1", from_location_id="ALT", to_location_id="LEW")


def test_render_creates_pdf(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED)], StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_pdf_header(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED)], StandardPrrLayout(), out)
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_multiple_pairs(tmp_path):
    out = tmp_path / "multi.pdf"
    pairs = [(CAR_A, LOADED), (CAR_B, EMPTY)] * 5  # 10 pairs = 2 pages
    render_pdf(pairs, StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 1000


def test_render_empty_pairs(tmp_path):
    out = tmp_path / "empty.pdf"
    render_pdf([], StandardPrrLayout(), out)
    assert out.exists()
