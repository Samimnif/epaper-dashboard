# What changed

## The bug you asked about
`display-data.json` was being read and written like this in the old code:

```python
with open('./display-data.json', 'r') as file:
    data = json.load(file)
with open('./display-data.json', 'w') as file:
    ...
    json.dump(data, file, indent=4)
```

Two problems:

1. `open(..., 'w')` truncates the file to zero bytes **before** `json.dump`
   writes anything. Kill the process (crash, pm2 restart, power blip) between
   those two lines and you're left with an empty file.
2. `garbage_collection.py`, `octranspo_gtfs.py`, and the Flask app were all
   separate processes doing this read-modify-write on the *same* file with no
   coordination, so two of them running close together could clobber each
   other or read a half-written file.

**Fix:** `data_store.py` is a new shared module. All reads/writes go through
`read_data()` / `update_data(mutate_fn)`, which:
- write to a temp file and atomically `os.replace()` it into place (so a
  reader always sees a fully-old or fully-new file, never a partial one),
- take a cross-process file lock (`filelock`) around the whole
  read-modify-write cycle, so concurrent updaters can't race each other,
- auto-recover with sane defaults if the file is ever missing or corrupt
  instead of crashing.

## Other bugs fixed along the way
- **`threading.Timer(30, update_json).start()` only fires once.** `Timer` is
  a one-shot alarm, not a recurring scheduler — your bus data was likely not
  actually refreshing every 30 seconds. `main.py` now uses a proper repeating
  background thread.
- **`display_show.py` swapped bus routes 70 and 73** when copying data in
  (`self.bus["70"] = data["73"]` and vice versa). Fixed so each route maps to
  itself.
- **`garbage_collection.py` and `octranspo_gtfs.py` ran their update logic at
  import time**, at module scope. Importing them (as `main.py` used to do
  with `from octranspo_gtfs import *`) triggered a network call as a side
  effect of importing. They now expose `get_garbage()` / `update_json()` as
  plain functions and only run automatically when executed directly
  (`python octranspo_gtfs.py`).

## Architecture change: one process instead of two
Previously pm2 ran two separate apps: `main.py` (display loop) and
`access_page.py` (Flask upload UI), with `garbage_collection.py` and
`octranspo_gtfs.py` run some other way. That's several independent things
touching the same JSON file and the same e-paper hardware with no
coordination.

Now there's **one** `main.py`: a single Flask app that serves the dashboard
(gallery + live bus times + garbage status) *and* runs the bus updater,
garbage updater, and e-paper display loop as background threads in the same
process. Benefits:
- Only one thing ever talks to the e-paper's SPI bus — no possibility of two
  processes fighting over hardware.
- pm2 only needs to manage one process.
- `display-data.json` is still the persistence layer (so state survives a
  restart), but it's no longer the *only* thing coordinating the pieces —
  the lock in `data_store.py` handles that.

`access_page.py` is no longer needed — its routes and logic are folded into
`main.py`. You can remove it from pm2.

## Migrating your pm2 setup

```bash
pm2 delete main        # or whatever your two old process names are
pm2 delete access_page

pm2 start main.py --name epaper-dashboard --interpreter python3
pm2 save
```

Set `FLASK_SECRET_KEY` in your `.env` if you want something other than the
default dev key (not critical for a LAN-only dashboard, but easy to do).

## Files
- `data_store.py` — shared atomic/locked JSON access (new)
- `main.py` — combined Flask app + schedulers + display loop (replaces the
  old `main.py` + `access_page.py`)
- `garbage_collection.py`, `octranspo_gtfs.py` — same logic, refactored to
  use `data_store` and to not run on import
- `display_show.py` — same rendering logic, reads via `data_store`, with the
  70/73 swap fixed
- `epd7in3f.py`, `epdconfig.py` — unchanged, copy these back in from your
  project (not modified here)
- `requirements.txt` — Python dependencies

Copy your existing `Font.ttc`, `bus_icons/`, `gallery/`, `GTFSExport/`,
`.env`, `epd7in3f.py`, and `epdconfig.py` into this folder before running.