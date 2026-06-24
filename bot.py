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
log = logging.getLogger("LEVEL23.6")

# ================= STATE =================
balance = 1000.0
trades = []
equity = [balance]

# ================= DATA =================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=200)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= CHOP FILTER =================
def market_regime(df):

    atr = (df["h"] - df["l"]).rolling(14).mean().iloc[-1]
    body = abs(df["c"] - df["o"]).rolling(14).mean().iloc[-1]

    trend_strength = body / atr if atr != 0 else 0

    if trend_strength > 0.6:
        return "TREND"
    elif trend_strength < 0.3:
        return "CHOP"
    else:
        return "NEUTRAL"

# ================= STRATEGY =================
def strategy(df):

    price = float(df["c"].iloc[-1])

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().std()

    regime = market_regime(df)

    score = 50
    signal = "WAIT"

    # ❌ NO TRADE IN CHOP MARKET
    if regime == "CHOP":
        return "WAIT", 0, price, regime

    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"

    if vol < 0.002:
        score += 10
    else:
        score -= 10

    if score < 65:
        signal = "WAIT"

    return signal, score, price, regime

# ================= SIM TRADE =================
def simulate(signal):

    if signal == "WAIT":
        return 0

    move = np.random.normal(0.0018, 0.007)

    return 10 * (move * 100)

# ================= METRICS =================
def stats_calc():

    if len(trades) == 0:
        return 0, 0

    winrate = len([t for t in trades if t > 0]) / len(trades)

    expectancy = np.mean(trades)

    return winrate, expectancy

# ================= DASHBOARD =================
def dashboard(score, regime):

    winrate, expectancy = stats_calc()

    return f"""
📊 LEVEL 23.6 SMART FILTER ENGINE

🚀 SOL/USDT

📡 Market Regime: {regime}

📈 Trades: {len(trades)}

🟢 WinRate: {winrate:.2f}
💰 Expectancy: {expectancy:.3f}

💹 Equity: {equity[-1]:.2f}

🧠 Last Score: {score}

⚡ ANTI-CHOP ACTIVE
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
🚀 LEVEL 23.6 STARTED

🧠 SMART FILTER ENGINE ACTIVE
🚫 CHOP MARKET BLOCKED
📡 SOL/USDT
""")

    last_report = time.time()

    global balance

    while True:

        try:

            df = get_data()

            signal, score, price, regime = strategy(df)

            pnl = simulate(signal)

            if signal != "WAIT":
                trades.append(pnl)
                balance += pnl
                equity.append(balance)

            log.info(f"{signal} | {score} | {regime} | {price} | Equity:{balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard(score, regime))
                last_report = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
