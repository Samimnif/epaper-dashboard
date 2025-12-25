import os
import json
from datetime import datetime
from PIL import Image
from flask import Flask, request, redirect, url_for, send_from_directory, render_template_string, flash, abort
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
GALLERY_DIR = os.path.join(APP_DIR, "gallery")
os.makedirs(GALLERY_DIR, exist_ok=True)

ORDER_FILE = os.path.join(GALLERY_DIR, "gallery_order.json")

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
        new_h = TARGET_SIZE[1]
        new_w = int(new_h * img_ratio)
    else:
        new_w = TARGET_SIZE[0]
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (img.width - TARGET_SIZE[0]) // 2
    top = (img.height - TARGET_SIZE[1]) // 2
    img = img.crop((left, top, left + TARGET_SIZE[0], top + TARGET_SIZE[1]))
    return img


def _safe_gallery_path(filename: str) -> str:
    """Prevent path traversal: only allow files inside gallery dir."""
    filename = os.path.basename(filename)
    full = os.path.join(GALLERY_DIR, filename)
    # ensure inside gallery
    if os.path.commonpath([GALLERY_DIR, os.path.abspath(full)]) != os.path.abspath(GALLERY_DIR):
        raise ValueError("Invalid filename")
    return full


def load_order() -> list[str]:
    if not os.path.exists(ORDER_FILE):
        return []
    try:
        with open(ORDER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


def save_order(order: list[str]) -> None:
    with open(ORDER_FILE, "w", encoding="utf-8") as f:
        json.dump(order, f, indent=2)


def list_gallery_files() -> list[dict]:
    """Return ordered list of files in gallery with metadata."""
    # actual files in folder
    filenames = [
        f for f in os.listdir(GALLERY_DIR)
        if os.path.isfile(os.path.join(GALLERY_DIR, f))
        and f != os.path.basename(ORDER_FILE)
    ]

    order = load_order()

    # keep only those still present
    order = [f for f in order if f in filenames]

    # append new ones not in order
    for f in sorted(filenames):
        if f not in order:
            order.append(f)

    # persist normalized order
    save_order(order)

    files = []
    for idx, name in enumerate(order):
        full = os.path.join(GALLERY_DIR, name)
        st = os.stat(full)
        files.append({
            "idx": idx,
            "name": name,
            "full_path": os.path.abspath(full),
            "size_kb": round(st.st_size / 1024, 1),
            "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
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
      .truncate { max-width: 520px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
  </head>
  <body class="bg-light">
    <div class="container py-4">

      <div class="d-flex align-items-center justify-content-between mb-3">
        <h3 class="mb-0">Image → BMP (800×480)</h3>
        <span class="badge text-bg-secondary">Saves to <span class="mono">gallery/</span></span>
      </div>

      {% with messages = get_flashed_messages() %}
        {% if messages %}
          <div class="mb-3">
            {% for m in messages %}
              <div class="alert alert-warning py-2 mb-2">{{ m }}</div>
            {% endfor %}
          </div>
        {% endif %}
      {% endwith %}

      <div class="card shadow-sm mb-4">
        <div class="card-body">
          <form class="row g-3" method="POST" action="/upload" enctype="multipart/form-data">
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
          <div>
            <strong>Gallery</strong>
            <span class="text-muted">({{ files|length }} files)</span>
          </div>
          <a class="btn btn-outline-secondary btn-sm" href="/">Refresh</a>
        </div>

        <div class="table-responsive">
          <table class="table table-striped table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th style="width: 70px;">Order</th>
                <th>File</th>
                <th style="width: 110px;">Size</th>
                <th style="width: 190px;">Modified</th>
                <th>Full path</th>
                <th style="width: 190px;" class="text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {% for f in files %}
                <tr>
                  <td class="mono">{{ f.idx }}</td>

                  <td class="truncate">
                    <a class="mono" href="{{ f.url }}">{{ f.name }}</a>
                  </td>

                  <td class="mono">{{ f.size_kb }} KB</td>
                  <td class="mono">{{ f.mtime }}</td>

                  <td class="mono truncate" title="{{ f.full_path }}">{{ f.full_path }}</td>

                  <td class="text-end">
                    <div class="btn-group btn-group-sm" role="group">
                      <form method="POST" action="/move" class="d-inline">
                        <input type="hidden" name="filename" value="{{ f.name }}">
                        <input type="hidden" name="direction" value="up">
                        <button class="btn btn-outline-primary" {% if loop.first %}disabled{% endif %}>↑</button>
                      </form>

                      <form method="POST" action="/move" class="d-inline">
                        <input type="hidden" name="filename" value="{{ f.name }}">
                        <input type="hidden" name="direction" value="down">
                        <button class="btn btn-outline-primary" {% if loop.last %}disabled{% endif %}>↓</button>
                      </form>

                      <a class="btn btn-outline-success" href="{{ f.url }}">View</a>

                      <form method="POST" action="/delete" class="d-inline"
                            onsubmit="return confirm('Delete {{ f.name }}?');">
                        <input type="hidden" name="filename" value="{{ f.name }}">
                        <button class="btn btn-outline-danger">Delete</button>
                      </form>
                    </div>
                  </td>
                </tr>
              {% endfor %}
              {% if files|length == 0 %}
                <tr><td colspan="6" class="text-center text-muted py-4">No files yet.</td></tr>
              {% endif %}
            </tbody>
          </table>
        </div>
      </div>

      <div class="text-muted small mt-3">
        Tip: the order is saved in <span class="mono">gallery/gallery_order.json</span>
      </div>

    </div>
  </body>
</html>
"""


@app.get("/")
def index():
    files = list_gallery_files()
    return render_template_string(PAGE, filename=None, files=files)


@app.post("/upload")
def upload():
    if "image" not in request.files:
        flash("No file part named 'image'.")
        return redirect(url_for("index"))

    file = request.files["image"]
    if file.filename == "":
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

    # add to order at end
    order = load_order()
    if out_name not in order:
        order.append(out_name)
        save_order(order)

    files = list_gallery_files()
    return render_template_string(PAGE, filename=out_name, files=files)


@app.post("/delete")
def delete_file():
    filename = request.form.get("filename", "")
    if not filename:
        abort(400)

    try:
        full = _safe_gallery_path(filename)
    except ValueError:
        abort(400)

    if os.path.exists(full):
        os.remove(full)

    order = load_order()
    order = [f for f in order if f != os.path.basename(filename)]
    save_order(order)

    flash(f"Deleted {os.path.basename(filename)}")
    return redirect(url_for("index"))


@app.post("/move")
def move_file():
    filename = os.path.basename(request.form.get("filename", ""))
    direction = request.form.get("direction", "")

    order = load_order()
    if filename not in order:
        return redirect(url_for("index"))

    i = order.index(filename)
    if direction == "up" and i > 0:
        order[i], order[i - 1] = order[i - 1], order[i]
        save_order(order)
    elif direction == "down" and i < len(order) - 1:
        order[i], order[i + 1] = order[i + 1], order[i]
        save_order(order)

    return redirect(url_for("index"))


@app.get("/gallery/<path:filename>")
def gallery_file(filename):
    # Send only from gallery folder
    return send_from_directory(GALLERY_DIR, os.path.basename(filename), as_attachment=False)


if __name__ == "__main__":
    # For LAN access on your Pi:
    # app.run(host="0.0.0.0", port=5000, debug=True)
    app.run(host="127.0.0.1", port=5000, debug=True)
