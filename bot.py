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
REPORT_INTERVAL = 600

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL23.7")

# ================= STATE =================
balance = 1000.0

trades = []          # +1 win / -1 loss
equity = [balance]
signals_log = []

# ================= DATA =================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=200)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= STRATEGY =================
def strategy(df):

    price = float(df["c"].iloc[-1])

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().std()

    score = 50

    if ema9 > ema21:
        score += 25
        signal = "LONG"
    else:
        score -= 25
        signal = "SHORT"

    if vol < 0.002:
        score += 10
    else:
        score -= 10

    if score < 65:
        signal = "WAIT"

    return signal, score, price

# ================= SIM TRADE =================
def simulate_trade(signal):

    if signal == "WAIT":
        return 0, "WAIT"

    move = np.random.normal(0.0015, 0.008)

    pnl = 10 * (move * 100)

    if pnl > 0:
        return 1, signal   # win
    else:
        return -1, signal  # loss

# ================= METRICS =================
def metrics():

    if len(trades) == 0:
        return 0, 0, 0

    winrate = len([t for t in trades if t == 1]) / len(trades)

    equity_arr = np.array(equity)

    peak = np.maximum.accumulate(equity_arr)
    drawdown = peak - equity_arr
    max_dd = float(np.max(drawdown))

    return winrate, max_dd, equity_arr[-1]

# ================= PERFORMANCE SCORE =================
def performance_score(winrate, max_dd):

    score = 50

    score += winrate * 40
    score -= max_dd * 0.5

    return max(0, min(100, score))

# ================= DASHBOARD =================
def dashboard(score, signal, price):

    winrate, max_dd, eq = metrics()
    perf = performance_score(winrate, max_dd)

    long_count = signals_log.count("LONG")
    short_count = signals_log.count("SHORT")
    wait_count = signals_log.count("WAIT")

    return f"""
📊 LEVEL 23.7 PRO ANALYTICS DASHBOARD

🚀 SOL/USDT

📈 EQUITY: {eq:.2f}

🟢 WinRate: {winrate:.2f}
📉 Max Drawdown: {max_dd:.2f}

⚡ Performance Score: {perf:.2f}/100

📊 Signals:
• LONG: {long_count}
• SHORT: {short_count}
• WAIT: {wait_count}

🧠 Last Signal: {signal}
📍 Price: {price:.2f}

📡 ANALYTICS ENGINE ACTIVE
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
🚀 LEVEL 23.7 STARTED

🧠 PRO ANALYTICS ENGINE ACTIVE
📊 WINRATE + DRAWDOWN TRACKING
⚡ SOL/USDT
""")

    last_report = time.time()

    global balance

    while True:

        try:

            df = get_data()

            signal, score, price = strategy(df)

            signals_log.append(signal)

            result, sig = simulate_trade(signal)

            if signal != "WAIT":
                trades.append(result)

                balance += result * 5
                equity.append(balance)

            log.info(f"{signal} | {score} | {price} | Equity:{balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:

                winrate, dd, eq = metrics()
                perf = performance_score(winrate, dd)

                await send(dashboard(perf, signal, price))

                last_report = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
