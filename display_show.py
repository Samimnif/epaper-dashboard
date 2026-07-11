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
    OVERLAY_WIDTH = 300
    OVERLAY_HEIGHT = 230
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

    def combined_disp(self, image_path=None):
        """The main view: a full-bleed gallery photo with bus/garbage info
        overlaid in a corner box."""
        self.load_data()

        if image_path and os.path.exists(image_path):
            img = self._fit_to_screen(Image.open(image_path))
        else:
            img = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)

        self.Himage = img
        draw = ImageDraw.Draw(self.Himage)

        x0, y0, x1, y1 = self._overlay_bounds()
        draw.rectangle((x0, y0, x1, y1), fill=self.epd.WHITE, outline=self.epd.BLACK, width=3)

        pad = 10
        x = x0 + pad
        y = y0 + pad

        draw.text((x, y), datetime.now().strftime("%H:%M"), font=self.font24, fill=self.epd.BLACK)
        y += 28

        collection_date = format_collection_date(self.garbageD)
        draw.text((x, y), f"Collection: {collection_date}", font=self.font18, fill=self.epd.BLACK)
        y += 22

        bin_rows = [
            ("garbage", self.garbage, self.epd.RED),
            ("yard", self.yard, self.epd.ORANGE),
            ("green", self.green, self.epd.GREEN),
            ("blue", self.blue, self.epd.BLUE),
            ("black", self.black, self.epd.BLACK),
        ]
        active = [(key, color) for key, is_active, color in bin_rows if is_active]

        if active:
            dot_x = x
            for key, color in active:
                draw.rectangle((dot_x, y, dot_x + 16, y + 16), fill=color)
                dot_x += 22
            y += 26
        else:
            draw.text((x, y), "No collection this week", font=self.font18, fill=self.epd.BLACK)
            y += 22

        draw.line((x0 + pad, y, x1 - pad, y), fill=self.epd.BLACK)
        y += 8

        draw.text((x, y), "Buses", font=self.font18, fill=self.epd.RED)
        y += 22

        now = datetime.now()
        max_lines = 4
        shown = 0
        for route, times in self.bus.items():
            entries = format_bus_times(times, now=now, max_items=1)
            if not entries:
                continue
            entry = entries[0]
            draw.text((x, y), f"{route}: {entry['minutes']} min", font=self.font18, fill=self.epd.BLACK)
            y += 20
            shown += 1
            if shown >= max_lines or y > y1 - pad:
                break

        if shown == 0:
            draw.text((x, y), "No buses soon", font=self.font18, fill=self.epd.BLACK)

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