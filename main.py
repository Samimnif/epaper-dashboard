import threading
import time

from octranspo_gtfs import *
from garbage_collection import *
from display_show import *

display = edisplay()

threading.Timer(30, update_json).start()
threading.Timer(86400, get_garbage).start()

MORNING_START = 5   # 05:00
MORNING_END = 10    # 10:00 (exclusive)

while True:
    now = datetime.now()
    hour = now.hour

    display.day_disp()
    time.sleep(5)
    display.gallery_disp()
    # if MORNING_START <= hour < MORNING_END:
    #     display.day_disp()
    # else:
    #     display.gallery_disp()

    time.sleep(60)