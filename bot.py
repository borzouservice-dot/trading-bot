import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
import os
from dataclasses import dataclass
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 30
REPORT_INTERVAL = 600
HEARTBEAT_INTERVAL = 120

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("V4.2_FIXED")

# ================= STATE =================
class Portfolio:
    def __init__(self):
        self.balance = 1000.0
        self.signals = []   # (symbol, signal, entry, result)
        self.last_signal = {}
        self.last_heartbeat = time.time()

portfolio = Portfolio()

# ================= TELEGRAM (FIXED ASYNC) =================
async def send(msg: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df["c"] = df["c"].astype(float)
    return df

# ================= STRATEGY =================
def strategy(df):
    price = float(df["c"].iloc[-1])

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

# ================= SIGNAL TRACKING =================
def register(symbol, signal, price):
    portfolio.signals.append({
        "symbol": symbol,
        "signal": signal,
        "entry": price,
        "result": "OPEN"
    })

def stats():
    wins = len([s for s in portfolio.signals if s["result"] == "WIN"])
    losses = len([s for s in portfolio.signals if s["result"] == "LOSS"])
    total = wins + losses
    acc = wins / total if total > 0 else 0
    return wins, losses, acc

def evaluate(current_price):
    for s in portfolio.signals:
        if s["result"] != "OPEN":
            continue

        change = (current_price - s["entry"]) / s["entry"]

        if s["signal"] == "LONG":
            if change > 0.002:
                s["result"] = "WIN"
            elif change < -0.002:
                s["result"] = "LOSS"

        if s["signal"] == "SHORT":
            if change < -0.002:
                s["result"] = "WIN"
            elif change > 0.002:
                s["result"] = "LOSS"

# ================= DASHBOARD =================
def dashboard(signal, price, score):
    wins, losses, acc = stats()

    return f"""
🚀 V4.2 FIXED DASHBOARD

💰 Balance: {portfolio.balance:.2f}

📊 SIGNAL PERFORMANCE
✔️ Wins: {wins}
❌ Losses: {losses}
📈 Accuracy: {acc:.2%}
📦 Total: {wins + losses}

🧠 Signal: {signal}
⚡ Score: {score}
📍 Price: {price:.2f}
"""

# ================= HEARTBEAT =================
async def heartbeat():
    wins, losses, acc = stats()

    await send(f"""
🟢 HEARTBEAT - BOT LIVE

Status: ACTIVE
Accuracy: {acc:.2%}
Wins: {wins} | Losses: {losses}
Signals: {len(portfolio.signals)}

System OK ✔️
""")

# ================= MAIN LOOP =================
async def run():
    await send("🚀 V4.2 FIXED STARTED")

    last_report = time.time()
    last_hb = time.time()

    while True:
        try:
            for s in SYMBOLS:

                df = get_data(s)
                signal, score, price = strategy(df)

                # register only meaningful signals
                if signal != "WAIT":
                    register(s, signal, price)

                evaluate(price)

                portfolio.last_signal[s] = signal

                log.info(f"{s} | {signal} | {score} | {price}")

            # 📊 REPORT
            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard(signal, price, score))
                last_report = time.time()

            # 🟢 HEARTBEAT FIXED
            if time.time() - last_hb > HEARTBEAT_INTERVAL:
                await heartbeat()
                last_hb = time.time()

        except Exception as e:
            log.error(f"Loop error: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
