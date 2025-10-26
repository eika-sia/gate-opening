import os
import time
import re
import json
from hashlib import sha256
from flask import Flask, render_template, request, jsonify
from serialio import SerialIO

app = Flask(__name__)

# Hard-coded password hash (SHA-256 of the secret)
# Example secret used here: "s3cr3t"
EXPECTED_HASH = "4e738ca5563c06cfd0018299933d58db1dd8bf97f6973dc99bf6cdc64b5550bd"

# device path (override with FLIPPER_DEVICE env if you want)
DEVICE = os.environ.get(
    "FLIPPER_DEVICE",
    "/dev/serial/by-id/usb-Flipper_Devices_Inc._Flipper_Jamalaki_flip_Jamalaki-if00"
)

# Global flipper instance (created at startup below)
flipper = None

@app.route("/")
def index():
    # Provide a tiny status to show whether flipper connected
    connected = flipper is not None
    return render_template("index.html", connected=connected, device=DEVICE)

@app.route("/send", methods=["POST"])
def send_command():
    """
    Expects JSON:
      { "hash": "<hex sha256>" }

    If hash matches EXPECTED_HASH, sends "hello_world" and returns device response (or error).
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Expected JSON"}), 400

    data = request.get_json()
    pw_hash = data.get("hash", "")
    if not isinstance(pw_hash, str) or len(pw_hash) != 64:
        return jsonify({"ok": False, "error": "Bad hash format"}), 400

    if pw_hash != EXPECTED_HASH:
        # failed auth
        return jsonify({"ok": False, "error": "Authentication failed"}), 403

    if flipper is None:
        return jsonify({"ok": False, "error": "Flipper not connected"}), 500

    try:
        # send hello_world and wait for response (1.5s)
        resp = flipper.send_and_wait("hello_world", wait=1.5)
        # decode for JSON; safe fallback
        text = resp.decode(errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
        return jsonify({"ok": True, "response": text})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Send failed: {e}"}), 500

@app.route("/status", methods=["GET"])
def status():
    connected = flipper is not None
    return jsonify({"connected": connected, "device": DEVICE})

# -------------------------
# Helper: try to start flipper (called at startup)
# -------------------------
def start_flipper():
    global flipper
    if flipper is not None:
        return
    try:
        flipper = SerialIO(DEVICE, baud=115200, line_ending=b"\r", timeout=0.7)
        # read initial banner if any
        # small sleep to let device send its banner
        time.sleep(0.2)
        banner = flipper.recv(timeout=1.0)
        print("[Flipper connected]", DEVICE)
        if banner:
            print(banner.decode(errors="replace"))
    except Exception as e:
        print("[Flipper not available]", DEVICE, e)
        flipper = None

# -------------------------
# Start app and flipper instance
# -------------------------
if __name__ == "__main__":
    # Avoid double-creating serial connection due to the reloader. If you want the reloader,
    # either run with FLASK_DEBUG=0 or let WERKZEUG_RUN_MAIN env logic handle it.
    # We'll only start the flipper when the process is the 'main' worker.
    # Werkzeug sets WERKZEUG_RUN_MAIN when reloader forks child; we want to create only once.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("FLASK_DEBUG") is None:
        start_flipper()
    else:
        # If running under plain `python app.py`, we start the flipper too
        start_flipper()

    # Run Flask. Use debug=False to avoid auto-reload creating multiple serial connections,
    # or accept the WERKZEUG_RUN_MAIN guard above.
    app.run(host="0.0.0.0", port=5000, debug=False)
