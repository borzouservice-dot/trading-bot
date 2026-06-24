import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
TIMEFRAME = "1m"
INTERVAL = 30
REPORT_INTERVAL = 600

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("UNIFIED_ENGINE")

# ================= STATE =================
@dataclass
class State:
    balance: float = 1000.0
    trades: list = None
    equity: list = None

    def __post_init__(self):
        self.trades = []
        self.equity = [self.balance]

state = State()

# ================= DATA =================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=200)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

    # FIX CRITICAL (numpy → pandas safe)
    for col in ["o","h","l","c"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna()

# ================= INDICATORS =================
def atr(df, period=14):
    high = df["h"]
    low = df["l"]
    close = df["c"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return float(tr.rolling(period).mean().iloc[-1])

# ================= STRATEGY =================
def strategy(df):
    price = float(df["c"].iloc[-1])

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().tail(30).std()

    score = 50
    signal = "WAIT"

    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"

    # FILTER (anti-chop)
    if vol < 0.0015:
        score -= 10
        signal = "WAIT"

    if score < 70:
        signal = "WAIT"

    return signal, float(score), price

# ================= EXECUTION =================
def simulate_trade(signal, price):
    if signal == "WAIT":
        return 0

    move = np.random.normal(0, 0.01)

    win_prob = 0.55 if signal in ["LONG", "SHORT"] else 0.5
    result = 1 if np.random.random() < win_prob else -1

    pnl = result * 5
    state.balance += pnl
    state.equity.append(state.balance)
    state.trades.append(pnl)

    return pnl

# ================= METRICS =================
def metrics():
    if len(state.trades) == 0:
        return 0.0, 0.0

    winrate = len([t for t in state.trades if t > 0]) / len(state.trades)

    eq = np.array(state.equity)
    peak = np.maximum.accumulate(eq)
    dd = np.max(peak - eq)

    return float(winrate), float(dd)

# ================= DASHBOARD =================
def dashboard():
    winrate, dd = metrics()

    return f"""
🚀 UNIFIED TRADING ENGINE v1

💰 Balance: {state.balance:.2f}
📊 WinRate: {winrate:.1%}
📉 Max DD: {dd:.2f}
📈 Trades: {len(state.trades)}
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= MAIN LOOP =================
async def run():

    await send("🚀 UNIFIED ENGINE STARTED")

    last_report = time.time()

    while True:
        try:
            for symbol in SYMBOLS:

                df = get_data(symbol)
                signal, score, price = strategy(df)

                pnl = simulate_trade(signal, price)

                log.info(f"{symbol} | {signal} | {score:.1f} | {price:.2f} | BAL:{state.balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
