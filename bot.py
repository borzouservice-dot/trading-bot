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

log = logging.getLogger("LEVEL21_AI")

# ================= DATA =================
def get_data(limit=200):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= REGIME DETECTION =================
def market_regime(df):

    returns = df["c"].pct_change()

    volatility = returns.std()

    trend_strength = abs(df["c"].iloc[-1] - df["c"].iloc[-20]) / df["c"].iloc[-20]

    if volatility < 0.001:
        return "CHOP"

    if trend_strength > 0.01:
        return "TREND"

    return "RANGE"

# ================= LIQUIDITY ZONES =================
def liquidity(df):

    support = df["l"].rolling(25).min().iloc[-2]
    resistance = df["h"].rolling(25).max().iloc[-2]

    return support, resistance

# ================= MOMENTUM =================
def momentum(df):

    body = abs(df["c"] - df["o"])
    range_size = df["h"] - df["l"]

    strength = (body / (range_size + 1e-9)).iloc[-1]

    return strength

# ================= AI SCORING ENGINE =================
def analyze(df):

    regime = market_regime(df)
    sup, res = liquidity(df)
    price = df["c"].iloc[-1]
    mom = momentum(df)

    score = 50

    # regime filter (MOST IMPORTANT)
    if regime == "TREND":
        score += 25
    elif regime == "RANGE":
        score += 10
    else:
        score -= 40  # CHOP = NO TRADE ZONE

    # liquidity positioning
    if price > res:
        score += 10
    if price < sup:
        score += 10

    # momentum filter
    if mom > 0.6:
        score += 15
    elif mom < 0.3:
        score -= 10

    signal = "WAIT"
    if score >= 75:
        signal = "LONG"
    elif score <= 25:
        signal = "SHORT"

    return signal, score, price, sup, res, regime, mom

# ================= FORMAT =================
def format_signal(signal, score, price, sup, res, regime, mom):

    if signal == "WAIT":
        return f"""
📊 SOL/USDT (LEVEL 21 AI ENGINE)

⚪ NO TRADE ZONE

🧠 Score: {score}/100
📉 Market Regime: {regime}

⚠️ Condition: NOT OPTIMAL
💡 Waiting for clean structure
""".strip()

    direction = "🟢 LONG" if signal == "LONG" else "🔴 SHORT"

    entry_low = sup
    entry_high = res

    sl = sup * 0.995 if signal == "LONG" else res * 1.005
    tp1 = price + abs(price - sup) * 1.3 if signal == "LONG" else price - abs(res - price) * 1.3
    tp2 = price + abs(price - sup) * 2.2 if signal == "LONG" else price - abs(res - price) * 2.2

    return f"""
🚀 SOL/USDT (LEVEL 21 AI HEDGE ENGINE)

{direction}

📍 Entry Zone:
{entry_low:.2f} - {entry_high:.2f}

📊 Support: {sup:.2f}
📊 Resistance: {res:.2f}

🧠 Market Regime: {regime}
⚡ Momentum: {mom:.2f}

🧠 Confidence: {score}/100

⛔ SL: {sl:.2f}

🎯 TP1: {tp1:.2f}
🎯 TP2: {tp2:.2f}

📡 Mode: AI DECISION ENGINE (NO EMOTION)
⚖️ Leverage: x1
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("🚀 LEVEL 21 STARTED\n🧠 AI MARKET REGIME ENGINE ACTIVE")

    last_signal = None

    while True:

        try:

            df = get_data()

            signal, score, price, sup, res, regime, mom = analyze(df)

            log.info(f"{signal} | {score} | {price:.2f} | {regime}")

            if signal != "WAIT" and signal != last_signal:

                msg = format_signal(signal, score, price, sup, res, regime, mom)
                await send(msg)

                last_signal = signal

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
