import urllib.request
import os
import csv

from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

from data_store import update_data

load_dotenv()

API_KEY = os.getenv('API_KEY')

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_trips_dict = {}
_stops_dict = {}

# route -> stop_code, kept in one place so it's easy to add/remove routes
ROUTE_STOPS = {
    '99': '4645',
    '73': '9819',
    '74': '9819',
    '70': '9819',
    '110': '9819',
    '198': '9819',
    '299': '4645',
    '283': '9819',
}


def _load_static_gtfs():
    global _trips_dict, _stops_dict
    trips_path = os.path.join(_BASE_DIR, "GTFSExport", "trips.txt")
    stops_path = os.path.join(_BASE_DIR, "GTFSExport", "stops.txt")

    with open(trips_path, mode='r', newline='', encoding='utf-8') as file:
        for row in csv.DictReader(file):
            _trips_dict[row['trip_id']] = {
                'route_id': row.get('route_id'),
                'trip_headsign': row.get('trip_headsign'),
                'direction_id': row.get('direction_id'),
            }

    with open(stops_path, mode='r', newline='', encoding='utf-8') as file:
        for row in csv.DictReader(file):
            _stops_dict[row['stop_id']] = {
                'stop_name': row.get('stop_name'),
                'stop_code': row.get('stop_code'),
            }


_load_static_gtfs()


def get_trips():
    try:
        url = "https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-tp/beta/v1/TripUpdates"
        hdr = {
            'Cache-Control': 'no-cache',
            'Ocp-Apim-Subscription-Key': API_KEY,
        }
        req = urllib.request.Request(url, headers=hdr, method='GET')
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read()
    except Exception as e:
        print(f"octranspo_gtfs: failed to fetch trip updates: {e}")
        return None


def get_bus_atStop(bus_id, stop_code):
    data = get_trips()
    if data is None:
        return []

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)

    all_times = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        trip_update = entity.trip_update
        if trip_update.trip.route_id != bus_id:
            continue

        for stu in trip_update.stop_time_update:
            stop_info = _stops_dict.get(stu.stop_id)
            if not stop_info or stop_info['stop_code'] != stop_code:
                continue

            if stu.HasField("arrival"):
                timestamp = stu.arrival.time
            elif stu.HasField("departure"):
                timestamp = stu.departure.time
            else:
                continue

            all_times.append(timestamp)

    all_times.sort()
    return all_times


def update_json():
    """Fetch live times for every configured route/stop and merge into display-data.json."""
    results = {route: get_bus_atStop(route, stop_code) for route, stop_code in ROUTE_STOPS.items()}

    def mutate(data):
        data.update(results)

    update_data(mutate)
    print("octranspo_gtfs: display-data.json updated")


if __name__ == "__main__":
    update_json()