#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single-process e-paper dashboard.

Architecture recap:
  - One Flask process serves the dashboard (gallery + live bus times +
    garbage status) AND runs the bus updater, garbage updater, and e-paper
    loop as background threads. Only one thing ever talks to the e-paper's
    SPI bus, and pm2 only has one process to manage.
  - display-data.json is the persistence layer; all reads/writes go through
    data_store.py (atomic writes + cross-process lock), so it survives
    crashes/restarts without corruption.
  - formatting.py has the shared logic for turning raw timestamps/date
    strings/booleans into human-readable text, used by both the web page
    and the e-paper renderer, so they always agree.

On refresh cadence / panel wear:
  - The web dashboard reads display-data.json fresh on every page load, so
    it's always as current as the last background data fetch (every 30s
    for buses). Slowing down the physical e-paper redraw does NOT make the
    web page stale - they're decoupled.
  - The e-paper panel itself is now throttled on purpose:
      * the bus/garbage view repaints every DAY_VIEW_REFRESH_INTERVAL
        (default 5 min) instead of every 70s,
      * gallery photos rotate every GALLERY_ROTATE_INTERVAL (default 1
        hour) instead of every 70s.
    Full-color e-paper refreshes are slow and do wear the panel over many
    thousands of cycles, so there's no reason to redraw the same bus ETA
    ballpark every 70 seconds. Tune the two constants below if you want it
    snappier or even more conservative.
"""

import os
import time
import threading
from datetime import datetime

from flask import (
    Flask, request, redirect, url_for,
    send_from_directory, render_template_string, flash
)
from werkzeug.utils import secure_filename
from PIL import Image

from data_store import read_data, last_updated
from formatting import format_collection_date, active_bins, format_bus_times
from garbage_collection import get_garbage
from octranspo_gtfs import update_json
from display_show import edisplay

APP_DIR = os.path.dirname(os.path.abspath(__file__))
GALLERY_DIR = os.path.join(APP_DIR, "gallery")
os.makedirs(GALLERY_DIR, exist_ok=True)

TARGET_SIZE = (800, 480)
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}

MORNING_START = 5   # 05:00, inclusive
MORNING_END = 14     # 14:00, exclusive - dashboard shows bus/garbage view in this window

# Background data fetch cadence (cheap: just an HTTP call + JSON write)
BUS_UPDATE_INTERVAL = 30          # seconds
GARBAGE_UPDATE_INTERVAL = 86400   # seconds (once a day)

# Physical e-paper redraw cadence (expensive: a real panel refresh).
# Decoupled from the data fetch above on purpose - see module docstring.
DAY_VIEW_REFRESH_INTERVAL = 300    # 5 minutes
GALLERY_ROTATE_INTERVAL = 3600     # 1 hour
LOOP_POLL_INTERVAL = 10            # how often we just *check* if it's time to redraw

BUS_ROUTES = ["99", "70", "74", "73", "110", "198", "299", "283"]

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me")

display = edisplay()
_gallery_index = 0
_gallery_index_lock = threading.Lock()
stop_event = threading.Event()


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

def _repeat(interval, func, name):
    """Run func() once immediately, then every `interval` seconds, until stop_event fires.

    This replaces the old `threading.Timer(30, update_json).start()` pattern,
    which only ever fired ONCE - Timer is a one-shot alarm, not a recurring
    scheduler.
    """
    def worker():
        while not stop_event.is_set():
            try:
                func()
            except Exception as e:
                print(f"[{name}] error: {e}")
            stop_event.wait(interval)

    t = threading.Thread(target=worker, name=name, daemon=True)
    t.start()
    return t


def _display_loop():
    """Decides WHAT to show and WHEN to actually push a new frame to the panel.

    Data keeps refreshing in the background every 30s regardless (cheap),
    but the physical redraw only happens on the slower cadence below to
    reduce wear on the e-paper panel.
    """
    global _gallery_index
    last_day_refresh = 0.0
    last_gallery_rotate = 0.0

    while not stop_event.is_set():
        now_ts = time.time()
        hour = datetime.now().hour

        try:
            if MORNING_START <= hour < MORNING_END:
                if now_ts - last_day_refresh >= DAY_VIEW_REFRESH_INTERVAL:
                    display.day_disp()
                    last_day_refresh = now_ts
            else:
                if now_ts - last_gallery_rotate >= GALLERY_ROTATE_INTERVAL:
                    files = [
                        os.path.join(GALLERY_DIR, f)
                        for f in sorted(os.listdir(GALLERY_DIR))
                        if os.path.isfile(os.path.join(GALLERY_DIR, f))
                    ]
                    if files:
                        with _gallery_index_lock:
                            if _gallery_index >= len(files):
                                _gallery_index = 0
                            path = files[_gallery_index]
                            _gallery_index += 1
                        display.gallery_disp_img(path)
                    last_gallery_rotate = now_ts
        except Exception as e:
            print(f"[display-loop] error: {e}")

        stop_event.wait(LOOP_POLL_INTERVAL)


def start_background_workers():
    _repeat(BUS_UPDATE_INTERVAL, update_json, "bus-updater")
    _repeat(GARBAGE_UPDATE_INTERVAL, get_garbage, "garbage-updater")
    threading.Thread(target=_display_loop, name="display-loop", daemon=True).start()


# ---------------------------------------------------------------------------
# Image handling (from the old access_page.py)
# ---------------------------------------------------------------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def convert_to_800x480_bmp(img: Image.Image) -> Image.Image:
    """Resize preserving aspect ratio then center-crop to 800x480."""
    img = img.convert("RGB")
    img_ratio = img.width / img.height
    target_ratio = TARGET_SIZE[0] / TARGET_SIZE[1]

    if img_ratio > target_ratio:
        new_h = TARGET_SIZE[1]
        new_w = int(new_h * img_ratio)
    else:
        new_w = TARGET_SIZE[0]
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (img.width - TARGET_SIZE[0]) // 2
    top = (img.height - TARGET_SIZE[1]) // 2
    return img.crop((left, top, left + TARGET_SIZE[0], top + TARGET_SIZE[1]))


def list_gallery_files():
    files = []
    for name in sorted(os.listdir(GALLERY_DIR)):
        full = os.path.join(GALLERY_DIR, name)
        if not os.path.isfile(full):
            continue
        st = os.stat(full)
        files.append({
            "name": name,
            "full_path": os.path.abspath(full),
            "size_kb": round(st.st_size / 1024, 1),
            "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "url": url_for("gallery_file", filename=name),
        })
    return files


# ---------------------------------------------------------------------------
# Dashboard template - gallery upload/manage + live bus & garbage status
# ---------------------------------------------------------------------------

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>E-Paper Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    .path { max-width: 420px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .bus-time { display: inline-block; margin: 2px 6px 2px 0; }
  </style>
</head>

<body class="bg-light">
<div class="container py-4">

  <div class="d-flex justify-content-between align-items-center mb-3">
    <h3 class="mb-0">E-Paper Dashboard</h3>
    <a class="btn btn-outline-secondary btn-sm" href="/">Refresh</a>
  </div>

  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for m in messages %}
        <div class="alert alert-warning py-2">{{ m }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  {% if data_updated %}
    <p class="text-muted small mb-3">Data last refreshed: {{ data_updated }}</p>
  {% endif %}

  <div class="row g-3 mb-4">
    <div class="col-md-6">
      <div class="card shadow-sm h-100">
        <div class="card-header"><strong>Garbage / Recycling</strong></div>
        <div class="card-body">
          <p class="mb-2">Collection date: <strong>{{ collection_date }}</strong></p>
          {% if bins_this_week %}
            {% for b in bins_this_week %}
              <span class="badge {{ b.badge_class }} me-1">{{ b.label }}</span>
            {% endfor %}
          {% else %}
            <p class="text-muted mb-0">No collection scheduled this week.</p>
          {% endif %}
        </div>
      </div>
    </div>

    <div class="col-md-6">
      <div class="card shadow-sm h-100">
        <div class="card-header"><strong>Next Buses</strong></div>
        <div class="card-body">
          <table class="table table-sm mb-0">
            <thead><tr><th>Route</th><th>Next arrivals</th></tr></thead>
            <tbody>
              {% for route, entries in bus_rows.items() %}
                <tr>
                  <td class="mono">{{ route }}</td>
                  <td>
                    {% if entries %}
                      {% for e in entries %}
                        <span class="badge text-bg-light border bus-time">
                          {{ e.clock }} <span class="text-muted">({{ e.minutes }} min)</span>
                        </span>
                      {% endfor %}
                    {% else %}
                      <span class="text-muted">No upcoming times</span>
                    {% endif %}
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <div class="card shadow-sm mb-4">
    <div class="card-body">
      <form method="POST" action="/upload" enctype="multipart/form-data" class="row g-3">
        <div class="col-md-8">
          <label class="form-label">Upload an image for the gallery rotation</label>
          <input class="form-control" type="file" name="image" accept="image/*" required>
          <div class="form-text">We resize + center-crop to 800×480, then save as BMP.</div>
        </div>
        <div class="col-md-4 d-flex align-items-end">
          <button class="btn btn-primary w-100" type="submit">Upload & Convert</button>
        </div>
      </form>
    </div>
  </div>

  <div class="card shadow-sm">
    <div class="card-header d-flex justify-content-between align-items-center">
      <div><strong>Gallery</strong> <span class="text-muted">({{ files|length }} files)</span></div>
    </div>

    <div class="table-responsive">
      <table class="table table-striped table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th>Image</th>
            <th>File</th>
            <th style="width: 110px;">Size</th>
            <th style="width: 190px;">Modified</th>
            <th style="width: 180px;" class="text-end">Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for f in files %}
            <tr>
              <td><img src="{{ f.url }}" style="height:70px"></td>
              <td class="path"><a class="mono" href="{{ f.url }}">{{ f.name }}</a></td>
              <td class="mono">{{ f.size_kb }} KB</td>
              <td class="mono">{{ f.mtime }}</td>
              <td class="text-end">
                <a class="btn btn-sm btn-outline-success" href="{{ f.url }}">View</a>
                <form method="POST" action="/delete" class="d-inline"
                      onsubmit="return confirm('Delete {{ f.name }}?');">
                  <input type="hidden" name="filename" value="{{ f.name }}">
                  <button class="btn btn-sm btn-outline-danger">Delete</button>
                </form>
              </td>
            </tr>
          {% endfor %}
          {% if files|length == 0 %}
            <tr><td colspan="5" class="text-center text-muted py-4">No files yet.</td></tr>
          {% endif %}
        </tbody>
      </table>
    </div>
  </div>

</div>
</body>
</html>
"""


@app.get("/")
def index():
    data = read_data()
    updated = last_updated()
    return render_template_string(
        PAGE,
        files=list_gallery_files(),
        collection_date=format_collection_date(data.get("date")),
        bins_this_week=active_bins(data),
        bus_rows={route: format_bus_times(data.get(route, [])) for route in BUS_ROUTES},
        data_updated=updated.strftime("%Y-%m-%d %H:%M:%S") if updated else None,
    )


@app.post("/upload")
def upload():
    file = request.files.get("image")
    if not file or file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Unsupported file type.")
        return redirect(url_for("index"))

    safe = secure_filename(file.filename)
    base = os.path.splitext(safe)[0]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"{base}_{stamp}_800x480.bmp"
    out_path = os.path.join(GALLERY_DIR, out_name)

    try:
        img = Image.open(file.stream)
        bmp = convert_to_800x480_bmp(img)
        bmp.save(out_path, format="BMP")
    except Exception as e:
        flash(f"Conversion failed: {e}")
        return redirect(url_for("index"))

    flash(f"Saved {out_name}")
    return redirect(url_for("index"))


@app.post("/delete")
def delete_file():
    name = os.path.basename(request.form.get("filename", ""))
    if not name:
        return redirect(url_for("index"))

    path = os.path.join(GALLERY_DIR, name)
    if os.path.isfile(path):
        os.remove(path)
        flash(f"Deleted {name}")
    else:
        flash("File not found.")

    return redirect(url_for("index"))


@app.get("/gallery/<path:filename>")
def gallery_file(filename):
    return send_from_directory(GALLERY_DIR, os.path.basename(filename), as_attachment=False)


if __name__ == "__main__":
    start_background_workers()
    # debug=False and use_reloader=False are important here: Flask's reloader
    # spawns a SECOND process, which would mean two processes fighting over
    # the same SPI/e-paper hardware and background threads running twice.
    app.run(host="0.0.0.0", port=4000, debug=False, use_reloader=False)