import ccxt
import asyncio
import pandas as pd
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
STATUS_INTERVAL = 1800

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL22.6")

# ================= DATA =================
def get_data(timeframe="1m", limit=150):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe, limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= TREND ENGINE =================
def trend_5m():

    df = get_data("5m", 120)

    ema_fast = df["c"].ewm(span=9).mean().iloc[-1]
    ema_slow = df["c"].ewm(span=21).mean().iloc[-1]

    if ema_fast > ema_slow:
        return "BULLISH"
    elif ema_fast < ema_slow:
        return "BEARISH"
    else:
        return "RANGE"

# ================= SCORE ENGINE =================
def strategy_score(df):

    price = df["c"].iloc[-1]

    ema_fast = df["c"].ewm(span=9).mean().iloc[-1]
    ema_slow = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().std()

    score = 50

    if ema_fast > ema_slow:
        score += 20
    else:
        score -= 20

    if vol < 0.002:
        score += 10
    else:
        score -= 10

    if price > df["h"].rolling(20).mean().iloc[-1]:
        score += 10

    if price < df["l"].rolling(20).mean().iloc[-1]:
        score -= 10

    if score >= 72:
        signal = "LONG"
    elif score <= 28:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price

# ================= FILTER (IMPORTANT) =================
def final_decision(signal, trend):

    if trend == "RANGE":
        return "WAIT"

    if trend == "BULLISH" and signal == "LONG":
        return "LONG"

    if trend == "BEARISH" and signal == "SHORT":
        return "SHORT"

    return "WAIT"

# ================= FORMAT =================
def format_signal(signal, score, price, trend):

    sl = price * 0.99

    if signal == "LONG":
        tp1 = price * 1.01
        tp2 = price * 1.02
        tp3 = price * 1.03

        icon = "🟢 LONG 📈"

    elif signal == "SHORT":
        tp1 = price * 0.99
        tp2 = price * 0.98
        tp3 = price * 0.97

        icon = "🔴 SHORT 📉"

    else:
        return f"""
🚀 SOL/USDT

⚪ WAIT

📊 Score: {score}
📈 Trend: {trend}

📡 LEVEL 22.6 AI ENGINE
"""

    return f"""
🚀 SOL/USDT

{icon}

📍 Entry: Market

⚡ Score: {score}/100
📈 Trend: {trend}

🔥 Risk: 1%
⚖️ Leverage: x1

⛔ SL: {sl:.2f}

🎯 TP1: {tp1:.2f}
🎯 TP2: {tp2:.2f}
🎯 TP3: {tp3:.2f}

📡 LEVEL 22.6 AI ENGINE
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("""
🚀 BOT STARTED

🧠 LEVEL 22.6 ACTIVE
🚀 SYMBOL: SOL/USDT

📡 SYSTEM ONLINE
⚡ TREND FILTER ENABLED
""")

    last_signal = None
    last_status = time.time()

    while True:

        try:

            df = get_data("1m")

            signal, score, price = strategy_score(df)

            trend = trend_5m()

            decision = final_decision(signal, trend)

            current = f"{decision}_{score}"

            log.info(f"{decision} | {score} | {trend} | {price}")

            if current != last_signal and decision != "WAIT":

                msg = format_signal(decision, score, price, trend)

                await send(msg)

                last_signal = current

            if time.time() - last_status > STATUS_INTERVAL:

                await send(f"""
📊 SYSTEM STATUS

🟢 ONLINE

🚀 SOL/USDT

📈 Last Score: {score}
📊 Trend: {trend}

🧠 Level 22.6
""")

                last_status = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
