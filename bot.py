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
REPORT_INTERVAL = 300

DATA_DIR = "data"
QTABLE_PATH = f"{DATA_DIR}/qtable.pkl"
STATS_PATH = f"{DATA_DIR}/stats.json"
TRADES_PATH = f"{DATA_DIR}/trades.csv"

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
q_table = {}
stats = {"wins": 0, "losses": 0, "total": 0}
equity = 1000
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
    return (1 if fast > slow else 0, 1 if rsi_val > 50 else 0)

def confidence(fast, slow, rsi_val):
    score = 0
    if fast > slow:
        score += 1
    if 50 < rsi_val < 70:
        score += 1
    return score / 2

def choose_action():
    return random.choice(ACTIONS)

def ai_engine(price, closes):
    fast = sma(closes, 8)
    slow = sma(closes, 21)
    r = rsi(closes, 14)

    if None in [fast, slow, r]:
        return None

    conf = confidence(fast, slow, r)
    if conf < 0.55:
        return None

    action = choose_action()
    if action == "HOLD":
        return None

    return {
        "action": action,
        "entry": price,
        "sl": price * 0.998,
        "tp": price * 1.003,
        "conf": conf,
        "time": time.time()
    }

# ================= TRADE =================
def finish_trade(win, price):
    global stats, equity, active_trade

    entry = active_trade["entry"]
    pnl = price - entry if active_trade["action"] == "LONG" else entry - price

    if win:
        stats["wins"] += 1
        equity += pnl
    else:
        stats["losses"] += 1
        equity -= abs(pnl)

    stats["total"] += 1
    active_trade = None

# ================= REPORT =================
def report():
    if stats["total"] == 0:
        return "📊 No trades yet"

    winrate = (stats["wins"] / stats["total"]) * 100

    return f"""
📊 RL PERFORMANCE (LEVEL 8.5)

✅ Wins: {stats['wins']}
❌ Losses: {stats['losses']}
📈 WinRate: {winrate:.2f}%

📦 Trades: {stats['total']}
💰 Equity: {equity:.2f}
Q-States: {len(q_table)}
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():
    global active_trade

    await send(f"""
🚀 BOT STARTED

🧠 LEVEL 8.5 ACTIVE
🚀 SYMBOL: {SYMBOL}

📊 PROFIT ENGINE ONLINE
""".strip())

    last_report = time.time()

    while True:

        ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=100)
        closes = [c[4] for c in ohlcv]
        price = closes[-1]

        if not active_trade:
            trade = ai_engine(price, closes)

            if trade:
                active_trade = trade

                await send(f"""
🚨 NEW TRADE

🚀 {SYMBOL}
🟢 {trade['action']}

📍 Entry: {trade['entry']:.2f}
⛔ SL: {trade['sl']:.2f}
🎯 TP: {trade['tp']:.2f}

📊 Confidence: {trade['conf']:.2f}
🧠 LEVEL 8.5
""".strip())

        # REPORT SYSTEM
        if time.time() - last_report > REPORT_INTERVAL:
            await send(report())
            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
