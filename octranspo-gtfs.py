########### Python 3.2 #############
import urllib.request, json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('API_KEY')

try:
    url = "https://nextrip-public-api.azure-api.net/octranspo/gtfs-rt-vp/beta/v1/VehiclePositions?stop_id=8903&trip_id=90"

    hdr ={
    # Request headers
    'Cache-Control': 'no-cache',
    'Ocp-Apim-Subscription-Key': API_KEY,
    }

    req = urllib.request.Request(url, headers=hdr)

    req.get_method = lambda: 'GET'
    response = urllib.request.urlopen(req)
    print(response.getcode())
    data = response.read()
    print(data)  # Print the raw data
    try:
        JSON_object = json.loads(data.decode('utf-8'))
        print(JSON_object)
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
except Exception as e:
    print(e)