import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
import os
from dataclasses import dataclass
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 30
REPORT_INTERVAL = 600
HEARTBEAT = 120

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("V5_1")

# ================= STATE =================
class Fund:
    def __init__(self):
        self.balance = 1000.0
        self.equity = [1000.0]
        self.trades = []       # 1 win / -1 loss
        self.signals = []
        self.last_signal = {}
        self.last_hb = time.time()

fund = Fund()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df["c"] = df["c"].astype(float)
    return df

# ================= MARKET REGIME =================
def market_regime(df):

    ema20 = df["c"].ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = df["c"].ewm(span=50, adjust=False).mean().iloc[-1]

    distance = abs(ema20 - ema50) / ema50

    if distance < 0.0008:
        return "CHOP"

    if ema20 > ema50:
        return "TREND_UP"

    return "TREND_DOWN"

# ================= SIGNAL ENGINE =================
def signal_engine(df):

    price = df["c"].iloc[-1]

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    rsi = compute_rsi(df["c"])

    score = 50
    signal = "WAIT"

    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"

    if rsi > 70:
        score -= 15
    elif rsi < 30:
        score += 15

    if score < 68:
        signal = "WAIT"

    return signal, score, price

# ================= RSI =================
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs)).iloc[-1]

# ================= TRACKING =================
def register(symbol, signal, price):
    fund.signals.append({
        "symbol": symbol,
        "signal": signal,
        "entry": price,
        "result": "OPEN"
    })

def evaluate(symbol, price):

    for s in fund.signals:

        if s["symbol"] != symbol:
            continue

        if s["result"] != "OPEN":
            continue

        change = (price - s["entry"]) / s["entry"]

        if s["signal"] == "LONG":
            if change > 0.003:
                s["result"] = "WIN"
                fund.trades.append(1)
                fund.balance += 10
                fund.equity.append(fund.balance)

            elif change < -0.003:
                s["result"] = "LOSS"
                fund.trades.append(-1)
                fund.balance -= 10
                fund.equity.append(fund.balance)

        if s["signal"] == "SHORT":
            if change < -0.003:
                s["result"] = "WIN"
                fund.trades.append(1)
                fund.balance += 10
                fund.equity.append(fund.balance)

            elif change > 0.003:
                s["result"] = "LOSS"
                fund.trades.append(-1)
                fund.balance -= 10
                fund.equity.append(fund.balance)

# ================= METRICS =================
def metrics():
    wins = len([t for t in fund.trades if t == 1])
    losses = len([t for t in fund.trades if t == -1])
    total = wins + losses
    acc = wins / total if total > 0 else 0

    eq = np.array(fund.equity)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq

    return wins, losses, acc, float(np.max(dd) if len(dd) else 0)

# ================= DASHBOARD =================
def dashboard():

    w, l, acc, dd = metrics()

    return f"""
🚀 V5.1 UNIFIED QUANT

💰 Balance: {fund.balance:.2f}

✔ Wins: {w}
❌ Losses: {l}
📊 Accuracy: {acc:.2%}
📉 Drawdown: {dd:.2f}

🧬 System: ACTIVE ✔️
"""

# ================= HEARTBEAT =================
async def heartbeat():
    w, l, acc, dd = metrics()

    await send(f"""
🟢 HEARTBEAT

Balance: {fund.balance:.2f}
Accuracy: {acc:.2%}
Wins: {w} | Losses: {l}
DD: {dd:.2f}

System OK ✔️
""")

# ================= MAIN LOOP =================
async def run():

    await send("🚀 V5.1 UNIFIED QUANT STARTED")
    await send("🟢 SYSTEM ONLINE")

    last_report = time.time()
    last_hb = time.time()

    while True:

        try:

            for sym in SYMBOLS:

                df = get_data(sym)

                regime = market_regime(df)

                signal, score, price = signal_engine(df)

                # CHOP FILTER
                if regime == "CHOP":
                    log.info(f"{sym} | CHOP MARKET SKIP")
                    continue

                # SIGNAL CHANGE ONLY
                if signal != "WAIT":

                    if signal != fund.last_signal.get(sym):

                        register(sym, signal, price)

                        await send(f"""
🚨 NEW SIGNAL

{sym}
Signal: {signal}
Score: {score}
Price: {price:.2f}
Regime: {regime}
""")

                        fund.last_signal[sym] = signal

                evaluate(sym, price)

                log.info(f"{sym} | {regime} | {signal} | {score} | {price}")

            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()

            if time.time() - last_hb > HEARTBEAT:
                await heartbeat()
                last_hb = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(run())
