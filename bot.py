import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
import os
import time

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

log = logging.getLogger("LEVEL18_SMC")

# ================= DATA =================
def get_data(limit=150):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    return df

# ================= STRUCTURE =================
def detect_structure(df):

    highs = df["h"]
    lows = df["l"]

    resistance = highs.rolling(20).max().iloc[-2]
    support = lows.rolling(20).min().iloc[-2]

    price = df["c"].iloc[-1]

    return support, resistance, price

# ================= LIQUIDITY SWEEP =================
def liquidity_sweep(df, support, resistance):

    last = df.iloc[-1]

    # wick above resistance but close below → fake breakout
    if last["h"] > resistance and last["c"] < resistance:
        return "SELL_SIDE_SWEEP"

    # wick below support but close above → fake breakdown
    if last["l"] < support and last["c"] > support:
        return "BUY_SIDE_SWEEP"

    return "NONE"

# ================= BREAK OF STRUCTURE =================
def bos(df):

    recent_high = df["h"].iloc[-10:].max()
    recent_low = df["l"].iloc[-10:].min()
    price = df["c"].iloc[-1]

    if price > recent_high:
        return "BULL_BOS"
    if price < recent_low:
        return "BEAR_BOS"

    return "NONE"

# ================= SIGNAL ENGINE =================
def analyze(df):

    support, resistance, price = detect_structure(df)

    sweep = liquidity_sweep(df, support, resistance)
    structure = bos(df)

    score = 50

    # BOS confirmation
    if structure == "BULL_BOS":
        score += 30
    if structure == "BEAR_BOS":
        score -= 30

    # liquidity sweep logic
    if sweep == "BUY_SIDE_SWEEP":
        score += 20
    if sweep == "SELL_SIDE_SWEEP":
        score -= 20

    # zone logic
    in_discount = price < support * 1.01
    in_premium = price > resistance * 0.99

    if in_discount:
        score += 10
    if in_premium:
        score -= 10

    # final decision
    if score >= 75:
        signal = "LONG"
    elif score <= 25:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price, support, resistance, sweep, structure

# ================= FORMAT =================
def format_signal(signal, score, price, support, resistance, sweep, structure):

    if signal == "WAIT":
        return f"""
📊 SOL/USDT

⚪ NO TRADE ZONE

📉 Market Structure Unclear
🧠 Score: {score}/100

⚡ Waiting for liquidity confirmation
""".strip()

    direction = "🟢 LONG" if signal == "LONG" else "🔴 SHORT"

    entry_low = support if signal == "LONG" else resistance
    entry_high = price

    sl = support * 0.995 if signal == "LONG" else resistance * 1.005
    tp1 = price + (price - support) * 1.2 if signal == "LONG" else price - (resistance - price) * 1.2
    tp2 = price + (price - support) * 2 if signal == "LONG" else price - (resistance - price) * 2

    return f"""
🚀 SOL/USDT (LEVEL 18 SMC LITE)

{direction}

📍 Entry Zone:
{entry_low:.2f} - {entry_high:.2f}

📊 Support: {support:.2f}
📊 Resistance: {resistance:.2f}

🧠 Structure: {structure}
💧 Liquidity: {sweep}

🧠 Confidence: {score}/100

⛔ SL: {sl:.2f}

🎯 Targets:
TP1: {tp1:.2f}
TP2: {tp2:.2f}

📡 Mode: SMART MONEY LITE (SOL OPTIMIZED)
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("🚀 LEVEL 18 STARTED\n🧠 SMART MONEY LITE ACTIVE (SOL)")

    last_signal = None

    while True:

        try:

            df = get_data()

            signal, score, price, sup, res, sweep, structure = analyze(df)

            log.info(f"{signal} | {score} | {price:.2f}")

            if signal != "WAIT" and signal != last_signal:

                msg = format_signal(signal, score, price, sup, res, sweep, structure)
                await send(msg)

                last_signal = signal

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
