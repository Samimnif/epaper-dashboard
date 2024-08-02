#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import epd7in3f
import time
from PIL import Image,ImageDraw,ImageFont
import traceback

epd = epd7in3f.EPD()   
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
    
epd.sleep()