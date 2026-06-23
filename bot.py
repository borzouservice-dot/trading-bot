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

log = logging.getLogger("LEVEL20_SNIPER")

# ================= DATA =================
def get_data(tf="1m", limit=200):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, tf, limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= STRUCTURE =================
def levels(df):

    resistance = df["h"].rolling(25).max().iloc[-2]
    support = df["l"].rolling(25).min().iloc[-2]

    price = df["c"].iloc[-1]

    return support, resistance, price

# ================= LIQUIDITY HUNT =================
def liquidity_hunt(df, support, resistance):

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # sweep low then close above → buy side liquidity grab
    buy_sweep = last["l"] < support and last["c"] > support

    # sweep high then close below → sell side liquidity grab
    sell_sweep = last["h"] > resistance and last["c"] < resistance

    return buy_sweep, sell_sweep

# ================= ORDER FLOW (proxy) =================
def order_flow(df):

    last = df.iloc[-1]

    body = abs(last["c"] - last["o"])
    candle_range = last["h"] - last["l"]

    strength = body / (candle_range + 1e-9)

    bullish_pressure = last["c"] > last["o"] and strength > 0.6
    bearish_pressure = last["c"] < last["o"] and strength > 0.6

    return bullish_pressure, bearish_pressure

# ================= SNIPER ENGINE =================
def analyze(df):

    support, resistance, price = levels(df)

    buy_sweep, sell_sweep = liquidity_hunt(df, support, resistance)
    bull_flow, bear_flow = order_flow(df)

    score = 50

    # liquidity logic (VERY IMPORTANT)
    if buy_sweep and bull_flow:
        score += 40

    if sell_sweep and bear_flow:
        score -= 40

    # breakout validation
    if price > resistance and bull_flow:
        score += 15

    if price < support and bear_flow:
        score -= 15

    signal = "WAIT"
    if score >= 80:
        signal = "LONG"
    elif score <= 20:
        signal = "SHORT"

    return signal, score, price, support, resistance, buy_sweep, sell_sweep

# ================= FORMAT =================
def format_signal(signal, score, price, sup, res, buy_sweep, sell_sweep):

    if signal == "WAIT":
        return f"""
📊 SOL/USDT

⚪ NO SNIPER SETUP

🧠 Score: {score}/100

💧 Liquidity: Waiting for sweep

⚡ No high-probability entry
""".strip()

    direction = "🟢 LONG" if signal == "LONG" else "🔴 SHORT"

    # SNIPER ENTRY ZONE (important change)
    entry_low = sup if signal == "LONG" else price
    entry_high = price if signal == "LONG" else res

    sl = sup * 0.995 if signal == "LONG" else res * 1.005

    tp1 = price + abs(price - sup) * 1.5 if signal == "LONG" else price - abs(res - price) * 1.5
    tp2 = price + abs(price - sup) * 2.5 if signal == "LONG" else price - abs(res - price) * 2.5

    return f"""
🎯 SOL/USDT (LEVEL 20 SNIPER)

{direction}

📍 ENTRY ZONE:
{entry_low:.2f} - {entry_high:.2f}

📊 Support: {sup:.2f}
📊 Resistance: {res:.2f}

💧 Buy Sweep: {"YES" if buy_sweep else "NO"}
💧 Sell Sweep: {"YES" if sell_sweep else "NO"}

🧠 Confidence: {score}/100

⛔ SL: {sl:.2f}

🎯 TP1: {tp1:.2f}
🎯 TP2: {tp2:.2f}

📡 Mode: SNIPER SMART MONEY ENGINE
⚖️ Leverage: x1 (manual only)
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("🎯 LEVEL 20 STARTED\n🧠 SNIPER SMART MONEY ENGINE ACTIVE")

    last_signal = None

    while True:

        try:

            df = get_data()

            signal, score, price, sup, res, buy_sweep, sell_sweep = analyze(df)

            log.info(f"{signal} | {score} | {price:.2f}")

            # VERY STRICT FILTER (important)
            if signal != "WAIT" and signal != last_signal:

                msg = format_signal(signal, score, price, sup, res, buy_sweep, sell_sweep)
                await send(msg)

                last_signal = signal

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
