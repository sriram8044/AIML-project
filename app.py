
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import os, time
from werkzeug.utils import secure_filename
from utils import process_pipeline

app = Flask(__name__)
app.secret_key = "devkey"
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    if "image" not in request.files:
        flash("No file uploaded.")
        return redirect(url_for("index"))
    file = request.files["image"]
    if file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ts = str(int(time.time()))
        input_path = os.path.join(UPLOAD_FOLDER, f"{ts}_{filename}")
        file.save(input_path)
        job_dir = os.path.join(OUTPUT_FOLDER, f"job_{ts}")
        lang = (request.form.get("lang","eng") or "eng").strip().lower() or "eng"
        result = process_pipeline(input_path, job_dir, lang=lang)
        return render_template("index.html",
                               original_path=input_path,
                               enhanced_color=result["enhanced_color"],
                               ocr_path=result["ocr_path"],
                               extracted_text=result["text"],
                               pdf_path=result["pdf_path"],
                               text_path=result["text_path"])
    else:
        flash("Unsupported file type.")
        return redirect(url_for("index"))

@app.route("/<path:filename>")
def serve_file(filename):
    if not os.path.exists(filename):
        return "Not found", 404
    directory = os.path.dirname(filename)
    name = os.path.basename(filename)
    return send_from_directory(directory or ".", name, as_attachment=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
