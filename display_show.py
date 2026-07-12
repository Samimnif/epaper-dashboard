#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import time
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFont

import epd7in3f
from data_store import read_data
from formatting import format_collection_date, format_bus_times


class edisplay:
    # Overlay panel geometry/position - tweak these to move or resize the box.
    OVERLAY_WIDTH = 330
    OVERLAY_HEIGHT = 300
    OVERLAY_MARGIN = 12
    OVERLAY_CORNER = "bottom_left"  # one of: bottom_left, bottom_right, top_left, top_right

    def __init__(self):
        self.garbage = False
        self.yard = False
        self.green = False
        self.blue = False
        self.black = False
        self.garbageD = ""
        self.bus = {"99": [], "73": [], "74": [], "70": [], "110": [], "198": [], "299": [], "283": []}

        self.bus_icons = {}  # cache
        self.icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bus_icons")
        self.icon_size = (70, 35)  # width, height (tune)

        self.epd = epd7in3f.EPD()
        self.epd.init()
        self.epd.Clear()
        self.font18 = ImageFont.truetype('Font.ttc', 18)
        self.font24 = ImageFont.truetype('Font.ttc', 24)
        self.font40 = ImageFont.truetype('Font.ttc', 40)
        self.font80 = ImageFont.truetype('Font.ttc', 80)

        self.Himage = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)

    def load_data(self):
        """Pull the latest bus/garbage data via the shared, lock-protected data store."""
        data = read_data()
        self.garbage = data.get("garbage", False)
        self.yard = data.get("yard", False)
        self.green = data.get("green", False)
        self.blue = data.get("blue", False)
        self.black = data.get("black", False)
        self.garbageD = data.get("date", "")

        for route in self.bus:
            self.bus[route] = data.get(route, [])

    def _fit_to_screen(self, img):
        """Resize + center-crop an arbitrary image to the panel's exact resolution.
        Gallery uploads are already 800x480 from the conversion step, so this is
        just a safety net for anything that isn't."""
        img = img.convert("RGB")
        if img.size == (self.epd.width, self.epd.height):
            return img

        ratio = img.width / img.height
        target_ratio = self.epd.width / self.epd.height
        if ratio > target_ratio:
            new_h = self.epd.height
            new_w = int(new_h * ratio)
        else:
            new_w = self.epd.width
            new_h = int(new_w / ratio)

        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (img.width - self.epd.width) // 2
        top = (img.height - self.epd.height) // 2
        return img.crop((left, top, left + self.epd.width, top + self.epd.height))

    def _overlay_bounds(self):
        w, h, m = self.OVERLAY_WIDTH, self.OVERLAY_HEIGHT, self.OVERLAY_MARGIN
        if self.OVERLAY_CORNER == "bottom_right":
            x0, y0 = self.epd.width - w - m, self.epd.height - h - m
        elif self.OVERLAY_CORNER == "top_left":
            x0, y0 = m, m
        elif self.OVERLAY_CORNER == "top_right":
            x0, y0 = self.epd.width - w - m, m
        else:  # bottom_left (default)
            x0, y0 = m, self.epd.height - h - m
        return x0, y0, x0 + w, y0 + h

    @staticmethod
    def _rounded_rect(draw, box, radius, **kwargs):
        """draw.rounded_rectangle needs Pillow >= 8.2 - fall back to a plain
        rectangle on older versions instead of crashing."""
        try:
            draw.rounded_rectangle(box, radius=radius, **kwargs)
        except AttributeError:
            draw.rectangle(box, **kwargs)

    @staticmethod
    def _text_width(draw, text, font):
        try:
            return draw.textlength(text, font=font)
        except AttributeError:
            return 9 * len(text)  # rough fallback for very old Pillow

    def combined_disp(self, image_path=None):
        """The main view: a full-bleed gallery photo with bus/garbage info
        overlaid in a HUD-style console panel in one corner."""
        self.load_data()

        if image_path and os.path.exists(image_path):
            img = self._fit_to_screen(Image.open(image_path))
        else:
            img = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)

        self.Himage = img
        draw = ImageDraw.Draw(self.Himage)

        accent = self.epd.BLUE
        x0, y0, x1, y1 = self._overlay_bounds()
        pad = 12
        x = x0 + pad
        inner_right = x1 - pad

        # Outer console panel: black glass with a thin accent border
        self._rounded_rect(draw, (x0, y0, x1, y1), radius=14, fill=self.epd.BLACK, outline=accent, width=3)

        # --- Header bar: clock + decorative status LEDs ---
        header_h = 34
        self._rounded_rect(draw, (x0 + 4, y0 + 4, x1 - 4, y0 + 4 + header_h), radius=10, fill=accent)
        draw.text((x, y0 + 8), datetime.now().strftime("%H:%M"), font=self.font24, fill=self.epd.WHITE)

        led_colors = [self.epd.GREEN, self.epd.YELLOW, self.epd.RED]
        led_r = 5
        led_cy = y0 + 4 + header_h // 2
        led_cx = inner_right - led_r
        for color in reversed(led_colors):
            draw.ellipse((led_cx - led_r, led_cy - led_r, led_cx + led_r, led_cy + led_r), fill=color)
            led_cx -= (led_r * 2 + 6)

        y = y0 + 4 + header_h + 12

        # --- Collection section ---
        draw.text((x, y), "COLLECTION", font=self.font18, fill=accent)
        y += 22
        collection_date = format_collection_date(self.garbageD)
        draw.text((x, y), collection_date, font=self.font18, fill=self.epd.WHITE)
        y += 28

        bin_defs = [
            ("garbage", self.garbage, self.epd.RED, "GRB"),
            ("yard", self.yard, self.epd.ORANGE, "YRD"),
            ("green", self.green, self.epd.GREEN, "GRN"),
            ("blue", self.blue, self.epd.BLUE, "BLU"),
            ("black", self.black, self.epd.WHITE, "BLK"),  # white chip so it reads on the black panel
        ]
        active = [(color, label) for _, is_active, color, label in bin_defs if is_active]

        if active:
            chip_h = 22
            chip_x = x
            for color, label in active:
                chip_w = int(self._text_width(draw, label, self.font18)) + 14
                if chip_x + chip_w > inner_right:
                    chip_x = x
                    y += chip_h + 6
                text_color = self.epd.BLACK if color in (self.epd.WHITE, self.epd.YELLOW, self.epd.ORANGE) else self.epd.WHITE
                self._rounded_rect(draw, (chip_x, y, chip_x + chip_w, y + chip_h), radius=6, fill=color)
                draw.text((chip_x + 7, y + 2), label, font=self.font18, fill=text_color)
                chip_x += chip_w + 6
            y += chip_h + 12
        else:
            draw.text((x, y), "No collection this week", font=self.font18, fill=self.epd.WHITE)
            y += 24

        draw.line((x, y, inner_right, y), fill=accent, width=2)
        y += 12

        # --- Buses section: route, minutes, and a small "time until arrival" gauge ---
        draw.text((x, y), "BUSES", font=self.font18, fill=accent)
        y += 24

        now = datetime.now()
        max_lines = 4
        shown = 0
        gauge_w, gauge_h = 60, 10
        gauge_x = inner_right - gauge_w
        max_wait_for_gauge = 30  # minutes; gauge reads "full" for anything sooner than this

        for route, times in self.bus.items():
            entries = format_bus_times(times, now=now, max_items=1)
            if not entries:
                continue
            minutes = entries[0]["minutes"]

            draw.text((x, y), route, font=self.font18, fill=self.epd.WHITE)
            draw.text((gauge_x - 48, y), f"{minutes}m", font=self.font18, fill=self.epd.WHITE)

            fill_ratio = max(0.0, min(1.0, 1 - (minutes / max_wait_for_gauge)))
            filled_w = int(gauge_w * fill_ratio)
            draw.rectangle((gauge_x, y + 4, gauge_x + gauge_w, y + 4 + gauge_h), outline=accent, width=1)
            if filled_w > 0:
                draw.rectangle((gauge_x, y + 4, gauge_x + filled_w, y + 4 + gauge_h), fill=accent)

            y += 24
            shown += 1
            if shown >= max_lines or y > y1 - pad:
                break

        if shown == 0:
            draw.text((x, y), "No buses soon", font=self.font18, fill=self.epd.WHITE)

        print(
            f"display_show: combined_disp redrawing - photo={os.path.basename(image_path) if image_path else 'none'}, "
            f"collection={collection_date}, active_bins={[label for _, label in active]}, bus_lines_shown={shown}"
        )
        self.epd.display(self.epd.getbuffer(self.Himage))

    # --- Kept for standalone/manual use; not used by the combined loop in main.py ---

    def gallery_disp_img(self, image_path):
        """Show a single image with no overlay. Non-blocking - caller controls timing."""
        Himage = Image.open(image_path)
        self.epd.display(self.epd.getbuffer(Himage))

    def get_bus_icon(self, route: str):
        if route in self.bus_icons:
            return self.bus_icons[route]

        path = os.path.join(self.icon_dir, f"{route}.bmp")
        if not os.path.exists(path):
            self.bus_icons[route] = None
            return None

        img = Image.open(path).convert("RGB")
        if self.icon_size:
            img = img.resize(self.icon_size)

        self.bus_icons[route] = img
        return img


if __name__ == '__main__':
    newdisplay = edisplay()
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery")
    files = [
        os.path.join(folder, f)
        for f in sorted(os.listdir(folder))
        if os.path.isfile(os.path.join(folder, f))
    ]
    newdisplay.combined_disp(files[0] if files else None)
    time.sleep(3)