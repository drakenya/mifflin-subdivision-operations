from abc import ABC, abstractmethod
from reportlab.pdfgen.canvas import Canvas
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import WaybillBase


class BaseLayout(ABC):
    card_width_pt: float = 180.0
    card_height_pt: float = 252.0
    origination_height_pt: float = 35.0
    car_height_pt: float = 50.0
    gutter_pt: float = 0.0
    content_inset_pt: float = 4.5
    label_font: str = "Times-Roman"
    value_font: str = "Times-Bold"

    def draw_card(
        self,
        canvas: Canvas,
        car: Car,
        waybill: WaybillBase,
        railroad: Railroad,
        x: float,
        y: float,
    ) -> None:
        w = self.card_width_pt
        h = self.card_height_pt
        inset = self.content_inset_pt
        orig_h = self.origination_height_pt
        car_h = self.car_height_pt
        waybill_h = h - orig_h - car_h  # 152

        # Waybill zone (bottom): inset at bottom and sides only
        self.draw_waybill_section(
            canvas, waybill,
            x + inset, y + inset,
            w - 2 * inset, waybill_h - inset,
        )
        # Car zone (middle): bounded by zones above and below, inset sides only
        self.draw_car_section(
            canvas, car,
            x + inset, y + waybill_h,
            w - 2 * inset, car_h,
        )
        # Origination zone (top): inset at top and sides only
        self.draw_origination_section(
            canvas, railroad, waybill,
            x + inset, y + waybill_h + car_h,
            w - 2 * inset, orig_h - inset,
        )

    @abstractmethod
    def draw_origination_section(
        self,
        canvas: Canvas,
        railroad: Railroad,
        waybill: WaybillBase,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None: ...

    @abstractmethod
    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None: ...

    @abstractmethod
    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None: ...
