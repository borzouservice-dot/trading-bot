import ccxt
import asyncio
import time
import logging
import numpy as np
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
import os

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SOL/USDT"
INTERVAL = 10

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

log = logging.getLogger("LEVEL13")

# ================= STATE =================
positions = []
equity = 1000

stats = {"wins": 0, "losses": 0, "total": 0}

MAX_POSITIONS = 2

# ================= DATA =================
def get_data(limit=100):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    return df

# ================= INDICATORS =================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

# ================= SIGNAL ENGINE =================
def signal_engine(df):

    df["ema_fast"] = ema(df["c"], 9)
    df["ema_slow"] = ema(df["c"], 21)
    df["rsi"] = rsi(df["c"], 14)

    latest = df.iloc[-1]

    trend_up = latest["ema_fast"] > latest["ema_slow"]
    trend_down = latest["ema_fast"] < latest["ema_slow"]

    rsi_val = latest["rsi"]

    if trend_up and rsi_val < 70:
        return "LONG", latest["c"]

    if trend_down and rsi_val > 30:
        return "SHORT", latest["c"]

    return "HOLD", latest["c"]

# ================= POSITION =================
def open_position(side, price):

    return {
        "side": side,
        "entry": price,
        "tp": price * 1.004,
        "sl": price * 0.997,
        "time": time.time()
    }

# ================= CLOSE =================
def close_position(pos, price):

    global equity, stats

    pnl = (price - pos["entry"]) if pos["side"] == "LONG" else (pos["entry"] - price)

    equity += pnl

    stats["total"] += 1

    if pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

# ================= CHECK =================
def check_positions(price):

    global positions

    new = []

    for p in positions:

        if p["side"] == "LONG":
            if price >= p["tp"] or price <= p["sl"]:
                close_position(p, price)
                continue

        else:
            if price <= p["tp"] or price >= p["sl"]:
                close_position(p, price)
                continue

        new.append(p)

    positions = new

# ================= REPORT =================
def report():

    wr = (stats["wins"] / stats["total"] * 100) if stats["total"] else 0

    return f"""
📊 LEVEL 13 DASHBOARD

💰 Equity: {equity:.2f}
📦 Positions: {len(positions)}

📈 Trades: {stats["total"]}
🟢 Wins: {stats["wins"]}
🔴 Losses: {stats["losses"]}
📊 WinRate: {wr:.2f}%

📡 Strategy: EMA(9/21) + RSI Filter
⚡ Mode: PRO SIGNAL ENGINE
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= START =================
async def start_msg():

    msg = f"""
🚀 BOT STARTED

🧠 LEVEL 13 ACTIVE
📡 SYMBOL: {SYMBOL}

📊 EMA + RSI STRATEGY LOADED
⚡ PRO MODE ENABLED
""".strip()

    await send(msg)
    log.info("STARTED")

# ================= LOOP =================
async def run():

    await start_msg()

    last_report = time.time()

    while True:

        try:

            df = get_data()

            signal, price = signal_engine(df)

            check_positions(price)

            # 🚨 filter quality trades
            if signal != "HOLD" and len(positions) < MAX_POSITIONS:

                pos = open_position(signal, price)
                positions.append(pos)

                msg = f"""
🚨 NEW TRADE (LEVEL 13)

🚀 {SYMBOL}
📊 {signal}

📍 Entry: {price:.2f}
🎯 TP: {pos['tp']:.2f}
⛔ SL: {pos['sl']:.2f}

📡 EMA + RSI CONFIRMED
📦 Positions: {len(positions)}
""".strip()

                await send(msg)

                log.info(f"{signal} | {price:.2f}")

            else:
                log.info(f"WAIT | {price:.2f} | Pos: {len(positions)}")

            if time.time() - last_report > 60:

                await send(report())
                last_report = time.time()

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
