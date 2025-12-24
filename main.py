import threading
import time

from octranspo_gtfs import *
from garbage_collection import *
from display_show import *

display = edisplay()

threading.Timer(30, update_json).start()
threading.Timer(86400, get_garbage).start()

while True:
    display.day_disp()
    time.sleep(60)