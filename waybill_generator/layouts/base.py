from abc import ABC, abstractmethod
from reportlab.pdfgen.canvas import Canvas
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import WaybillBase


class BaseLayout(ABC):
    card_width_pt: float = 180.0
    card_height_pt: float = 252.0
    car_section_fraction: float = 0.33
    gutter_pt: float = 9.0
    content_inset_pt: float = 4.0

    def draw_card(
        self, canvas: Canvas, car: Car, waybill: WaybillBase, x: float, y: float
    ) -> None:
        w = self.card_width_pt
        h = self.card_height_pt
        inset = self.content_inset_pt
        car_h = h * self.car_section_fraction
        waybill_h = h - car_h

        self.draw_car_section(canvas, car, x + inset, y + waybill_h, w - 2 * inset, car_h - inset)
        self.draw_waybill_section(canvas, waybill, x + inset, y + inset, w - 2 * inset, waybill_h - inset)

    @abstractmethod
    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None: ...

    @abstractmethod
    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None: ...
