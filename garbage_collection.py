import urllib.request
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from data_store import update_data

load_dotenv()


def _parse_ics(ics_text):
    events = []
    event = None
    for line in ics_text.split('\n'):
        if line.startswith("BEGIN:VEVENT"):
            event = {}
            continue
        if line.startswith("END:VEVENT"):
            if event is not None:
                events.append(event)
            event = None
            continue
        if event is not None and ':' in line:
            key, val = line.split(':', 1)  # split once, values can contain ':'
            event[key] = val.split('\r')[0]
    return events


def get_garbage():
    """Fetch this week's collection schedule and merge it into display-data.json."""
    client_id = os.getenv('CLIENT_ID')
    if not client_id:
        print("garbage_collection: CLIENT_ID not set in .env, skipping")
        return

    url = f"https://recollect.a.ssl.fastly.net/api/places/{client_id}/services/208/events.en.ics"

    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=15) as response:
            ics_data = response.read().decode('utf-8')
    except Exception as e:
        print(f"garbage_collection: failed to fetch events: {e}")
        return

    events = _parse_ics(ics_data)

    today = datetime.today().date()
    start_of_this_week = today - timedelta(days=today.weekday())
    start_of_next_week = start_of_this_week + timedelta(weeks=1)

    events_this_week = []
    for event in events:
        start_date_str = event.get('DTSTART;VALUE=DATE')
        if not start_date_str:
            continue
        start_date = datetime.strptime(start_date_str, '%Y%m%d').date()
        if start_of_this_week <= start_date < start_of_next_week:
            events_this_week.append(event)

    if not events_this_week:
        print("garbage_collection: no events found for this week")
        return

    def mutate(data):
        for event in events_this_week:
            data['date'] = event['DTSTART;VALUE=DATE']
            for key in ['garbage', 'yard', 'green', 'blue', 'black']:
                data[key] = False
            for part in event.get('DESCRIPTION', '').split('\\, '):
                part = part.lower()
                if 'garbage' in part:
                    data['garbage'] = True
                elif 'yard' in part:
                    data['yard'] = True
                elif 'green' in part:
                    data['green'] = True
                elif 'blue' in part:
                    data['blue'] = True
                elif 'black' in part:
                    data['black'] = True

    update_data(mutate)
    print("garbage_collection: display-data.json updated")


if __name__ == "__main__":
    get_garbage()