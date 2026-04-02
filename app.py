import os
import uuid
import json
import requests
from flask import Flask, render_template, request, jsonify, url_for, abort
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()  # loads .env file automatically

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY — check your .env file")

BUCKET_FILES  = "docshare-files"
BUCKET_THUMBS = "docshare-thumbs"
ALLOWED_FILE_EXT  = {"pdf", "ppt", "pptx"}
ALLOWED_THUMB_EXT = {"jpg", "jpeg", "png", "webp", "gif"}

# ── Supabase REST helpers ─────────────────────────────────────────────
def _h(ct="application/json"):
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": ct,
    }

def db_select(table, filters=None, order=None):
    params = {"select": "*"}
    if order:   params["order"] = order
    if filters:
        for col, val in filters.items():
            params[col] = f"eq.{val}"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                     headers={**_h(), "Prefer": "return=representation"}, params=params)
    r.raise_for_status()
    return r.json()

def db_select_one(table, row_id):
    params = {"select": "*", "id": f"eq.{row_id}"}
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                     headers={**_h(), "Prefer": "return=representation"}, params=params)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None

def db_insert(table, row):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}",
                      headers={**_h(), "Prefer": "return=representation"},
                      data=json.dumps(row))
    r.raise_for_status()
    return r.json()

def db_update(table, row_id, data):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}",
                       headers={**_h(), "Prefer": "return=representation"},
                       params={"id": f"eq.{row_id}"},
                       data=json.dumps(data))
    r.raise_for_status()
    return r.json()

def db_delete(table, row_id):
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}",
                        headers=_h(), params={"id": f"eq.{row_id}"})
    r.raise_for_status()

def storage_upload(bucket, file_bytes, filename, content_type):
    unique_name = f"{uuid.uuid4()}_{secure_filename(filename)}"
    r = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{bucket}/{unique_name}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": content_type},
        data=file_bytes,
    )
    r.raise_for_status()
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{unique_name}", unique_name

def storage_delete(bucket, path):
    requests.delete(
        f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )

def allowed_file(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

def get_ct(filename):
    return {
        "pdf": "application/pdf", "ppt": "application/vnd.ms-powerpoint",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp", "gif": "image/gif",
    }.get(filename.rsplit(".", 1)[-1].lower(), "application/octet-stream")

def storage_path_from_url(url):
    """Extract just the filename part after the bucket name."""
    try:
        return url.split("/public/")[1].split("/", 1)[1]
    except Exception:
        return None

# ════════════════════════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════════════════════════

# ── READ: Homepage ───────────────────────────────────────────────────
@app.route("/")
def index():
    files = db_select("files", order="uploaded_at.desc")
    users = {}
    for f in files:
        users.setdefault(f["username"], []).append(f)
    return render_template("index.html", users=users)

# ── READ: User page ──────────────────────────────────────────────────
@app.route("/user/<username>")
def user_page(username):
    files = db_select("files", filters={"username": username.lower()}, order="uploaded_at.desc")
    if not files:
        return render_template("404.html", username=username), 404
    return render_template("user.html", username=username, files=files)

# ── READ: Single file detail ─────────────────────────────────────────
@app.route("/file/<file_id>")
def file_detail(file_id):
    f = db_select_one("files", file_id)
    if not f:
        abort(404)
    return render_template("file_detail.html", f=f)

# ── CREATE: Upload ───────────────────────────────────────────────────
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    username   = request.form.get("username", "").strip().lower()
    title      = request.form.get("title", "").strip()
    doc_file   = request.files.get("document")
    thumb_file = request.files.get("thumbnail")

    errors = []
    if not username: errors.append("Username is required.")
    if not title:    errors.append("Title is required.")
    if not doc_file or not doc_file.filename:
        errors.append("A PDF or PPT file is required.")
    elif not allowed_file(doc_file.filename, ALLOWED_FILE_EXT):
        errors.append("Only PDF, PPT, PPTX allowed.")
    if thumb_file and thumb_file.filename:
        if not allowed_file(thumb_file.filename, ALLOWED_THUMB_EXT):
            errors.append("Thumbnail must be JPG, PNG, WEBP, or GIF.")
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    try:
        doc_url, doc_path = storage_upload(BUCKET_FILES, doc_file.read(),
                                           doc_file.filename, get_ct(doc_file.filename))
        thumb_url, thumb_path = None, None
        if thumb_file and thumb_file.filename:
            thumb_url, thumb_path = storage_upload(BUCKET_THUMBS, thumb_file.read(),
                                                   thumb_file.filename, get_ct(thumb_file.filename))
        db_insert("files", {
            "username":    username,
            "title":       title,
            "file_url":    doc_url,
            "file_path":   doc_path,
            "thumb_url":   thumb_url,
            "thumb_path":  thumb_path,
            "file_type":   doc_file.filename.rsplit(".", 1)[-1].lower(),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })
    except requests.HTTPError as e:
        return jsonify({"ok": False, "errors": [f"Upload failed: {e.response.text}"]}), 500

    return jsonify({"ok": True, "redirect": url_for("index")})

# ── UPDATE: Edit title ───────────────────────────────────────────────
@app.route("/file/<file_id>/edit", methods=["GET", "POST"])
def edit_file(file_id):
    f = db_select_one("files", file_id)
    if not f:
        abort(404)

    if request.method == "GET":
        return render_template("edit.html", f=f)

    # PATCH
    new_title = request.form.get("title", "").strip()
    new_thumb  = request.files.get("thumbnail")

    errors = []
    if not new_title: errors.append("Title cannot be empty.")
    if new_thumb and new_thumb.filename:
        if not allowed_file(new_thumb.filename, ALLOWED_THUMB_EXT):
            errors.append("Thumbnail must be JPG, PNG, WEBP, or GIF.")
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    try:
        update_data = {"title": new_title}
        if new_thumb and new_thumb.filename:
            # Delete old thumb if exists
            if f.get("thumb_path"):
                storage_delete(BUCKET_THUMBS, f["thumb_path"])
            thumb_url, thumb_path = storage_upload(BUCKET_THUMBS, new_thumb.read(),
                                                   new_thumb.filename, get_ct(new_thumb.filename))
            update_data["thumb_url"]  = thumb_url
            update_data["thumb_path"] = thumb_path
        db_update("files", file_id, update_data)
    except requests.HTTPError as e:
        return jsonify({"ok": False, "errors": [f"Update failed: {e.response.text}"]}), 500

    return jsonify({"ok": True, "redirect": url_for("user_page", username=f["username"])})

# ── DELETE: Remove file ──────────────────────────────────────────────
@app.route("/file/<file_id>/delete", methods=["POST"])
def delete_file(file_id):
    f = db_select_one("files", file_id)
    if not f:
        return jsonify({"ok": False, "error": "Not found"}), 404
    try:
        if f.get("file_path"):
            storage_delete(BUCKET_FILES,  f["file_path"])
        if f.get("thumb_path"):
            storage_delete(BUCKET_THUMBS, f["thumb_path"])
        db_delete("files", file_id)
    except requests.HTTPError as e:
        return jsonify({"ok": False, "error": e.response.text}), 500

    return jsonify({"ok": True, "redirect": url_for("index")})

# ── API: JSON endpoints (bonus) ──────────────────────────────────────
@app.route("/api/files")
def api_files():
    files = db_select("files", order="uploaded_at.desc")
    return jsonify(files)

@app.route("/api/files/<file_id>")
def api_file(file_id):
    f = db_select_one("files", file_id)
    return jsonify(f) if f else (jsonify({"error": "not found"}), 404)

if __name__ == "__main__":
    app.run(debug=True, port=5000)