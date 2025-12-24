import os
from datetime import datetime
from PIL import Image
from flask import Flask, request, redirect, url_for, send_from_directory, render_template_string, flash
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


PAGE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Image → 800x480 BMP</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 40px; }
      .card { max-width: 680px; padding: 18px; border: 1px solid #ddd; border-radius: 10px; }
      .msg { color: #b00; margin: 8px 0; }
      input[type=file] { margin: 10px 0; }
      button { padding: 10px 14px; cursor: pointer; }
      img { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 8px; margin-top: 12px; }
      .small { color: #555; font-size: 0.9em; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Convert image to BMP (800×480)</h2>

      {% with messages = get_flashed_messages() %}
        {% if messages %}
          {% for m in messages %}
            <div class="msg">{{ m }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <form method="POST" action="/upload" enctype="multipart/form-data">
        <input type="file" name="image" accept="image/*" required>
        <br>
        <button type="submit">Upload & Convert</button>
      </form>

      <p class="small">Saved in <code>gallery/</code> as a BMP resized/cropped to 800×480.</p>

      {% if filename %}
        <h3>Result</h3>
        <div><a href="{{ url_for('gallery_file', filename=filename) }}">Download/View BMP</a></div>
      {% endif %}
    </div>
  </body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE, filename=None)


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

    # Create output filename
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

    return render_template_string(PAGE, filename=out_name)


@app.get("/gallery/<path:filename>")
def gallery_file(filename):
    return send_from_directory(GALLERY_DIR, filename, as_attachment=False)


if __name__ == "__main__":
    # For LAN access on your Pi:
    # app.run(host="0.0.0.0", port=5000, debug=True)
    app.run(host="127.0.0.1", port=5000, debug=True)
