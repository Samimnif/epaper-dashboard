#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from datetime import datetime
from PIL import Image
from flask import (
    Flask, request, redirect, url_for,
    send_from_directory, render_template_string,
    flash
)
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
GALLERY_DIR = os.path.join(APP_DIR, "gallery")
os.makedirs(GALLERY_DIR, exist_ok=True)

TARGET_SIZE = (800, 480)
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}

app = Flask(__name__)
app.secret_key = "change-me"  # needed for flash messages


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def convert_to_800x480_bmp(img: Image.Image) -> Image.Image:
    """Resize preserving aspect ratio then center-crop to 800x480."""
    img = img.convert("RGB")
    img_ratio = img.width / img.height
    target_ratio = TARGET_SIZE[0] / TARGET_SIZE[1]

    if img_ratio > target_ratio:
        # too wide -> fit height
        new_h = TARGET_SIZE[1]
        new_w = int(new_h * img_ratio)
    else:
        # too tall -> fit width
        new_w = TARGET_SIZE[0]
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (img.width - TARGET_SIZE[0]) // 2
    top = (img.height - TARGET_SIZE[1]) // 2
    img = img.crop((left, top, left + TARGET_SIZE[0], top + TARGET_SIZE[1]))
    return img


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


PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Image → 800×480 BMP</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    .path { max-width: 520px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  </style>
</head>

<body class="bg-light">
<div class="container py-4">

  <div class="d-flex justify-content-between align-items-center mb-3">
    <h3 class="mb-0">Image → BMP (800×480)</h3>
    <span class="badge text-bg-secondary">Saves to <span class="mono">gallery/</span></span>
  </div>

  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for m in messages %}
        <div class="alert alert-warning py-2">{{ m }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <div class="card shadow-sm mb-4">
    <div class="card-body">
      <form method="POST" action="/upload" enctype="multipart/form-data" class="row g-3">
        <div class="col-md-8">
          <label class="form-label">Upload an image</label>
          <input class="form-control" type="file" name="image" accept="image/*" required>
          <div class="form-text">We resize + center-crop to 800×480, then save as BMP.</div>
        </div>
        <div class="col-md-4 d-flex align-items-end">
          <button class="btn btn-primary w-100" type="submit">Upload & Convert</button>
        </div>
      </form>

      {% if filename %}
        <hr>
        <div class="alert alert-success mb-0">
          Saved: <a class="mono" href="{{ url_for('gallery_file', filename=filename) }}">{{ filename }}</a>
        </div>
      {% endif %}
    </div>
  </div>

  <div class="card shadow-sm">
    <div class="card-header d-flex justify-content-between align-items-center">
      <div><strong>Gallery</strong> <span class="text-muted">({{ files|length }} files)</span></div>
      <a class="btn btn-outline-secondary btn-sm" href="/">Refresh</a>
    </div>

    <div class="table-responsive">
      <table class="table table-striped table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
          <th>Image</th>
            <th>File</th>
            <th style="width: 110px;">Size</th>
            <th style="width: 190px;">Modified</th>
            <th>Full Path</th>
            <th style="width: 180px;" class="text-end">Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for f in files %}
            <tr>
            <td><img src="./gallery/{{ f.name }}" style="height:70px"></td>
              <td class="path">
                <a class="mono" href="{{ f.url }}">{{ f.name }}</a>
              </td>
              <td class="mono">{{ f.size_kb }} KB</td>
              <td class="mono">{{ f.mtime }}</td>
              <td class="mono path" title="{{ f.full_path }}">{{ f.full_path }}</td>
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
    return render_template_string(PAGE, files=list_gallery_files(), filename=None)


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

    return render_template_string(PAGE, files=list_gallery_files(), filename=out_name)


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
    # For LAN access on your Pi:
    app.run(host="0.0.0.0", port=4000, debug=True)
    #app.run(host="127.0.0.1", port=5000, debug=True)
