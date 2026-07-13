#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import time
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import epd7in3f
from data_store import read_data
from formatting import format_collection_date, format_bus_times


class edisplay:
    # Layout constants - tweak to reposition/resize things.
    MARGIN = 16
    TIME_CORNER = "top_right"    # one of: top_left, top_right, bottom_left, bottom_right
    INFO_CORNER = "bottom_left"  # one of: top_left, top_right, bottom_left, bottom_right

    # Frosted-glass info panel ("Liquid Glass" style). The panel is built by
    # blurring + tinting the PHOTO PIXELS BEHIND IT (not a flat color), then
    # letting the final 7-color quantization dither that into a frosted-looking
    # texture. It isn't true pixel transparency (this hardware can't do that),
    # but it reads as translucent rather than a flat solid block.
    PANEL_WIDTH = 330
    PANEL_HEIGHT = 300
    PANEL_CORNER_RADIUS = 20
    PANEL_BLUR_RADIUS = 8       # how "frosted"/soft the photo behind it looks
    PANEL_TINT_RGB = (0, 0, 0)  # tint color blended into the blurred photo
    PANEL_TINT_ALPHA = 130      # 0-255: how strong the tint is (higher = more opaque)

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

    def _box_at_corner(self, corner, width, height, margin):
        """Bounding box (x0, y0, x1, y1) for a WxH panel anchored at a screen corner."""
        if corner == "top_right":
            x0 = self.epd.width - margin - width
            y0 = margin
        elif corner == "bottom_right":
            x0 = self.epd.width - margin - width
            y0 = self.epd.height - margin - height
        elif corner == "bottom_left":
            x0 = margin
            y0 = self.epd.height - margin - height
        else:  # top_left (default)
            x0 = margin
            y0 = margin
        return x0, y0, x0 + width, y0 + height

    def _frosted_panel(self, base_img, box):
        """Return a copy of base_img with a frosted-glass rounded panel blended
        into it at `box`: the photo pixels under the panel get blurred and
        tinted (not replaced with a flat color), so the photo still shows
        through - the closest a 7-color e-paper can get to real translucency."""
        x0, y0, x1, y1 = box
        region = base_img.crop(box)

        blurred = region.filter(ImageFilter.GaussianBlur(self.PANEL_BLUR_RADIUS))
        tint_layer = Image.new("RGB", region.size, self.PANEL_TINT_RGB)
        blended = Image.blend(blurred, tint_layer, self.PANEL_TINT_ALPHA / 255)

        # Rounded-corner mask so the panel has soft corners instead of a hard box
        mask = Image.new("L", region.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        self._rounded_rect(mask_draw, (0, 0, region.size[0] - 1, region.size[1] - 1),
                            self.PANEL_CORNER_RADIUS, fill=255)

        result = base_img.copy()
        result.paste(blended, (x0, y0), mask)

        # A thin light edge highlight, like a glass rim catching light
        edge_draw = ImageDraw.Draw(result)
        self._rounded_rect(edge_draw, box, self.PANEL_CORNER_RADIUS, outline=self.epd.WHITE, width=2)
        return result

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
        """The main view: a full-bleed gallery photo, a big clock floating
        top-right, and bus/garbage info sitting on a frosted-glass panel in
        one corner (blurred/tinted photo showing through, not a flat color)."""
        self.load_data()

        if image_path and os.path.exists(image_path):
            img = self._fit_to_screen(Image.open(image_path))
        else:
            img = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)

        panel_box = self._box_at_corner(self.INFO_CORNER, self.PANEL_WIDTH, self.PANEL_HEIGHT, self.MARGIN)
        self.Himage = self._frosted_panel(img, panel_box)
        draw = ImageDraw.Draw(self.Himage)

        # --- Big clock, top-right, floating directly over the photo (no panel) ---
        time_text = datetime.now().strftime("%H:%M")
        time_w = self._text_width(draw, time_text, self.font40)
        tx, ty = self._corner_xy(self.TIME_CORNER, self.MARGIN)
        tx -= time_w  # anchor is the corner point; shift left by the text width to right-align
        self._outlined_text(draw, (tx, ty), time_text, font=self.font40,
                             fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=3)

        # --- Info content, laid out inside the frosted panel ---
        px0, py0, px1, py1 = panel_box
        pad = 14
        x = px0 + pad
        y = py0 + pad
        max_x = px1 - pad

        collection_date = format_collection_date(self.garbageD)
        self._outlined_text(draw, (x, y), f"Collection: {collection_date}", font=self.font18,
                             fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=1)
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
                if item_x + item_w > max_x:
                    item_x = x
                    y += 22
                self._framed_rect(draw, (item_x, y, item_x + 14, y + 14), fill=color)
                self._outlined_text(draw, (item_x + 20, y - 3), label, font=self.font18,
                                     fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=1)
                item_x += item_w
            y += 22
        else:
            self._outlined_text(draw, (x, y), "No collection this week", font=self.font18,
                                 fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=1)
            y += 22

        y += 10

        self._outlined_text(draw, (x, y), "BUSES", font=self.font18,
                             fill=self.epd.YELLOW, outline=self.epd.BLACK, stroke_width=1)
        y += 24

        now = datetime.now()
        max_lines = 4
        shown = 0
        gauge_w, gauge_h = 60, 10
        gauge_x = x + 100
        max_wait_for_gauge = 30  # minutes; gauge reads "full" for anything sooner than this

        for route, times in self.bus.items():
            if y > py1 - pad - gauge_h:
                break
            entries = format_bus_times(times, now=now, max_items=1)
            if not entries:
                continue
            minutes = entries[0]["minutes"]

            self._outlined_text(draw, (x, y), route, font=self.font18,
                                 fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=1)
            self._outlined_text(draw, (x + 40, y), f"{minutes}m", font=self.font18,
                                 fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=1)

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
                                 fill=self.epd.WHITE, outline=self.epd.BLACK, stroke_width=1)

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