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
    "options": {"defaultType": "spot"}
})

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL22.7")

# ================= STATS =================
stats = {
    "signals": 0,
    "wins": 0,
    "losses": 0,
    "equity": 1000.0,
    "peak": 1000.0,
    "drawdown": 0.0
}

RISK_PER_TRADE = 10

# ================= DATA =================
def get_data(limit=150):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= STRATEGY =================
def strategy_score(df):

    price = float(df["c"].iloc[-1])

    ema_fast = df["c"].ewm(span=9).mean().iloc[-1]
    ema_slow = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().std()

    score = 50
    trend = "NEUTRAL"

    if ema_fast > ema_slow:
        score += 20
        trend = "BULLISH"
    else:
        score -= 20
        trend = "BEARISH"

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

    return signal, score, price, trend

# ================= PAPER TRADE =================
def simulate_trade(signal):

    if signal == "WAIT":
        return 0

    move = np.random.normal(0.002, 0.01)
    pnl = RISK_PER_TRADE * (move * 100)

    return pnl

# ================= DASHBOARD =================
def dashboard(score, trend):

    total = stats["wins"] + stats["losses"]
    winrate = stats["wins"] / total if total > 0 else 0

    return f"""
📊 LEVEL 22.7 PRO DASHBOARD

🚀 SOL/USDT

📈 Signals: {stats['signals']}

🟢 Wins: {stats['wins']}
🔴 Losses: {stats['losses']}
📊 WinRate: {winrate:.2f}

💰 Equity: {stats['equity']:.2f} USDT
📈 Peak: {stats['peak']:.2f}
📉 Drawdown: {stats['drawdown']:.2f}

🧠 Last Score: {score}
📡 Trend: {trend}

⚡ PAPER TRADING MODE
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

🧠 LEVEL 22.7 ACTIVE
🚀 SYMBOL: SOL/USDT

📊 PRO DASHBOARD ENABLED
⚡ PAPER TRADING MODE
""")

    last_status = time.time()

    while True:

        try:

            df = get_data()

            signal, score, price, trend = strategy_score(df)

            stats["signals"] += 1

            pnl = simulate_trade(signal)

            stats["equity"] += pnl

            if pnl > 0:
                stats["wins"] += 1
            elif pnl < 0:
                stats["losses"] += 1

            if stats["equity"] > stats["peak"]:
                stats["peak"] = stats["equity"]

            stats["drawdown"] = stats["peak"] - stats["equity"]

            log.info(f"{signal} | {score} | {trend} | {price} | Equity:{stats['equity']:.2f}")

            if time.time() - last_status > STATUS_INTERVAL:

                await send(dashboard(score, trend))

                last_status = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
