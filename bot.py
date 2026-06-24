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

TIMEFRAMES = ["1m", "5m", "15m"]
INTERVAL = 30
REPORT_INTERVAL = 600

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("V3_INST")

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
def get_data(symbol, tf):
    df = exchange.fetch_ohlcv(symbol, tf, limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df[["o","h","l","c"]] = df[["o","h","l","c"]].astype(float)
    return df

# ================= INDICATORS =================
def atr(df):
    h, l, c = df["h"], df["l"], df["c"]

    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)

    return tr.rolling(14).mean().iloc[-1]

def trend(df):
    ema_fast = df["c"].ewm(9).mean().iloc[-1]
    ema_slow = df["c"].ewm(21).mean().iloc[-1]

    if ema_fast > ema_slow:
        return "BULL"
    elif ema_fast < ema_slow:
        return "BEAR"
    return "SIDE"

def momentum(df):
    r = df["c"].pct_change().tail(10).sum()
    return r

def volume_ok(df):
    return df["v"].iloc[-1] > df["v"].rolling(20).mean().iloc[-1]

# ================= LIQUIDITY FILTER =================
def liquidity_sweep(df):
    high = df["h"].iloc[-10:].max()
    low = df["l"].iloc[-10:].min()
    price = df["c"].iloc[-1]

    # fake breakout detection
    if price > high * 1.002:
        return "FAKE_UP"
    if price < low * 0.998:
        return "FAKE_DOWN"
    return "CLEAN"

# ================= MULTI TF SCORE =================
def multi_tf_score(symbol):
    signals = []

    for tf in TIMEFRAMES:
        df = get_data(symbol, tf)

        t = trend(df)
        m = momentum(df)
        v = volume_ok(df)
        liq = liquidity_sweep(df)

        score = 50

        if t == "BULL":
            score += 25
        elif t == "BEAR":
            score -= 25

        if m > 0:
            score += 10
        else:
            score -= 10

        if v:
            score += 10
        else:
            score -= 10

        if liq != "CLEAN":
            score -= 20

        signals.append(score)

    return np.mean(signals)

# ================= STRATEGY =================
def strategy(symbol):
    df = get_data(symbol, "1m")

    price = df["c"].iloc[-1]
    score = multi_tf_score(symbol)

    if score > 70:
        signal = "LONG"
    elif score < 30:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price

# ================= EXECUTION =================
def open_position(symbol, signal, price):
    if symbol in portfolio.positions:
        return

    atr_val = atr(get_data(symbol, "1m"))
    size = (portfolio.balance * 0.01) / (atr_val * 2)

    sl = price - atr_val * 2 if signal == "LONG" else price + atr_val * 2
    tp = price + atr_val * 3 if signal == "LONG" else price - atr_val * 3

    portfolio.positions[symbol] = Position(symbol, price, size, signal, sl, tp)

    log.info(f"OPEN {symbol} {signal} @ {price:.2f}")

def close_position(symbol, price):
    pos = portfolio.positions[symbol]

    pnl = (price - pos.entry) * pos.size if pos.side == "LONG" else (pos.entry - price) * pos.size

    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)

    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} PnL:{pnl:.2f}")

def manage(symbol, df):
    if symbol not in portfolio.positions:
        return

    pos = portfolio.positions[symbol]
    price = df["c"].iloc[-1]

    if (pos.side == "LONG" and price <= pos.sl) or (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price)

    if (pos.side == "LONG" and price >= pos.tp) or (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price)

# ================= DASHBOARD =================
def dashboard():
    winrate = len([t for t in portfolio.trades if t > 0]) / max(1, len(portfolio.trades))

    return f"""
🚀 V3 INSTITUTIONAL ENGINE

💰 Balance: {portfolio.balance:.2f}
📊 WinRate: {winrate:.1%}
📦 Positions: {len(portfolio.positions)}
📈 Trades: {len(portfolio.trades)}
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except:
        pass

# ================= LOOP =================
async def run():
    await send("🚀 V3 INSTITUTIONAL STARTED")

    while True:
        try:
            for symbol in SYMBOLS:

                signal, score, price = strategy(symbol)

                df = get_data(symbol, "1m")
                manage(symbol, df)

                if signal != "WAIT":
                    open_position(symbol, signal, price)

                log.info(f"{symbol} | {signal} | {score:.1f} | {price:.2f}")

            await asyncio.sleep(INTERVAL)

        except Exception as e:
            log.error(e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
