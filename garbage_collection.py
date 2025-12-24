import urllib.request, json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

def get_garbage():
    load_dotenv()

    CLIENT_ID = os.getenv('CLIENT_ID')

    url = f"https://recollect.a.ssl.fastly.net/api/places/{CLIENT_ID}/services/208/events.en.ics"

    req = urllib.request.Request(url)

    req.get_method = lambda: 'GET'
    response = urllib.request.urlopen(req)
    print(response.getcode())
    data = response.read()

    ics_data = data.decode('utf-8')
    events = []
    in_event = False
    lines = ics_data.split('\n')
    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            event = {}
            in_event = True
            continue
        if line.startswith("END:VEVENT"):
            events.append(event)
            in_event = False
            continue
        if in_event:
            if ':' in line:
                key, val = line.split(':', 1)  # Split only once to handle values containing ':'
                event[key] = val.split('\r')[0]

    #print(events)

    today = datetime.today().date()
    start_of_this_week = today - timedelta(days=today.weekday())
    start_of_next_week = start_of_this_week + timedelta(weeks=1)
    end_of_next_week = start_of_next_week + timedelta(weeks=1)
    events_this_week = []
    events_next_week = []

    for event in events:
        # Parse the start date of the event
        start_date_str = event['DTSTART;VALUE=DATE']
        start_date = datetime.strptime(start_date_str, '%Y%m%d').date()

        # Check if the event is for this week or next week
        if start_of_this_week <= start_date < start_of_next_week:
            events_this_week.append(event)
        elif start_date >= start_of_next_week and start_date < end_of_next_week:
            events_next_week.append(event)

    with open('./display-data.json', 'r') as file:
        data = json.load(file)
    with open('./display-data.json', 'w') as file:
        for event in events_this_week:
            data['date'] = event['DTSTART;VALUE=DATE']#datetime.strptime(event['DTSTART;VALUE=DATE'], '%Y%m%d')
            for i in ['garbage', 'yard', 'green', 'blue', 'black']:
                data[i] = False
            for i in event['DESCRIPTION'].split('\\, '):
                i = i.lower()
                if 'garbage' in i:
                    data['garbage'] = True
                elif 'yard' in i:
                    data['yard'] = True
                elif 'green' in i:
                    data['green'] = True
                elif 'blue' in i:
                    data['blue'] = True
                elif 'black' in i:
                    data['black'] = True
        json.dump(data, file, indent=4)
get_garbage()
