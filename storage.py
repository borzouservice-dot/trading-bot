import json
import os

STATE_FILE = "data/state.json"

DEFAULT_STATE = {
    "balance": 1000.0,
    "positions": {},
    "wins": 0,
    "losses": 0,
    "trades": 0,
    "session_pnl": 0.0,
    "max_balance": 1000.0,
    "consecutive_loss": 0
}


def load_state():
    if not os.path.exists(STATE_FILE):
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()


def save_state(state):
    os.makedirs("data", exist_ok=True)

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def reset_state():
    save_state(DEFAULT_STATE)
