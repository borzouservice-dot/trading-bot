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
HEARTBEAT_INTERVAL = 300

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

# ================= STATE =================
q_table = {}
stats = {"wins": 0, "losses": 0, "total": 0}
active_trade = None

ACTIONS = ["LONG", "SHORT", "HOLD"]

last_heartbeat = 0

# ================= SAFE INDICATORS =================
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

def volatility(closes):
    if len(closes) < 20:
        return 0

    returns = []
    for i in range(1, len(closes)):
        returns.append(abs(closes[i] - closes[i - 1]))

    return sum(returns[-20:]) / 20

# ================= MARKET REGIME =================
def market_state(closes):
    fast = sma(closes, 8)
    slow = sma(closes, 21)
    r = rsi(closes, 14)
    vol = volatility(closes)

    if None in [fast, slow, r]:
        return None

    trend = fast - slow

    # 📉 DEAD MARKET
    if vol < (closes[-1] * 0.0003):
        return "DEAD"

    # 📊 RANGE MARKET
    if abs(trend) < closes[-1] * 0.0008:
        return "RANGE"

    # 🚀 TREND MARKET
    return "TREND"

# ================= CONFIDENCE =================
def confidence(fast, slow, rsi_val, regime):
    score = 0

    if regime == "DEAD":
        return 0

    if regime == "RANGE":
        if 40 < rsi_val < 60:
            score += 0.5
        else:
            score -= 0.5

    if regime == "TREND":
        if fast > slow:
            score += 1
        if 50 < rsi_val < 70:
            score += 1

    return max(0, score / 2)

# ================= ENGINE =================
def get_state(fast, slow, rsi_val, regime):
    return (
        1 if fast > slow else 0,
        1 if rsi_val > 50 else 0,
        {"TREND": 1, "RANGE": 2, "DEAD": 0}[regime]
    )

def choose_action():
    return random.choice(ACTIONS)

def ai_engine(price, closes):
    fast = sma(closes, 8)
    slow = sma(closes, 21)
    r = rsi(closes, 14)
    vol = volatility(closes)
    regime = market_state(closes)

    if None in [fast, slow, r, regime]:
        return None

    conf = confidence(fast, slow, r, regime)

    # 💣 STRONG FILTERS
    if regime == "DEAD":
        return None

    if conf < 0.6:
        return None

    if vol < price * 0.0004:
        return None

    action = choose_action()

    if action == "HOLD":
        return None

    return {
        "action": action,
        "entry": price,
        "sl": price * (0.997 if action == "LONG" else 1.003),
        "tp": price * (1.004 if action == "LONG" else 0.996),
        "regime": regime,
        "conf": conf,
        "time": time.time()
    }

# ================= TRADE =================
def finish_trade():
    global active_trade, stats

    active_trade = None

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():
    global active_trade, last_heartbeat

    await send(f"""
🚀 BOT STARTED

🧠 LEVEL 8.4 ACTIVE
🚀 SYMBOL: {SYMBOL}

🌍 SMART MARKET FILTER ON
""".strip())

    last_heartbeat = time.time()

    while True:

        try:
            ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=100)
            closes = [c[4] for c in ohlcv]
            price = closes[-1]
        except:
            await asyncio.sleep(5)
            continue

        trade = ai_engine(price, closes)

        if trade:
            active_trade = trade

            await send(f"""
🚨 SMART SIGNAL

🚀 {SYMBOL}
🟢 {trade['action']}

📍 Entry: {trade['entry']:.2f}
⛔ SL: {trade['sl']:.2f}
🎯 TP: {trade['tp']:.2f}

🌍 Market: {trade['regime']}
📊 Confidence: {trade['conf']:.2f}

🧠 LEVEL 8.4
""".strip())

        # 💓 HEARTBEAT
        now = time.time()
        if now - last_heartbeat > HEARTBEAT_INTERVAL:
            await send(f"""
💓 HEARTBEAT

🚀 ACTIVE
🌍 {SYMBOL}
🧠 LEVEL 8.4

⏱ {time.strftime('%H:%M:%S')}
""".strip())

            last_heartbeat = now

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
