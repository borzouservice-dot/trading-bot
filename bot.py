import os
import time
import random
import asyncio
import logging
import json
import csv
import pickle
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SOL/USDT"

INTERVAL = 20

HEARTBEAT_INTERVAL = 300  # 5 minutes

DATA_DIR = "data"
QTABLE_PATH = f"{DATA_DIR}/qtable.pkl"
STATS_PATH = f"{DATA_DIR}/stats.json"
TRADES_PATH = f"{DATA_DIR}/trades.csv"

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger(__name__)

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= HEARTBEAT =================
last_heartbeat = 0

# ================= SAFE STORAGE =================
def load_qtable():
    try:
        if os.path.exists(QTABLE_PATH) and os.path.getsize(QTABLE_PATH) > 0:
            with open(QTABLE_PATH, "rb") as f:
                return pickle.load(f)
    except:
        pass
    return {}

def save_qtable():
    try:
        tmp = QTABLE_PATH + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(q_table, f)
        os.replace(tmp, QTABLE_PATH)
    except:
        pass

def load_stats():
    try:
        if os.path.exists(STATS_PATH):
            with open(STATS_PATH, "r") as f:
                return json.load(f)
    except:
        pass
    return {"wins": 0, "losses": 0, "total": 0}

def save_stats():
    try:
        tmp = STATS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(stats, f, indent=2)
        os.replace(tmp, STATS_PATH)
    except:
        pass

def log_trade(action, entry, exit_price, profit):
    try:
        file_exists = os.path.exists(TRADES_PATH)

        with open(TRADES_PATH, "a", newline="") as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow(["time", "action", "entry", "exit", "profit"])

            writer.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                action,
                entry,
                exit_price,
                profit
            ])
    except:
        pass

# ================= STATE =================
q_table = load_qtable()
stats = load_stats()
active_trade = None

ACTIONS = ["LONG", "SHORT", "HOLD"]

# ================= INDICATORS =================
def sma(data, n):
    return sum(data[-n:]) / n if len(data) >= n else None

def rsi(data, n=14):
    if len(data) < n + 1:
        return None

    gains, losses = [], []

    for i in range(1, len(data)):
        diff = data[i] - data[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[-n:]) / n
    avg_loss = sum(losses[-n:]) / n

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================= ENGINE =================
def get_state(fast, slow, rsi_val):
    trend = 1 if fast > slow else 0
    momentum = 1 if rsi_val > 50 else 0
    return (trend, momentum)

def confidence(fast, slow, rsi_val):
    score = 0
    if fast > slow:
        score += 1
    if 50 < rsi_val < 70:
        score += 1
    return score / 2

def get_q(state, action):
    return q_table.get((state, action), 0.0)

def choose_action(state):
    if random.random() < 0.1:
        return random.choice(ACTIONS)

    qs = [get_q(state, a) for a in ACTIONS]
    return ACTIONS[qs.index(max(qs))]

def update_q(state, action, reward, alpha=0.1):
    old = q_table.get((state, action), 0.0)
    q_table[(state, action)] = old + alpha * (reward - old)

# ================= DATA =================
def get_data():
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe="1m", limit=100)
        return [c[4] for c in ohlcv]
    except:
        return None

# ================= ENGINE =================
def ai_engine(price, closes):
    fast = sma(closes, 8)
    slow = sma(closes, 21)
    r = rsi(closes, 14)

    if None in [fast, slow, r]:
        return None

    conf = confidence(fast, slow, r)

    if conf < 0.55:
        return None

    state = get_state(fast, slow, r)
    action = choose_action(state)

    if action == "HOLD":
        return None

    return {
        "state": state,
        "action": action,
        "entry": price,
        "sl": price * (0.998 if action == "LONG" else 1.002),
        "tp": price * (1.003 if action == "LONG" else 0.997),
        "conf": conf,
        "time": time.time()
    }

# ================= TRADE =================
def finish_trade(win, price):
    global active_trade, stats

    entry = active_trade["entry"]
    action = active_trade["action"]

    profit = abs(price - entry)

    reward = profit if win else -profit
    update_q(active_trade["state"], action, reward)

    log_trade(action, entry, price, profit)

    stats["total"] += 1
    stats["wins"] += 1 if win else 0
    stats["losses"] += 1 if not win else 0

    save_qtable()
    save_stats()

    active_trade = None

def check_trade(price):
    global active_trade

    if not active_trade:
        return

    t = active_trade

    if t["action"] == "LONG":
        if price >= t["tp"]:
            finish_trade(True, price)
        elif price <= t["sl"]:
            finish_trade(False, price)

    elif t["action"] == "SHORT":
        if price <= t["tp"]:
            finish_trade(True, price)
        elif price >= t["sl"]:
            finish_trade(False, price)

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():
    global active_trade, last_heartbeat

    # 🚀 STARTUP MESSAGE
    await send(f"""
🚀 BOT STARTED

🧠 LEVEL 8.3 ACTIVE
🚀 SYMBOL: {SYMBOL}

📡 SYSTEM ONLINE
⚡ READY FOR SIGNALS
""".strip())

    last_heartbeat = time.time()

    while True:

        closes = get_data()
        if not closes:
            await asyncio.sleep(5)
            continue

        price = closes[-1]

        check_trade(price)

        # 🚨 TRADE GENERATION
        if not active_trade:
            trade = ai_engine(price, closes)

            if trade:
                active_trade = trade

                msg = f"""
🚨 NEW SOL SIGNAL

🚀 {SYMBOL}
🟢 {trade['action']}

📍 Entry: {trade['entry']:.2f}
⛔ SL: {trade['sl']:.2f}
🎯 TP: {trade['tp']:.2f}

🧠 State: {trade['state']}
📊 Confidence: {trade['conf']:.2f}

🤖 LEVEL 8.3
""".strip()

                await send(msg)

        # 💓 HEARTBEAT
        now = time.time()
        if now - last_heartbeat > HEARTBEAT_INTERVAL:

            await send(f"""
💓 HEARTBEAT

🚀 Bot: ACTIVE
🧠 Mode: LEVEL 8.3
🚀 Symbol: {SYMBOL}

⏱ Time: {time.strftime('%H:%M:%S')}
""".strip())

            last_heartbeat = now

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
