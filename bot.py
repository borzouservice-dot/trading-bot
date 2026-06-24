import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
from dataclasses import dataclass
from typing import Optional
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 30
REPORT_INTERVAL = 600

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("LEVEL24.3")

# ================= SAFE CAST ENGINE =================
def f(x):
    try:
        if isinstance(x, (pd.Series, pd.DataFrame)):
            x = x.iloc[-1]
        if isinstance(x, np.ndarray):
            x = x.item()
        return float(x)
    except:
        return 0.0

# ================= STATE =================
@dataclass
class Position:
    symbol: str
    entry: float
    size: float
    side: str
    sl: float
    tp: float
    trailing_sl: float

class Portfolio:
    def __init__(self):
        self.balance = 1000.0
        self.positions = {}
        self.trades = []
        self.equity = [1000.0]

portfolio = Portfolio()

# ================= DATA =================
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=200)
        df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

        df = df.apply(pd.to_numeric, errors="coerce")
        df = df.dropna()

        return df
    except Exception as e:
        log.error(f"DATA ERROR {symbol}: {e}")
        return pd.DataFrame()

# ================= ATR (FIXED 100%) =================
def atr(df, period=14):
    if df.empty or len(df) < period + 2:
        return 0.0

    high = df["h"]
    low = df["l"]
    close = df["c"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    val = tr.rolling(period).mean().iloc[-1]

    return f(val if not np.isnan(val) else df["c"].iloc[-1] * 0.015)

# ================= STRATEGY =================
def strategy(df):
    if df.empty:
        return "WAIT", 0.0, 0.0

    price = f(df["c"].iloc[-1])

    ema9 = f(df["c"].ewm(span=9).mean().iloc[-1])
    ema21 = f(df["c"].ewm(span=21).mean().iloc[-1])
    vol = f(df["c"].pct_change().tail(30).std())

    score = 50

    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"

    if vol < 0.0018:
        score += 10
    elif vol > 0.0045:
        score -= 15

    if score < 65:
        signal = "WAIT"

    return signal, f(score), price

# ================= POSITION MANAGEMENT =================
def open_position(symbol, signal, price, atr_val):
    if symbol in portfolio.positions:
        return

    if atr_val <= 0:
        return

    size = max(5.0, (0.01 * portfolio.balance) / atr_val)

    sl = price - atr_val * 2 if signal == "LONG" else price + atr_val * 2
    tp = price + atr_val * 3 if signal == "LONG" else price - atr_val * 3

    portfolio.positions[symbol] = Position(
        symbol, price, size, signal, sl, tp, sl
    )

    log.info(f"OPEN {symbol} {signal} @ {price:.2f}")

def close_position(symbol, price, reason):
    pos = portfolio.positions[symbol]

    pnl = (price - pos.entry) * pos.size if pos.side == "LONG" else (pos.entry - price) * pos.size
    pnl -= abs(pnl) * 0.002

    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)

    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} | {reason} | PnL={pnl:.2f}")

def manage_positions(df, symbol):
    if symbol not in portfolio.positions or df.empty:
        return

    price = f(df["c"].iloc[-1])
    pos = portfolio.positions[symbol]
    atr_val = atr(df)

    if pos.side == "LONG":
        pos.sl = max(pos.sl, price - atr_val * 2)
    else:
        pos.sl = min(pos.sl, price + atr_val * 2)

    if (pos.side == "LONG" and price <= pos.sl) or (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price, "SL")
        return

    if (pos.side == "LONG" and price >= pos.tp) or (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price, "TP")

# ================= METRICS =================
def metrics():
    if not portfolio.trades:
        return 0.0, 0.0, portfolio.balance

    wins = [t for t in portfolio.trades if t > 0]
    winrate = len(wins) / len(portfolio.trades)

    eq = np.array(portfolio.equity)
    peak = np.maximum.accumulate(eq)
    dd = np.max(peak - eq)

    return winrate, dd, portfolio.balance

# ================= DASHBOARD =================
def dashboard():
    wr, dd, bal = metrics()

    return f"""
🚀 LEVEL 24.3 STABLE ENGINE

💰 Balance: {bal:.2f}
🟢 WinRate: {wr:.1%}
📉 Max DD: {dd:.2f}
📦 Trades: {len(portfolio.trades)}
📊 Open: {len(portfolio.positions)}

STATUS: STABLE + NO CRASH
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= MAIN LOOP =================
async def run():
    await send("🚀 LEVEL 24.3 STARTED")

    last_report = time.time()

    while True:
        try:
            for symbol in SYMBOLS:

                df = get_data(symbol)
                signal, score, price = strategy(df)
                atr_val = atr(df)

                manage_positions(df, symbol)

                if signal != "WAIT":
                    open_position(symbol, signal, price, atr_val)

                log.info(f"{symbol} | {signal} | {score:.1f} | {price:.2f} | BAL:{portfolio.balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()

        except Exception as e:
            log.exception(e)

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
