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

SYMBOL = "BTC/USDT"
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

log = logging.getLogger("LEVEL16")

# ================= DATA =================
def get_data(limit=120):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    return df

# ================= INDICATORS =================
def ema(s, n):
    return s.ewm(span=n).mean()

def atr(df, period=14):
    high_low = df["h"] - df["l"]
    high_close = np.abs(df["h"] - df["c"].shift())
    low_close = np.abs(df["l"] - df["c"].shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def rsi(series, n=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = -delta.clip(upper=0).rolling(n).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

# ================= MARKET ANALYSIS =================
def analyze(df):

    df["ema9"] = ema(df["c"], 9)
    df["ema21"] = ema(df["c"], 21)
    df["rsi"] = rsi(df["c"], 14)
    df["atr"] = atr(df)

    last = df.iloc[-1]

    price = last["c"]

    trend_up = last["ema9"] > last["ema21"]
    trend_down = last["ema9"] < last["ema21"]

    rsi_val = last["rsi"]
    volatility = last["atr"]

    score = 50

    # trend weight
    if trend_up:
        score += 25
    if trend_down:
        score -= 25

    # RSI filter
    if 40 < rsi_val < 60:
        score += 10
    elif rsi_val > 70 or rsi_val < 30:
        score -= 15

    # volatility filter
    if volatility > df["atr"].mean():
        score -= 10
    else:
        score += 5

    # signal decision
    if score >= 70:
        signal = "LONG"
    elif score <= 30:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price, rsi_val, volatility, trend_up

# ================= SIGNAL FORMAT =================
def format_signal(signal, score, price, rsi, atr_val, trend_up):

    direction = "🟢 LONG" if signal == "LONG" else "🔴 SHORT" if signal == "SHORT" else "⚪ WAIT"

    if signal == "WAIT":
        return f"""
📊 {SYMBOL}

⚪ NO TRADE ZONE

📉 Market is not clear
🧠 Score: {score}/100

⚡ Waiting for confirmation
""".strip()

    sl = price - (atr_val * 1.5) if signal == "LONG" else price + (atr_val * 1.5)
    tp1 = price + (atr_val * 2) if signal == "LONG" else price - (atr_val * 2)
    tp2 = price + (atr_val * 3) if signal == "LONG" else price - (atr_val * 3)

    return f"""
🚀 {SYMBOL}

{direction}

📍 Entry: {price:.2f}
⚖️ Leverage: x1
🛡 Risk: 0.5% – 1%

⛔ Stop-Loss: {sl:.2f}

🎯 Targets:
TP1: {tp1:.2f}
TP2: {tp2:.2f}

🧠 Confidence: {score}/100
📉 RSI: {rsi:.2f}
📊 Volatility: {"High" if atr_val > 0 else "Normal"}

📡 Mode: SAFE PRO SIGNAL ENGINE
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= START =================
async def start():

    await send(f"""
🚀 LEVEL 16 STARTED

🧠 SAFE PRO SIGNAL ENGINE ACTIVE
📊 {SYMBOL}
⚖️ Leverage Fixed: x1

⚡ Trading Mode: MANUAL ONLY
""".strip())

# ================= LOOP =================
async def run():

    await start()

    last_signal = None

    while True:

        try:

            df = get_data()

            signal, score, price, rsi, atr_val, trend = analyze(df)

            log.info(f"{signal} | {score} | {price:.2f}")

            # فقط سیگنال‌های جدید
            if signal != "WAIT" and signal != last_signal:

                msg = format_signal(signal, score, price, rsi, atr_val, trend)
                await send(msg)

                last_signal = signal

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= RUN =================
if __name__ == "__main__":
    asyncio.run(run())
