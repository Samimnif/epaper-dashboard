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
    # Layout constants for the no-background overlay - tweak to reposition things.
    MARGIN = 16
    INFO_MAX_WIDTH = 380   # keeps the bin/bus info clustered in one corner instead of spanning the screen
    TIME_CORNER = "top_right"    # one of: top_left, top_right, bottom_left, bottom_right
    INFO_CORNER = "bottom_left"  # one of: top_left, top_right, bottom_left, bottom_right

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

    def _corner_xy(self, corner, margin):
        """Top-left anchor point for a given screen corner."""
        if corner == "top_right":
            return self.epd.width - margin, margin
        elif corner == "bottom_right":
            return self.epd.width - margin, self.epd.height - margin
        elif corner == "bottom_left":
            return margin, self.epd.height - margin
        else:  # top_left (default)
            return margin, margin

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

    @staticmethod
    def _outlined_text(draw, xy, text, font, fill, outline, stroke_width=2):
        """Draw text with a solid outline/halo so it stays readable directly
        over an arbitrary photo, with no background box needed."""
        try:
            draw.text(xy, text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=outline)
        except TypeError:
            # Pillow < 6.2 doesn't support stroke_width - fake it by drawing
            # the text offset in every direction first, then the real text on top.
            x, y = xy
            for dx in (-stroke_width, 0, stroke_width):
                for dy in (-stroke_width, 0, stroke_width):
                    if dx or dy:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline)
            draw.text(xy, text, font=font, fill=fill)

    def _framed_rect(self, draw, box, fill=None, frame_pad=2):
        """A small rect (icon/gauge) with a black backdrop plus a white ring
        around it, so it stays visible whether the photo behind it is light
        or dark - a plain white-outlined shape can vanish on a light photo,
        and a plain black one can vanish on a dark photo; this survives both."""
        x0, y0, x1, y1 = box
        draw.rectangle((x0 - frame_pad, y0 - frame_pad, x1 + frame_pad, y1 + frame_pad), fill=self.epd.BLACK)
        draw.rectangle(box, fill=fill, outline=self.epd.WHITE, width=1)

    def combined_disp(self, image_path=None):
        """The main view: a full-bleed gallery photo with the clock and
        bus/garbage info floating directly on top - no background box, so it
        blends into the photo. Legibility comes from outlined ("halo") text
        instead of a solid panel."""
        self.load_data()

        if image_path and os.path.exists(image_path):
            img = self._fit_to_screen(Image.open(image_path))
        else:
            img = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)

        self.Himage = img
        draw = ImageDraw.Draw(self.Himage)

        # --- Big clock, top-right, floating over the photo ---
        time_text = datetime.now().strftime("%H:%M")
        time_w = self._text_width(draw, time_text, self.font40)
        tx, ty = self._corner_xy(self.TIME_CORNER, self.MARGIN)
        tx -= time_w  # anchor is the corner point; shift left by the text width to right-align
        self._outlined_text(draw, (tx, ty), time_text, font=self.font40,
                             fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=3)

        # --- Info block (collection + bins + buses), floating in a corner ---
        ix, iy = self._corner_xy(self.INFO_CORNER, self.MARGIN)
        # Reserve enough vertical room above the bottom margin for: date line,
        # up to 2 rows of bin icons, a gap, "BUSES" label, and up to 4 bus rows.
        block_height = 22 + 44 + 10 + 24 + (4 * 24)
        if self.INFO_CORNER.startswith("bottom"):
            y = iy - block_height
        else:
            y = iy
        x = ix

        collection_date = format_collection_date(self.garbageD)
        self._outlined_text(draw, (x, y), f"Collection: {collection_date}", font=self.font18,
                             fill=self.epd.WHITE, outline=self.epd.BLACK)
        y += 26

        bin_defs = [
            ("garbage", self.garbage, self.epd.RED, "GRB"),
            ("yard", self.yard, self.epd.ORANGE, "YRD"),
            ("green", self.green, self.epd.GREEN, "GRN"),
            ("blue", self.blue, self.epd.BLUE, "BLU"),
            ("black", self.black, self.epd.BLACK, "BLK"),
        ]
        active = [(color, label) for _, is_active, color, label in bin_defs if is_active]

        if active:
            item_x = x
            for color, label in active:
                label_w = self._text_width(draw, label, self.font18)
                item_w = 14 + 6 + int(label_w) + 16
                if item_x + item_w > x + self.INFO_MAX_WIDTH:
                    item_x = x
                    y += 22
                self._framed_rect(draw, (item_x, y, item_x + 14, y + 14), fill=color)
                self._outlined_text(draw, (item_x + 20, y - 3), label, font=self.font18,
                                     fill=self.epd.WHITE, outline=self.epd.BLACK)
                item_x += item_w
            y += 22
        else:
            self._outlined_text(draw, (x, y), "No collection this week", font=self.font18,
                                 fill=self.epd.WHITE, outline=self.epd.BLACK)
            y += 22

        y += 10

        self._outlined_text(draw, (x, y), "BUSES", font=self.font18,
                             fill=self.epd.YELLOW, outline=self.epd.BLACK)
        y += 24

        now = datetime.now()
        max_lines = 4
        shown = 0
        gauge_w, gauge_h = 60, 10
        gauge_x = x + 100
        max_wait_for_gauge = 30  # minutes; gauge reads "full" for anything sooner than this

        for route, times in self.bus.items():
            entries = format_bus_times(times, now=now, max_items=1)
            if not entries:
                continue
            minutes = entries[0]["minutes"]

            self._outlined_text(draw, (x, y), route, font=self.font18,
                                 fill=self.epd.WHITE, outline=self.epd.BLACK)
            self._outlined_text(draw, (x + 40, y), f"{minutes}m", font=self.font18,
                                 fill=self.epd.WHITE, outline=self.epd.BLACK)

            fill_ratio = max(0.0, min(1.0, 1 - (minutes / max_wait_for_gauge)))
            filled_w = int(gauge_w * fill_ratio)
            self._framed_rect(draw, (gauge_x, y + 4, gauge_x + gauge_w, y + 4 + gauge_h))
            if filled_w > 0:
                draw.rectangle((gauge_x, y + 4, gauge_x + filled_w, y + 4 + gauge_h), fill=self.epd.BLUE)

            y += 24
            shown += 1
            if shown >= max_lines:
                break

        if shown == 0:
            self._outlined_text(draw, (x, y), "No buses soon", font=self.font18,
                                 fill=self.epd.WHITE, outline=self.epd.BLACK)

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