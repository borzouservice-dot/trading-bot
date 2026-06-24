import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
from dataclasses import dataclass
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 30
REPORT_INTERVAL = 600

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("V4.2")

# ================= STATE =================
@dataclass
class SignalTrade:
    symbol: str
    signal: str
    entry: float
    result: str = "OPEN"  # WIN / LOSS / OPEN

class Portfolio:
    def __init__(self):
        self.balance = 1000.0
        self.signals = []
        self.trades = []
        self.equity = [1000.0]
        self.last_signal = {}
        self.last_heartbeat = time.time()

portfolio = Portfolio()

# ================= TELEGRAM =================
def send(msg):
    try:
        bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df["c"] = df["c"].astype(float)
    return df

# ================= STRATEGY =================
def strategy(df):
    price = df["c"].iloc[-1]

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().tail(30).std()

    score = 50

    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"

    if vol < 0.0018:
        score += 15
    elif vol > 0.004:
        score -= 20

    if score < 70:
        signal = "WAIT"

    return signal, score, price

# ================= TRACK SIGNALS =================
def register_signal(symbol, signal, price):
    portfolio.signals.append(SignalTrade(symbol, signal, price))

def evaluate_signals(current_price):
    """
    بررسی اینکه سیگنال‌ها درست بودن یا نه
    """
    for s in portfolio.signals:
        if s.result != "OPEN":
            continue

        if s.signal == "WAIT":
            s.result = "SKIP"
            continue

        change = (current_price - s.entry) / s.entry

        if s.signal == "LONG":
            if change > 0:
                s.result = "WIN"
            elif change < -0.003:
                s.result = "LOSS"

        if s.signal == "SHORT":
            if change < 0:
                s.result = "WIN"
            elif change > 0.003:
                s.result = "LOSS"

# ================= STATS =================
def stats():
    wins = len([s for s in portfolio.signals if s.result == "WIN"])
    losses = len([s for s in portfolio.signals if s.result == "LOSS"])
    total = wins + losses

    accuracy = wins / total if total > 0 else 0

    return wins, losses, accuracy

# ================= DASHBOARD =================
def dashboard(signal, price, score):
    wins, losses, acc = stats()

    return f"""
🚀 V4.2 SIGNAL PERFORMANCE DASHBOARD

💰 Balance: {portfolio.balance:.2f}

📊 Signal Stats:
✔️ Wins: {wins}
❌ Losses: {losses}
📈 Accuracy: {acc:.2%}
📦 Total Tracked: {wins + losses}

🧠 Current Signal: {signal}
⚡ Score: {score}
📍 Price: {price:.2f}
"""

# ================= HEARTBEAT =================
def heartbeat():
    wins, losses, acc = stats()

    send(f"""
🟢 V4.2 HEARTBEAT

System: ACTIVE
Accuracy: {acc:.2%}
Wins: {wins} | Losses: {losses}
Signals tracked: {len(portfolio.signals)}

Bot is LIVE ✔️
""")

# ================= LOOP =================
async def run():
    send("🚀 V4.2 STARTED")

    last_report = time.time()

    while True:
        try:
            for s in SYMBOLS:

                df = get_data(s)
                signal, score, price = strategy(df)

                register_signal(s, signal, price)
                evaluate_signals(price)

                log.info(f"{s} | {signal} | {score} | {price}")

            if time.time() - last_report > REPORT_INTERVAL:
                send(dashboard(signal, price, score))
                last_report = time.time()

            if time.time() - portfolio.last_heartbeat > 120:
                heartbeat()
                portfolio.last_heartbeat = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
