import os
import time
from flask import Flask, render_template, request, jsonify
from serialio import SerialIO

app = Flask(__name__)

EXPECTED_PW = os.environ.get("FLIPPER_PW")

DEVICE = os.environ.get(
    "FLIPPER_DEVICE",
    "/dev/serial/by-id/usb-Flipper_Devices_Inc._Flipper_Jamalaki_flip_Jamalaki-if00"
)

PROJ_NAME = os.environ.get(
    "PROJ_NAME",
    ""
)

COMMAND = os.environ.get(
    "FLIPPER_CMD",
    "hello_world"
)

# Global flipper instance (created at startup below)
flipper = None

@app.route(f"/{PROJ_NAME}/")
def index():
    # Provide a tiny status to show whether flipper connected
    connected = status().get_json()['connected']
    return render_template("index.html", connected=connected, device=DEVICE)

@app.route(f"/{PROJ_NAME}/send", methods=["POST"])
def send_command():
    """
    Expects JSON:
      { "pw": "pw string" }
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Expected JSON"}), 400

    data = request.get_json()
    pw = data.get("pw", "")
    if not isinstance(pw, str):
        return jsonify({"ok": False, "error": "Bad password format"}), 400

    if pw != EXPECTED_PW:
        # failed auth
        return jsonify({"ok": False, "error": "Authentication failed"}), 403

    if status().get_json()['connected'] is False:
        return jsonify({"ok": False, "error": "Flipper not connected"}), 500
    
    if flipper is None:
        return jsonify({"ok": False, "error": "Internal flipper error"})

    try:
        # send a chosen command
        resp = flipper.send_and_wait(COMMAND, wait=3)
        # decode for JSON; safe fallback
        text = resp.decode(errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
        return jsonify({"ok": True, "response": text})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Send failed: {e}"}), 500

@app.route(f"/{PROJ_NAME}/status", methods=["GET"])
def status():
    global flipper
    # Attempt reconnecting a flipper if not connected
    if flipper is None:
        start_flipper()
        if flipper is None:
            return jsonify({"connected": False, "device": DEVICE})
        return jsonify({"connected": True, "device": DEVICE})
    # Check if the flipper is still connected
    else:
        try:
            resp = flipper.send_and_wait('hello_world', wait=1.5)
            text = resp.decode(errors="replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
        except:
            flipper = None
            return jsonify({"connected": False, "device": DEVICE})
        
        if "Hello" not in text:
            flipper = None
            return jsonify({"connected": False, "device": DEVICE})

        return jsonify({"connected": True, "device": DEVICE})


        

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
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("FLASK_DEBUG") is None:
        start_flipper()
    else:
        # If running under plain `python app.py`, we start the flipper too
        start_flipper()
    
    if EXPECTED_PW is None:
        raise ValueError("Expected password in env")

    app.run(host="0.0.0.0", port=5000, debug=False)
