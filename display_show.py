#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import time
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFont

import epd7in3f
from data_store import read_data


class edisplay:
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
        self.font24 = ImageFont.truetype('Font.ttc', 24)
        self.font18 = ImageFont.truetype('Font.ttc', 18)
        self.font40 = ImageFont.truetype('Font.ttc', 40)
        self.font80 = ImageFont.truetype('Font.ttc', 80)

        self.Himage = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)

    def load_data(self):
        """Pull the latest bus/garbage data via the shared, lock-protected data store.

        NOTE: the original code copied data["73"] into self.bus["70"] and
        vice versa - that swap is fixed here so each route maps to itself.
        """
        data = read_data()
        self.garbage = data.get("garbage", False)
        self.yard = data.get("yard", False)
        self.green = data.get("green", False)
        self.blue = data.get("blue", False)
        self.black = data.get("black", False)
        self.garbageD = data.get("date", "")

        for route in self.bus:
            self.bus[route] = data.get(route, [])

    def gallery_disp(self):
        """Loop through every image in gallery/, showing each for an hour. Blocking."""
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery")
        files = [
            os.path.join(folder, f)
            for f in sorted(os.listdir(folder))
            if os.path.isfile(os.path.join(folder, f))
        ]
        for path in files:
            print(path)
            self.gallery_disp_img(path)
            time.sleep(3600)

    def gallery_disp_img(self, image_path):
        """Show a single image. Non-blocking - caller controls timing."""
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

    def day_disp(self):
        self.load_data()

        self.Himage = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)
        draw = ImageDraw.Draw(self.Himage)

        draw.text((5, 0), f'{date.today().strftime("%B %d, %Y")}', font=self.font40, fill=self.epd.BLACK)
        draw.text((5, 30), f'{datetime.now().strftime("%H:%M")}', font=self.font80, fill=self.epd.BLACK)

        if self.garbageD:
            try:
                dt = datetime.strptime(self.garbageD, "%Y%m%d")
                formatted = dt.strftime("%B %d, %Y")
            except ValueError:
                formatted = "unknown"
        else:
            formatted = "unknown"
        draw.text((5, 125), f'Collection: {formatted}', font=self.font24, fill=self.epd.BLACK)

        if self.garbage:
            draw.rectangle((5, 170, 55, 220), fill=self.epd.RED)
            draw.text((60, 185), 'Garbage', font=self.font18, fill=self.epd.RED)
        if self.yard:
            draw.rectangle((5, 230, 55, 280), fill=self.epd.ORANGE)
            draw.text((60, 245), 'Yard Trimmings', font=self.font18, fill=self.epd.ORANGE)
        if self.green:
            draw.rectangle((5, 290, 55, 340), fill=self.epd.GREEN)
            draw.text((60, 305), 'Green Bin', font=self.font18, fill=self.epd.GREEN)
        if self.blue:
            draw.rectangle((5, 350, 55, 400), fill=self.epd.BLUE)
            draw.text((60, 365), 'Plastic', font=self.font18, fill=self.epd.BLUE)
        if self.black:
            draw.rectangle((5, 410, 55, 460), fill=self.epd.BLACK)
            draw.text((60, 425), 'Paper/Cardboard', font=self.font18, fill=self.epd.BLACK)

        draw.line((380, 5, 380, 450), fill=self.epd.BLACK)

        x_route = 400
        x_times = 500
        header_h = 50
        row_h = 45
        time_gap = 85
        now = int(time.time())
        max_times = 4

        draw.text((400, 0), 'Buses', font=self.font40, fill=self.epd.RED)
        for row, (route, times) in enumerate(self.bus.items()):
            y = header_h + row * row_h

            icon = self.get_bus_icon(route)
            if icon is not None:
                self.Himage.paste(icon, (x_route, y + 5))
            else:
                draw.text((x_route, y), route, font=self.font40, fill=self.epd.BLACK)

            for col, ts in enumerate(times[:max_times]):
                diff_min = max(0, (int(ts) - now) // 60)
                draw.text((x_times + col * time_gap, y + 10), f"{diff_min} min", font=self.font18, fill=self.epd.BLACK)

        self.epd.display(self.epd.getbuffer(self.Himage))


if __name__ == '__main__':
    newdisplay = edisplay()
    newdisplay.day_disp()
    time.sleep(3)
    newdisplay.gallery_disp()