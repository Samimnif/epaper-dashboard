import urllib.request, json
import os
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import csv

load_dotenv()

API_KEY = os.getenv('API_KEY')
trips_dict = dict()
stops_dict = dict()

with open("./GTFSExport/trips.txt", mode='r', newline='', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    for row in reader:
        trip_id = row['trip_id']
        trips_dict[trip_id] = {
            'route_id': row.get('route_id'),
            'trip_headsign': row.get('trip_headsign'),
            'direction_id': row.get('direction_id')
        }

with open("./GTFSExport/stops.txt", mode='r', newline='', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    for row in reader:
        stop_id = row['stop_id']
        stops_dict[stop_id] = {
            'stop_name': row.get('stop_name'),
            'stop_code': row.get('stop_code')
        }

def get_trips():
    try:
        url = "https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-tp/beta/v1/TripUpdates"

        hdr = {
            # Request headers
            'Cache-Control': 'no-cache',
            'Ocp-Apim-Subscription-Key': API_KEY,
        }

        req = urllib.request.Request(url, headers=hdr)
        req.get_method = lambda: 'GET'
        response = urllib.request.urlopen(req)

        return response.read()
    except Exception as e:
        print(e)

def get_bus_atStop(bus_id, stop_code):
    global trips_dict, stops_dict
    data = get_trips()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        trip_update = entity.trip_update
        route_id = trip_update.trip.route_id

        if route_id != bus_id:
            continue  # Skip other routes

        print(f"\nTrip ID: {trip_update.trip.trip_id}, Route: {route_id}\n {trips_dict[trip_update.trip.trip_id]}")
        for stu in trip_update.stop_time_update:
            stop_id = stu.stop_id

            # Debug: print all stop IDs for this trip
            print(f"  -> Stop ID in trip: {stop_id} {stops_dict[stop_id]['stop_name']}")

            # Check if this is the stop we care about
            if stops_dict[stop_id]['stop_code'] == stop_code:
                # Prefer arrival time, fallback to departure
                if stu.HasField("arrival"):
                    timestamp = stu.arrival.time
                    kind = "Arrival"
                elif stu.HasField("departure"):
                    timestamp = stu.departure.time
                    kind = "Departure"
                else:
                    continue

                readable_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {kind} at Stop {stop_id} => {readable_time}")
                #return readable_time, timestamp


get_bus_atStop('99','3048')
# try:
#     url = "https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-tp/beta/v1/TripUpdates"
#     #url = "https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-vp/beta/v1/VehiclePositions"
#     hdr ={
#     # Request headers
#     'Cache-Control': 'no-cache',
#     'Ocp-Apim-Subscription-Key': API_KEY,
#     }
#
#     req = urllib.request.Request(url, headers=hdr)
#
#     TARGET_ROUTE_ID = "99"
#     TARGET_STOP_ID = "4645"
#
#     req.get_method = lambda: 'GET'
#     response = urllib.request.urlopen(req)
#
#     data = response.read()
#     feed = gtfs_realtime_pb2.FeedMessage()
#     feed.ParseFromString(data)
#
#     try:
#         for entity in feed.entity:
#             if not entity.HasField("trip_update"):
#                 continue
#
#             trip_update = entity.trip_update
#             route_id = trip_update.trip.route_id
#
#             if route_id != TARGET_ROUTE_ID:
#                 continue  # Skip other routes
#
#             print(f"\nTrip ID: {trip_update.trip.trip_id}, Route: {route_id}\n {trips_dict[trip_update.trip.trip_id]}")
#             for stu in trip_update.stop_time_update:
#                 stop_id = stu.stop_id
#
#                 # Debug: print all stop IDs for this trip
#                 print(f"  -> Stop ID in trip: {stop_id} {stops_dict[stop_id]['stop_name']}")
#
#                 # Check if this is the stop we care about
#                 if stops_dict[stop_id]['stop_code'] == TARGET_STOP_ID:
#                     # Prefer arrival time, fallback to departure
#                     if stu.HasField("arrival"):
#                         timestamp = stu.arrival.time
#                         kind = "Arrival"
#                     elif stu.HasField("departure"):
#                         timestamp = stu.departure.time
#                         kind = "Departure"
#                     else:
#                         continue
#
#                     readable_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
#                     print(f"  {kind} at Stop {stop_id} => {readable_time}")
#
#     except json.JSONDecodeError as e:
#         print("Error decoding JSON:", e)
# except Exception as e:
#     print(e)