import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
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

log = logging.getLogger("LEVEL17_SOL")

# ================= DATA =================
def get_data(limit=120):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    return df

# ================= INDICATORS =================
def ema(s, n):
    return s.ewm(span=n).mean()

def atr(df, n=14):
    hl = df["h"] - df["l"]
    hc = abs(df["h"] - df["c"].shift())
    lc = abs(df["l"] - df["c"].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(n).mean()

# ================= SOL BEHAVIOR FILTER =================
def detect_fake_breakout(df):

    last = df.iloc[-1]
    prev = df.iloc[-2]

    body = abs(last["c"] - last["o"])
    wick_up = last["h"] - max(last["c"], last["o"])
    wick_down = min(last["c"], last["o"]) - last["l"]

    # wick dominance = fake breakout signal
    if wick_up > body * 2 or wick_down > body * 2:
        return True

    return False

# ================= SIGNAL ENGINE =================
def analyze(df):

    df["ema9"] = ema(df["c"], 9)
    df["ema21"] = ema(df["c"], 21)
    df["atr"] = atr(df)

    last = df.iloc[-1]

    price = last["c"]

    trend_up = last["ema9"] > last["ema21"]
    trend_down = last["ema9"] < last["ema21"]

    volatility = last["atr"]

    score = 50

    # trend
    if trend_up:
        score += 25
    if trend_down:
        score -= 25

    # volatility control (SOL important)
    if volatility > df["atr"].mean() * 1.5:
        score -= 20
    else:
        score += 5

    # fake breakout penalty
    fake = detect_fake_breakout(df)
    if fake:
        score -= 25

    # signal decision
    if score >= 75:
        signal = "LONG"
    elif score <= 25:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price, volatility, fake

# ================= FORMAT =================
def format_signal(signal, score, price, atr_val, fake):

    if signal == "WAIT":
        return f"""
📊 SOL/USDT

⚪ NO TRADE ZONE

🧠 Score: {score}/100
📉 Market is unstable
⚡ Waiting for clean setup
""".strip()

    direction = "🟢 LONG" if signal == "LONG" else "🔴 SHORT"

    # SOL dynamic zone (not fixed price)
    entry_low = price * 0.998
    entry_high = price * 1.002

    sl = price - atr_val * 1.8 if signal == "LONG" else price + atr_val * 1.8
    tp1 = price + atr_val * 2.2 if signal == "LONG" else price - atr_val * 2.2
    tp2 = price + atr_val * 3.5 if signal == "LONG" else price - atr_val * 3.5

    return f"""
🚀 SOL/USDT (LEVEL 17)

{direction}

📍 Entry Zone:
{entry_low:.2f} - {entry_high:.2f}

⚖️ Leverage: x1
🛡 Risk: 0.5% – 1%

⛔ Stop-Loss: {sl:.2f}

🎯 Targets:
TP1: {tp1:.2f}
TP2: {tp2:.2f}

🧠 Confidence: {score}/100
📊 Volatility: {"HIGH" if atr_val > 0 else "NORMAL"}
⚠️ Fake Breakout: {"YES" if fake else "NO"}

📡 Mode: SOL OPTIMIZED ENGINE
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("🚀 LEVEL 17 SOL ENGINE STARTED\n🧠 Fake Breakout Filter ACTIVE")

    last_signal = None

    while True:

        try:

            df = get_data()

            signal, score, price, atr_val, fake = analyze(df)

            log.info(f"{signal} | {score} | {price:.2f}")

            # cooldown system (important for SOL)
            if signal != "WAIT" and signal != last_signal:

                msg = format_signal(signal, score, price, atr_val, fake)
                await send(msg)

                last_signal = signal

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
