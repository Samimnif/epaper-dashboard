import threading
import time

from octranspo_gtfs import *
from garbage_collection import *
from display_show import *

display = edisplay()

threading.Timer(30, update_json).start()
threading.Timer(86400, get_garbage).start()

MORNING_START = 5   # 05:00
MORNING_END = 14    # 10:00 (exclusive)

folder = "gallery"
count = 0

while True:
    now = datetime.now()
    hour = now.hour

    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ]

    # display.day_disp()
    # time.sleep(5)
    # display.gallery_disp()
    if MORNING_START <= hour < MORNING_END:
        display.day_disp()
    else:
        if count >= len(files):
            count = 0
        else: count += 1

        #display.gallery_disp()
        display.gallery_disp_img(files[count])

    time.sleep(70)