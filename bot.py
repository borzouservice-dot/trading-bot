import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
from telegram import Bot
from dotenv import load_dotenv
import os

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SOL/USDT"

INTERVAL = 30
STATUS_INTERVAL = 600

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}  # SAFE MODE (no futures trading)
})

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL23_SAFE")

# ================= SIM STATE =================
balance = 1000.0
position = None

stats = {
    "signals": 0,
    "wins": 0,
    "losses": 0,
    "trades": 0,
    "equity": balance,
    "peak": balance,
    "drawdown": 0
}

# ================= DATA =================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=150)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= STRATEGY =================
def strategy(df):

    price = float(df["c"].iloc[-1])

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().std()

    score = 50
    trend = "NEUTRAL"

    if ema9 > ema21:
        score += 25
        trend = "BULLISH"
    else:
        score -= 25
        trend = "BEARISH"

    if vol < 0.002:
        score += 10
    else:
        score -= 10

    if score >= 70:
        signal = "LONG"
    elif score <= 30:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price, trend

# ================= SIM POSITION =================
def open_position(signal, price):

    if signal == "WAIT":
        return None

    size = 10  # fixed risk demo

    sl = price * (0.99 if signal == "LONG" else 1.01)
    tp = price * (1.02 if signal == "LONG" else 0.98)

    return {
        "signal": signal,
        "entry": price,
        "size": size,
        "sl": sl,
        "tp": tp,
        "status": "OPEN"
    }

# ================= SIM TRADE UPDATE =================
def update_position(pos, price):

    global balance

    if not pos:
        return None

    if pos["signal"] == "LONG":

        if price >= pos["tp"]:
            pnl = +10
        elif price <= pos["sl"]:
            pnl = -10
        else:
            return pos

    elif pos["signal"] == "SHORT":

        if price <= pos["tp"]:
            pnl = +10
        elif price >= pos["sl"]:
            pnl = -10
        else:
            return pos

    else:
        return pos

    # close trade
    balance += pnl

    stats["trades"] += 1

    if pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

    stats["equity"] = balance

    if balance > stats["peak"]:
        stats["peak"] = balance

    stats["drawdown"] = stats["peak"] - balance

    return None

# ================= DASHBOARD =================
def dashboard(score, trend):

    total = stats["wins"] + stats["losses"]
    winrate = stats["wins"] / total if total > 0 else 0

    return f"""
📊 LEVEL 23 SAFE DASHBOARD

🚀 SOL/USDT

📈 Signals: {stats['trades']}
🟢 Wins: {stats['wins']}
🔴 Losses: {stats['losses']}
📊 WinRate: {winrate:.2f}

💰 Equity: {stats['equity']:.2f}
📈 Peak: {stats['peak']:.2f}
📉 Drawdown: {stats['drawdown']:.2f}

🧠 Last Score: {score}
📡 Trend: {trend}

⚡ SAFE SIMULATION MODE
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    global position

    await send("""
🚀 LEVEL 23 SAFE STARTED

🧠 SIMULATION MODE ACTIVE
🚫 NO REAL TRADES
📡 SOL/USDT
""")

    last_status = time.time()

    while True:

        try:

            df = get_data()

            signal, score, price, trend = strategy(df)

            stats["signals"] += 1

            # open position
            if position is None:
                position = open_position(signal, price)

            # update position
            position = update_position(position, price)

            log.info(f"{signal} | {score} | {trend} | {price} | Equity:{balance:.2f}")

            # dashboard
            if time.time() - last_status > STATUS_INTERVAL:

                await send(dashboard(score, trend))

                last_status = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
