"""
Reel-share test server.

Purpose: find out what Instagram's messaging API sends your bot when someone
shares a reel, and whether the link in that message downloads as a real video.

It does NOT summarize anything. It only logs and tests.
"""
import hashlib
import hmac
import json
import os
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from flask import Flask, abort, jsonify, request, send_from_directory

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")      # you invent this; paste same value in Meta dashboard
APP_SECRET = os.environ.get("APP_SECRET", "")          # Meta app secret (checks messages really come from Meta)
REPORT_KEY = os.environ.get("REPORT_KEY", "")          # you invent this; protects /report, /recheck, /videos
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")  # optional; used only for a second download attempt
DATA_DIR = os.environ.get("DATA_DIR", "data")
MAX_VIDEO_BYTES = 100 * 1024 * 1024

VIDEO_DIR = os.path.join(DATA_DIR, "videos")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
os.makedirs(VIDEO_DIR, exist_ok=True)
lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def load_results():
    try:
        with open(RESULTS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_results(results):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def try_fetch(url, use_token, save_as=None):
    """Download test. Returns a dict describing exactly what came back."""
    headers = {"User-Agent": "Mozilla/5.0 (reel-test)"}
    if use_token and IG_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {IG_ACCESS_TOKEN}"
    info = {"time": now(), "with_token": use_token}
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=30)
        info["status"] = r.status_code
        info["content_type"] = r.headers.get("Content-Type")
        info["content_length_header"] = r.headers.get("Content-Length")
        info["served_from"] = urlparse(r.url).netloc
        chunks = r.iter_content(chunk_size=65536)
        first = next(chunks, b"")
        ctype = (info["content_type"] or "").lower()
        is_video = ctype.startswith("video/") or first[4:8] == b"ftyp"
        info["looks_like_video"] = bool(is_video)
        info["first_bytes_hex"] = first[:16].hex()
        if r.status_code == 200 and is_video and save_as:
            path = os.path.join(VIDEO_DIR, save_as)
            size = 0
            with open(path, "wb") as f:
                f.write(first)
                size += len(first)
                for chunk in chunks:
                    size += len(chunk)
                    if size > MAX_VIDEO_BYTES:
                        info["note"] = "stopped at size limit"
                        break
                    f.write(chunk)
            info["saved_file"] = save_as
            info["saved_bytes"] = size
        r.close()
    except Exception as e:  # network errors, timeouts, etc.
        info["error"] = repr(e)
    return info


def process_payload(data):
    for entry in data.get("entry", []):
        for m in entry.get("messaging", []):
            message = m.get("message", {})
            for i, att in enumerate(message.get("attachments", []) or []):
                payload = att.get("payload", {}) or {}
                url = payload.get("url")
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                record = {
                    "received": now(),
                    "attachment_type": att.get("type"),
                    "attachment_payload": payload,
                    "message_mid": message.get("mid"),
                    "downloads": [],
                    "rechecks": [],
                }
                if url:
                    fname = f"{stamp}-{i}-{att.get('type')}.mp4"
                    first = try_fetch(url, use_token=False, save_as=fname)
                    record["downloads"].append(first)
                    if not first.get("looks_like_video") and IG_ACCESS_TOKEN:
                        record["downloads"].append(try_fetch(url, use_token=True, save_as=fname))
                with lock:
                    results = load_results()
                    results.append(record)
                    save_results(results)
                print("RESULT:", json.dumps(record, indent=2), flush=True)


def check_key():
    if not REPORT_KEY or request.args.get("key") != REPORT_KEY:
        abort(403)


@app.route("/")
def home():
    return "Reel test server is running."


@app.route("/webhook", methods=["GET"])
def verify():
    # Meta calls this once when you save the webhook in the dashboard.
    if request.args.get("hub.mode") == "subscribe" and VERIFY_TOKEN and \
            request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge", ""), 200
    abort(403)


@app.route("/webhook", methods=["POST"])
def receive():
    raw = request.get_data()
    if APP_SECRET:
        sent = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sent, expected):
            abort(403)
    else:
        print("WARNING: APP_SECRET not set, signature not checked", flush=True)
    data = request.get_json(silent=True) or {}
    print("RAW PAYLOAD:", json.dumps(data, indent=2), flush=True)
    # Reply fast so Meta doesn't retry; do the download test in the background.
    threading.Thread(target=process_payload, args=(data,), daemon=True).start()
    return "ok", 200


@app.route("/report")
def report():
    check_key()
    return jsonify(load_results())


@app.route("/recheck")
def recheck():
    """Open this at ~1 hour and ~24 hours later to see if old links still work."""
    check_key()
    with lock:
        results = load_results()
        for rec in results:
            url = (rec.get("attachment_payload") or {}).get("url")
            if url:
                rec.setdefault("rechecks", []).append(try_fetch(url, use_token=False))
        save_results(results)
    return jsonify(results)


@app.route("/videos/<name>")
def videos(name):
    check_key()
    return send_from_directory(VIDEO_DIR, name)
