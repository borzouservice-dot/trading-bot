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

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("V4_HEDGE")

# ================= STATE =================
@dataclass
class Position:
    symbol: str
    entry: float
    size: float
    side: str
    sl: float
    tp: float

class Portfolio:
    def __init__(self):
        self.balance = 1000.0
        self.positions = {}
        self.trades = []
        self.equity = [1000.0]

portfolio = Portfolio()

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df[["o","h","l","c","v"]] = df[["o","h","l","c","v"]].astype(float)
    return df

# ================= LAYER 1: TREND =================
def trend_score(df):
    ema50 = df["c"].ewm(50).mean().iloc[-1]
    ema200 = df["c"].ewm(200).mean().iloc[-1]

    if ema50 > ema200:
        return 1
    elif ema50 < ema200:
        return -1
    return 0

# ================= LAYER 2: MOMENTUM =================
def momentum_score(df):
    rsi = 100 - (100 / (1 + df["c"].pct_change().rolling(14).mean()))
    rsi_val = rsi.iloc[-1]

    roc = df["c"].pct_change(5).iloc[-1]

    score = 0

    if rsi_val > 55:
        score += 1
    elif rsi_val < 45:
        score -= 1

    if roc > 0:
        score += 1
    else:
        score -= 1

    return score

# ================= LAYER 3: LIQUIDITY =================
def liquidity_score(df):
    high = df["h"].rolling(20).max().iloc[-1]
    low = df["l"].rolling(20).min().iloc[-1]
    price = df["c"].iloc[-1]

    if price > high * 1.002:
        return -1
    if price < low * 0.998:
        return -1

    return 1

# ================= LAYER 4: VOLUME =================
def volume_score(df):
    v = df["v"]
    if v.iloc[-1] > v.rolling(20).mean().iloc[-1]:
        return 1
    return 0

# ================= FINAL SCORE =================
def final_score(df):
    t = trend_score(df)
    m = momentum_score(df)
    l = liquidity_score(df)
    v = volume_score(df)

    score = (t * 35) + (m * 25) + (l * 25) + (v * 15)
    return score

# ================= STRATEGY =================
def strategy(symbol):
    df = get_data(symbol)
    price = df["c"].iloc[-1]

    score = final_score(df)

    if score > 50:
        signal = "LONG"
    elif score < -50:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price

# ================= RISK =================
def position_size(balance, price):
    risk = balance * 0.01
    return risk / price

# ================= EXECUTION =================
def execute(symbol, signal, price):
    if symbol in portfolio.positions:
        return

    if signal == "WAIT":
        return

    size = position_size(portfolio.balance, price)

    if signal == "LONG":
        sl = price * 0.99
        tp = price * 1.03
    else:
        sl = price * 1.01
        tp = price * 0.97

    portfolio.positions[symbol] = Position(symbol, price, size, signal, sl, tp)

    log.info(f"OPEN {symbol} {signal} @ {price:.2f} | SCORE")

# ================= MANAGE =================
def manage(symbol, price):
    if symbol not in portfolio.positions:
        return

    pos = portfolio.positions[symbol]

    if pos.side == "LONG":
        pnl = (price - pos.entry) * pos.size
        if price <= pos.sl or price >= pos.tp:
            close(symbol, price, pnl)
    else:
        pnl = (pos.entry - price) * pos.size
        if price >= pos.sl or price <= pos.tp:
            close(symbol, price, pnl)

def close(symbol, price, pnl):
    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)
    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} PnL:{pnl:.2f}")

# ================= LOOP =================
async def run():
    log.info("🚀 V4 HEDGE FUND STARTED")

    while True:
        for s in SYMBOLS:
            signal, score, price = strategy(s)

            manage(s, price)
            execute(s, signal, price)

            log.info(f"{s} | {signal} | {score:.1f} | {price:.2f}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
