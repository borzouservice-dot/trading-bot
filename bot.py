import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
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

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

log = logging.getLogger("LEVEL19")

# ================= DATA =================
def get_data(tf="1m", limit=200):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, tf, limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= STRUCTURE =================
def structure(df):

    high = df["h"].rolling(20).max().iloc[-2]
    low = df["l"].rolling(20).min().iloc[-2]

    price = df["c"].iloc[-1]

    return low, high, price

# ================= VOLUME SPIKE =================
def volume_spike(df):

    vol_mean = df["v"].rolling(20).mean().iloc[-2]
    last_vol = df["v"].iloc[-1]

    return last_vol > vol_mean * 1.8

# ================= BREAKOUT CONFIRMATION =================
def breakout(df, resistance, support):

    last = df.iloc[-1]

    body = abs(last["c"] - last["o"])
    range_size = last["h"] - last["l"]

    strength = body / (range_size + 1e-9)

    bull_break = last["c"] > resistance and strength > 0.6
    bear_break = last["c"] < support and strength > 0.6

    if bull_break:
        return "BULL_BREAK"
    if bear_break:
        return "BEAR_BREAK"

    return "NONE"

# ================= MULTI TIMEFRAME =================
def analyze():

    df_1m = get_data("1m")
    df_5m = get_data("5m")
    df_15m = get_data("15m")

    sup1, res1, price = structure(df_1m)
    sup5, res5, _ = structure(df_5m)
    sup15, res15, _ = structure(df_15m)

    vol_ok = volume_spike(df_1m)

    brk1 = breakout(df_1m, res1, sup1)
    brk5 = breakout(df_5m, res5, sup5)

    score = 50

    # multi timeframe alignment
    if brk1 == brk5 == "BULL_BREAK":
        score += 35

    if brk1 == brk5 == "BEAR_BREAK":
        score -= 35

    # liquidity alignment
    if price > res1 and price > res5:
        score += 10

    if price < sup1 and price < sup5:
        score -= 10

    # volume confirmation
    if vol_ok:
        score += 15
    else:
        score -= 10

    signal = "WAIT"
    if score >= 75:
        signal = "LONG"
    elif score <= 25:
        signal = "SHORT"

    return signal, score, price, sup1, res1, vol_ok, brk1, brk5

# ================= FORMAT =================
def format_signal(signal, score, price, sup, res, vol, brk1, brk5):

    if signal == "WAIT":
        return f"""
📊 SOL/USDT

⚪ NO TRADE ZONE

🧠 Score: {score}/100

📉 Multi-TF not aligned
💧 Volume: {"OK" if vol else "LOW"}

⚡ Waiting for clean breakout
""".strip()

    direction = "🟢 LONG" if signal == "LONG" else "🔴 SHORT"

    sl = sup * 0.995 if signal == "LONG" else res * 1.005
    tp1 = price + abs(price - sup) * 1.2 if signal == "LONG" else price - abs(res - price) * 1.2
    tp2 = price + abs(price - sup) * 2 if signal == "LONG" else price - abs(res - price) * 2

    return f"""
🚀 SOL/USDT (LEVEL 19 PRO SMC)

{direction}

📍 Entry: {price:.2f}
📊 Support: {sup:.2f}
📊 Resistance: {res:.2f}

📈 Breakout 1m: {brk1}
📈 Breakout 5m: {brk5}

💧 Volume Spike: {"YES" if vol else "NO"}

🧠 Confidence: {score}/100

⛔ SL: {sl:.2f}

🎯 TP1: {tp1:.2f}
🎯 TP2: {tp2:.2f}

📡 Mode: MULTI-TIMEFRAME SMC PRO
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("🚀 LEVEL 19 STARTED\n🧠 MULTI-TF SMC PRO ACTIVE")

    last_signal = None

    while True:

        try:

            signal, score, price, sup, res, vol, brk1, brk5 = analyze()

            log.info(f"{signal} | {score} | {price:.2f}")

            if signal != "WAIT" and signal != last_signal:

                msg = format_signal(signal, score, price, sup, res, vol, brk1, brk5)
                await send(msg)

                last_signal = signal

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
