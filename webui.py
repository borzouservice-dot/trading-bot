# ==========================================
# WEB UI V4
# ==========================================

from flask import Flask
from flask import render_template
from flask import jsonify

import psutil
import time

from storage import load_state

# ==========================================
# APP
# ==========================================

app = Flask(__name__)

START_TIME = time.time()

# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )

# ==========================================
# API STATUS
# ==========================================

@app.route("/api/status")
def api_status():

    s = load_state()

    trades = s["trades"]

    wr = 0

    if trades > 0:

        wr = (
            s["wins"]
            /
            trades
            *
            100
        )

    positions = []

    for sym, p in s["positions"].items():

        positions.append({

            "symbol": sym,

            "side": p["side"]

        })

    uptime = int(
        time.time()
        -
        START_TIME
    )

    return jsonify({

        "balance":
            s["balance"],

        "session_pnl":
            s["session_pnl"],

        "trades":
            trades,

        "wins":
            s["wins"],

        "losses":
            s["losses"],

        "win_rate":
            wr,

        "positions":
            positions,

        "cpu":
            psutil.cpu_percent(),

        "ram":
            int(
                psutil.Process()
                .memory_info()
                .rss
                /
                1024
                /
                1024
            ),

        "uptime":
            f"{uptime}s",

        "status":
            "ONLINE"

    })

# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=8080,

        debug=False

    )
