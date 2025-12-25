#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import epd7in3f
import time
from PIL import Image,ImageDraw,ImageFont
import traceback
import json
from datetime import date, datetime

class edisplay:
    def __init__(self):
        self.garbage = False
        self.yard = False
        self.green = False
        self.blue = False
        self.black = False
        self.garbageD = ""
        self.bus = {"99":[], "73":[], "74":[], "70":[], "110":[], "198":[], "299":[], "283":[]}

        self.bus_icons = {}  # cache
        self.icon_dir = "./bus_icons"
        self.icon_size = (70, 35)  # width, height (tune)

        self.epd = epd7in3f.EPD()
        self.epd.init()
        self.epd.Clear()
        self.font24 = ImageFont.truetype('Font.ttc', 24)
        self.font18 = ImageFont.truetype('Font.ttc', 18)
        self.font40 = ImageFont.truetype('Font.ttc', 40)
        self.font80 = ImageFont.truetype('Font.ttc', 80)

        self.Himage = Image.new('RGB', (self.epd.width, self.epd.height), self.epd.WHITE)  # 255: clear the frame

    def read_data(self, fileName):
        with open(fileName, 'r') as f:
            data = json.load(f)
        self.garbage = data["garbage"]
        self.yard = data["yard"]
        self.green = data["green"]
        self.blue = data["blue"]
        self.black = data["black"]
        self.garbageD = data["date"]

        self.bus["99"] = data["99"]
        self.bus["70"] = data["73"]
        self.bus["73"] = data["70"]
        self.bus["74"] = data["74"]
        self.bus["110"] = data["110"]
        self.bus["198"] = data["198"]
        self.bus["299"] = data["299"]
        self.bus["283"] = data["283"]

    def update_display(self):
        draw = ImageDraw.Draw(self.Himage)
        draw.text((5, 0), 'Garbage Day: 20 Sept', font=self.font18, fill=self.epd.RED)
        print("updated")

    def sample_disp(self):
        draw = ImageDraw.Draw(self.Himage)
        draw.text((5, 0), f'{date.today().strftime("%B %d, %Y")}', font=self.font40, fill=self.epd.RED)
        draw.rectangle((5, 170, 55, 220), fill=self.epd.ORANGE)
        draw.text((60, 185), 'Garbage', font=self.font18, fill=self.epd.ORANGE)
        draw.rectangle((5, 230, 55, 280), fill=self.epd.YELLOW)
        draw.text((60, 245), 'Yard Trimmings', font=self.font18, fill=self.epd.YELLOW)
        draw.rectangle((5, 290, 55, 340), fill=self.epd.GREEN)
        draw.text((60, 305), 'Green Bin', font=self.font18, fill=self.epd.GREEN)
        draw.rectangle((5, 350, 55, 400), fill=self.epd.BLUE)
        draw.text((60, 365), 'Blue - Plastic', font=self.font18, fill=self.epd.BLUE)
        draw.rectangle((5, 410, 55, 460), fill=self.epd.BLACK)
        draw.text((60, 425), 'Black - Paper/Cardboard', font=self.font18, fill=self.epd.BLACK)

        draw.line((350, 5, 350, 450), fill = self.epd.BLACK)

        draw.text((400, 20), 'Next Bus ', font=self.font40, fill=self.epd.RED)
        draw.text((400, 50), '99', font=self.font80, fill=self.epd.BLUE)
        draw.text((400, 200), 'Then', font=self.font40, fill=self.epd.RED)

        self.epd.display(self.epd.getbuffer(self.Himage))

    def gallery_disp(self):
        folder = "gallery"
        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
        ]

        for i in files:
            print(i)
            Himage = Image.open(i)
            self.epd.display(self.epd.getbuffer(Himage))
            time.sleep(30)

    def get_bus_icon(self, route: str):
        """Return a PIL Image for the route icon, cached. None if missing."""
        if route in self.bus_icons:
            return self.bus_icons[route]

        path = os.path.join(self.icon_dir, f"{route}.bmp")
        if not os.path.exists(path):
            self.bus_icons[route] = None
            return None

        img = Image.open(path).convert("RGB")

        # resize to fit your row height nicely
        if self.icon_size:
            img = img.resize(self.icon_size)

        self.bus_icons[route] = img
        return img

    def day_disp(self):
        self.read_data("./display-data.json")
        draw = ImageDraw.Draw(self.Himage)

        draw.text((5, 0), f'{date.today().strftime("%B %d, %Y")}', font=self.font40, fill=self.epd.BLACK)
        draw.text((5, 30), f'{datetime.now().strftime("%H:%M")}', font=self.font80, fill=self.epd.BLACK)

        dt = datetime.strptime(self.garbageD, "%Y%m%d")
        formatted = dt.strftime("%B %d, %Y")
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

        #separator
        draw.line((380, 5, 380, 450), fill = self.epd.BLACK)

        #OCtranspo Part
        x_route = 400
        x_times = 500
        header_h = 50
        row_h = 45  # vertical spacing between routes
        time_gap = 85  # horizontal spacing between times (adjust)
        now = int(time.time())

        max_times = 4  # show only next N times per route (optional)

        draw.text((400, 0), f'Buses', font=self.font40, fill=self.epd.RED)
        for row, (route, times) in enumerate(self.bus.items()):
            y = header_h + row * row_h

            # Route label
            #draw.text((x_route, y), route, font=self.font40, fill=self.epd.BLACK)

            icon = self.get_bus_icon(route)
            if icon is not None:
                self.Himage.paste(icon, (x_route, y + 5))  # +5 to vertically center a bit
            else:
                # fallback if icon missing
                draw.text((x_route, y), route, font=self.font40, fill=self.epd.BLACK)

            # Times across the row
            for col, ts in enumerate(times[:max_times]):
                diff_sec = int(ts) - now
                diff_min = max(0, diff_sec // 60)  # no negatives

                t_str = datetime.fromtimestamp(int(ts)).strftime("%H:%M")
                draw.text((x_times + col * time_gap, y + 10), f"{diff_min} min", font=self.font18, fill=self.epd.BLACK)

        self.epd.display(self.epd.getbuffer(self.Himage))


if __name__ == '__main__':
    newdisplay = edisplay()
    #newdisplay.read_data("display-data.json")
    #newdisplay.sample_disp()
    newdisplay.day_disp()
    time.sleep(3)
    newdisplay.gallery_disp()

"""epd = epd7in3f.EPD()
epd.init()
epd.Clear()
font24 = ImageFont.truetype('Font.ttc', 24)
font18 = ImageFont.truetype('Font.ttc', 18)
font40 = ImageFont.truetype('Font.ttc', 40)

# Drawing on the image
Himage = Image.new('RGB', (epd.width, epd.height), epd.WHITE)  # 255: clear the frame
draw = ImageDraw.Draw(Himage)
draw.text((5, 0), 'hello world', font = font18, fill = epd.RED)
draw.text((5, 20), '7.3inch e-Paper (F)', font = font24, fill = epd.YELLOW)
draw.text((5, 45), u'å¾®é›ªç”µå­', font = font40, fill = epd.GREEN)
draw.text((5, 85), u'å¾®é›ªç”µå­', font = font40, fill = epd.BLUE)
draw.text((5, 125), u'å¾®é›ªç”µå­', font = font40, fill = epd.ORANGE)

draw.line((5, 170, 80, 245), fill = epd.BLUE)
draw.line((80, 170, 5, 245), fill = epd.ORANGE)
draw.rectangle((5, 170, 80, 245), outline = epd.BLACK)
draw.rectangle((90, 170, 165, 245), fill = epd.GREEN)
draw.arc((5, 250, 80, 325), 0, 360, fill = epd.RED)
draw.chord((90, 250, 165, 325), 0, 360, fill = epd.YELLOW)
epd.display(epd.getbuffer(Himage))
time.sleep(3)

# read bmp file
Himage = Image.open('7.3inch-1.bmp')
epd.display(epd.getbuffer(Himage))
time.sleep(3)

Himage = Image.open('7.3inch-3.bmp')
epd.display(epd.getbuffer(Himage))
time.sleep(3)

epd.Clear()

epd.sleep()"""