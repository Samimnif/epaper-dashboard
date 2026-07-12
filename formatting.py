"""
Shared formatting helpers used by both the web dashboard (main.py) and the
e-paper renderer (display_show.py), so the two always show the same thing
the same way.
"""

from datetime import datetime

BIN_LABELS = {
    "garbage": "Garbage",
    "yard": "Yard Trimmings",
    "green": "Green Bin",
    "blue": "Blue - Plastic",
    "black": "Black - Paper/Cardboard",
}

# Fixed display order for the bins
BIN_ORDER = ["garbage", "yard", "green", "blue", "black"]

# Bootstrap badge classes for the web dashboard, keyed the same way
BIN_BADGE_CLASS = {
    "garbage": "text-bg-danger",
    "yard": "text-bg-warning",
    "green": "text-bg-success",
    "blue": "text-bg-primary",
    "black": "text-bg-dark",
}


def format_collection_date(date_str):
    """'20260709' -> 'July 9, 2026'. Returns 'Unknown' if missing/unparseable."""
    if not date_str:
        return "Unknown"
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return "Unknown"
    return f"{dt.strftime('%B')} {dt.day}, {dt.strftime('%Y')}"


def active_bins(data):
    """Return [{'key': 'garbage', 'label': 'Garbage'}, ...] for bins collected this week,
    in a fixed, predictable order."""
    return [
        {"key": key, "label": BIN_LABELS[key], "badge_class": BIN_BADGE_CLASS[key]}
        for key in BIN_ORDER
        if data.get(key)
    ]


def _strip_leading_zero(time_str):
    return time_str[1:] if time_str.startswith("0") else time_str


def format_bus_times(timestamps, now=None, max_items=4):
    """
    Turn a list of unix timestamps into display-ready entries:
    [{"clock": "5:42 PM", "minutes": 6}, ...]

    - Filters out times that have already passed (with a small grace window
      for clock skew), instead of showing "-3 min" or similar nonsense.
    - Sorts ascending (soonest first).
    - Caps to max_items so the display/table doesn't overflow.
    """
    if now is None:
        now = datetime.now()
    now_ts = int(now.timestamp())

    upcoming = sorted(ts for ts in timestamps if ts >= now_ts - 60)
    entries = []
    for ts in upcoming[:max_items]:
        minutes = max(0, (ts - now_ts) // 60)
        clock = _strip_leading_zero(datetime.fromtimestamp(ts).strftime("%I:%M %p"))
        entries.append({"clock": clock, "minutes": minutes})
    return entries