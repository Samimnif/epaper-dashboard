#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import epd7in3f
import time
from PIL import Image,ImageDraw,ImageFont
import traceback
import json
from datetime import date

class edisplay:
    def __init__(self):
        self.garbage = False
        self.yard = False
        self.green = False
        self.blue = False
        self.black = False

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

if __name__ == '__main__':
    newdisplay = edisplay()
    #newdisplay.read_data("display-data.json")
    newdisplay.sample_disp()

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