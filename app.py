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
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import buddy
from flask import Flask, Response, abort, jsonify, request, send_from_directory
from markupsafe import escape

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")      # you invent this; paste same value in Meta dashboard
APP_SECRET = os.environ.get("APP_SECRET", "")          # Meta app secret (checks messages really come from Meta)
REPORT_KEY = os.environ.get("REPORT_KEY", "")          # you invent this; protects /report, /recheck, /videos
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")  # optional; used only for a second download attempt
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "your-email-not-set@example.com")  # shown on /privacy
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


GRAPH = "https://graph.instagram.com/v26.0"


def scrub(text):
    """Never let the access token appear in logs or reports."""
    text = str(text)
    return text.replace(IG_ACCESS_TOKEN, "***") if IG_ACCESS_TOKEN else text


def graph_lookup(media_id):
    """Official route: ask Meta's own API for this reel's media record.
    Tries several field lists, because asking for a field that isn't allowed
    makes the whole request fail."""
    if not IG_ACCESS_TOKEN:
        return [{"note": "IG_ACCESS_TOKEN not set in Render, so this lookup was skipped"}]
    field_sets = [
        "id,media_type,media_product_type,media_url,permalink,caption,timestamp,username,media_audio_type",
        "id,media_type,media_url,permalink,caption,timestamp",
        "id,permalink",
    ]
    attempts = []
    for fields in field_sets:
        try:
            r = requests.get(f"{GRAPH}/{media_id}",
                             params={"fields": fields, "access_token": IG_ACCESS_TOKEN}, timeout=30)
            try:
                body = r.json()
            except ValueError:
                body = {"raw": r.text[:500]}
        except Exception as e:
            attempts.append({"fields": fields, "error": scrub(repr(e))})
            continue
        attempts.append({"fields": fields, "status": r.status_code, "body": body})
        if r.status_code == 200:
            break
    return attempts


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
                    "sender_id": (m.get("sender") or {}).get("id"),
                    "downloads": [],
                    "rechecks": [],
                }
                if url:
                    fname = f"{stamp}-{i}-{att.get('type')}.mp4"
                    first = try_fetch(url, use_token=False, save_as=fname)
                    record["downloads"].append(first)
                    if (not first.get("looks_like_video") and IG_ACCESS_TOKEN
                            and urlparse(url).netloc != "www.instagram.com"):
                        record["downloads"].append(try_fetch(url, use_token=True, save_as=fname))
                reel_id = payload.get("reel_video_id")
                if att.get("type") == "ig_reel" and reel_id:
                    attempts = graph_lookup(reel_id)
                    record["graph_lookup"] = attempts
                    media_url = None
                    for a in attempts:
                        if a.get("status") == 200:
                            media_url = (a.get("body") or {}).get("media_url")
                    record["graph_media_url_present"] = bool(media_url)
                    if media_url:
                        record["graph_download"] = try_fetch(media_url, use_token=False,
                                                             save_as=f"{stamp}-{i}-graph.mp4")
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
    if os.environ.get("BUDDY_ENABLED") == "1":
        threading.Thread(target=buddy.process, args=(data,), daemon=True).start()
    return "ok", 200


@app.route("/privacy")
def privacy():
    email = escape(CONTACT_EMAIL)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy - noobody.bot test</title>
<style>body{{font-family:sans-serif;max-width:700px;margin:2rem auto;padding:0 1rem;line-height:1.6}}</style>
</head><body>
<h1>Privacy Policy</h1>
<p><strong>noobody.bot (private test)</strong></p>
<p>This is a small private test of an Instagram messaging tool. It is used only by a few invited test accounts.</p>
<h2>What we collect</h2>
<p>Messages sent to the Instagram account noobody.bot, including shared reel links, captions and media, and the Instagram ID of the account that sent them.</p>
<h2>How we use it</h2>
<p>Only to test whether shared content can be received and processed. It is not sold and not used for advertising. To write replies, message text and reel captions are sent to an AI provider (Google Gemini or Anthropic), which may process them under its own terms.</p>
<h2>Storage and deletion</h2>
<p>Reels you share (the link, the caption and any note you give about the reel, but never your name) may be reviewed by a person and may be added to the bot\'s library for other people; because they are not tied to you, saying \'forget me\' cannot remove them. To let the bot remember you, your recent messages, interests and simple facts you tell it are stored in a hosted database. Say \'forget me\' to the bot, or email us at the address below, and we delete them. Everything is deleted when the test ends.</p>
<h2>Contact</h2>
<p>{email}</p>
</body></html>"""


@app.route("/send")
def send_test():
    """Send a message from the bot to someone who messaged it in the last 24 hours.
    text= is an optional sentence. link= is an optional reel link, sent as its own
    separate message so Instagram shows a clean preview card with no blue text.
    If both are given, the sentence goes first, then the link."""
    check_key()
    to = request.args.get("to", "")
    text = request.args.get("text", "")
    link = request.args.get("link", "")
    if not IG_ACCESS_TOKEN:
        return jsonify({"error": "IG_ACCESS_TOKEN is not set in Render"}), 400
    if not to or not (text or link):
        return jsonify({"error": "need ?to=<sender_id> and text= and/or link="}), 400

    def post_message(msg):
        r = requests.post(f"{GRAPH}/me/messages",
                          headers={"Authorization": f"Bearer {IG_ACCESS_TOKEN}"},
                          json={"recipient": {"id": to}, "message": {"text": msg[:900]}},
                          timeout=30)
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:500]}
        return {"status": r.status_code, "response": body}

    results = []
    try:
        if text:
            results.append(post_message(text))
        if text and link:
            time.sleep(1.5)  # keep the order: sentence first, card second
        if link:
            results.append(post_message(link))
    except Exception as e:
        return jsonify({"error": scrub(repr(e)), "sent_so_far": results}), 500
    return jsonify({"sent": results})


@app.route("/tick")
def tick():
    """An outside timer (for example cron-job.org) opens this every ~10 minutes. It also keeps the
    free Render server awake. Sends the occasional message to people who wrote recently."""
    check_key()
    return jsonify({"nudged": buddy.send_nudges()})


@app.route("/submissions.csv")
def submissions_csv():
    """Same list as /submissions, as a CSV a Google Sheet can pull in with IMPORTDATA."""
    check_key()
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    cols = ["url", "category", "tags", "note", "summary", "status", "id", "caption"]
    w.writerow(cols)
    for r in buddy.export_rows():
        w.writerow([r[c] for c in cols])
    return Response(out.getvalue(), mimetype="text/csv")


@app.route("/submissions")
def submissions():
    """Reels users shared, with the AI's suggested category, waiting for a human to review."""
    check_key()
    return jsonify(buddy.load_submissions())


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
