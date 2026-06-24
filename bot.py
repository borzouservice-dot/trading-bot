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
log = logging.getLogger("LEVEL23.5")

# ================= STATE =================
balance = 1000.0

trades = []
equity_curve = [balance]

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

    if score < 60 and score > 40:
        signal = "WAIT"

    return signal, score, price

# ================= SIM TRADE =================
def simulate_trade(signal):

    if signal == "WAIT":
        return 0

    # realistic noise model
    move = np.random.normal(0.0015, 0.008)

    pnl = 10 * (move * 100)

    return pnl

# ================= METRICS =================
def calculate_metrics():

    global trades, equity_curve

    if len(trades) == 0:
        return 0, 0, 0

    avg_win = np.mean([t for t in trades if t > 0] or [0])
    avg_loss = np.mean([t for t in trades if t < 0] or [0])

    win_rate = len([t for t in trades if t > 0]) / len(trades)

    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    # drawdown
    peak = equity_curve[0]
    max_dd = 0

    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    return win_rate, expectancy, max_dd

# ================= DASHBOARD =================
def dashboard(score):

    win_rate, expectancy, max_dd = calculate_metrics()

    return f"""
📊 LEVEL 23.5 PERFORMANCE ANALYZER

🚀 SOL/USDT

📈 Trades: {len(trades)}

🟢 WinRate: {win_rate:.2f}
💰 Expectancy: {expectancy:.3f}

📉 Max Drawdown: {max_dd:.2f}

💹 Equity: {equity_curve[-1]:.2f}

🧠 Last Score: {score}

⚡ EDGE ANALYSIS MODE
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
🚀 LEVEL 23.5 STARTED

🧠 PERFORMANCE ANALYZER ACTIVE
📊 EDGE DETECTION MODE
⚡ SOL/USDT
""")

    last_report = time.time()

    global balance

    while True:

        try:

            df = get_data()

            signal, score, price = strategy(df)

            pnl = simulate_trade(signal)

            if signal != "WAIT":
                trades.append(pnl)

                balance += pnl
                equity_curve.append(balance)

            log.info(f"{signal} | {score} | PnL:{pnl:.2f} | Equity:{balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:

                await send(dashboard(score))

                last_report = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
