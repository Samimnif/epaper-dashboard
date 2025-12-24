import threading
import time

from octranspo_gtfs import *
from garbage_collection import *
from display_show import *

display = edisplay()

threading.Timer(10, update_json).start()
threading.Timer(86400, get_garbage).start()

while True:
    display
    time.sleep(1)