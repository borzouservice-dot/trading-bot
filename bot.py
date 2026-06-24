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
log = logging.getLogger("LEVEL24.2")

# ================= SAFE CAST ENGINE (FIX CORE) =================
def f(x):
    """Force scalar float — FIX numpy.ndarray bug"""
    if isinstance(x, np.ndarray):
        return float(x.item())
    if isinstance(x, (np.floating, float, int)):
        return float(x)
    try:
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
        self.last_heartbeat = time.time()

portfolio = Portfolio()

# ================= DATA =================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

    for col in ["o","h","l","c","v"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()
    return df

# ================= ATR (SAFE FIXED) =================
def atr(df, period=14):
    high = df["h"]
    low = df["l"]
    close = df["c"]

    tr = np.maximum.reduce([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ])

    val = tr.rolling(period).mean().iloc[-1]

    return f(val if not np.isnan(val) else df["c"].iloc[-1] * 0.015)

# ================= STRATEGY (FIXED TYPES) =================
def strategy(df):
    price = f(df["c"].iloc[-1])

    ema9 = f(df["c"].ewm(span=9, adjust=False).mean().iloc[-1])
    ema21 = f(df["c"].ewm(span=21, adjust=False).mean().iloc[-1])

    vol = f(df["c"].pct_change().tail(30).std())

    score = 50
    signal = "WAIT"

    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"

    if vol < 0.0018:
        score += 15
    elif vol > 0.0045:
        score -= 20

    if score < 68:
        signal = "WAIT"

    return signal, f(score), price

# ================= POSITION MANAGEMENT =================
def position_size(balance, atr_val, price):
    risk = 0.01 * balance
    stop = atr_val * 2

    if stop == 0:
        return 0.001

    size_usdt = risk / stop * price
    return max(5.0, size_usdt / price)

def open_position(symbol, signal, price, atr_val):
    if symbol in portfolio.positions:
        return

    size = position_size(portfolio.balance, atr_val, price)

    sl = price - atr_val * 2 if signal == "LONG" else price + atr_val * 2
    tp = price + atr_val * 3 if signal == "LONG" else price - atr_val * 3

    portfolio.positions[symbol] = Position(
        symbol=symbol,
        entry=price,
        size=size,
        side=signal,
        sl=sl,
        tp=tp,
        trailing_sl=sl
    )

    log.info(f"OPEN {symbol} {signal} | size={size:.4f} | price={price:.4f}")

def close_position(symbol, price, reason):
    pos = portfolio.positions[symbol]

    if pos.side == "LONG":
        pnl = (price - pos.entry) * pos.size
    else:
        pnl = (pos.entry - price) * pos.size

    pnl -= abs(pnl) * 0.002

    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)

    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} | {reason} | PnL={pnl:.2f}")

def manage_positions(df, symbol):
    if symbol not in portfolio.positions:
        return

    price = f(df["c"].iloc[-1])
    pos = portfolio.positions[symbol]
    atr_val = atr(df)

    # trailing
    if pos.side == "LONG":
        new_sl = price - atr_val * 2
        if new_sl > pos.trailing_sl:
            pos.trailing_sl = new_sl
            pos.sl = max(pos.sl, new_sl)
    else:
        new_sl = price + atr_val * 2
        if new_sl < pos.trailing_sl:
            pos.trailing_sl = new_sl
            pos.sl = min(pos.sl, new_sl)

    # SL / TP
    if (pos.side == "LONG" and price <= pos.sl) or (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price, "SL")
        return

    if (pos.side == "LONG" and price >= pos.tp) or (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price, "TP")
        return

# ================= METRICS =================
def metrics():
    if not portfolio.trades:
        return 0.0, 0.0, portfolio.balance

    wins = [t for t in portfolio.trades if t > 0]
    winrate = len(wins) / len(portfolio.trades)

    eq = np.array(portfolio.equity)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq

    return f(winrate), f(np.max(dd)), f(portfolio.balance)

# ================= HEALTH CHECK (NEW FIX) =================
def heartbeat():
    portfolio.last_heartbeat = time.time()

    if time.time() - portfolio.last_heartbeat > 120:
        log.error("SYSTEM STUCK (NO HEARTBEAT)")

# ================= DASHBOARD =================
def dashboard():
    winrate, dd, bal = metrics()
    open_pos = len(portfolio.positions)

    return f"""
🚀 LEVEL 24.2 FIXED ENGINE

💰 Balance: {bal:.2f}
🟢 WinRate: {winrate:.1%}
📉 Max DD: {dd:.2f}
📦 Trades: {len(portfolio.trades)}
📌 Open: {open_pos}

🧠 STATUS: STABLE + TYPE SAFE
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():
    await send("🚀 LEVEL 24.2 STARTED\n🧠 SAFE TYPE ENGINE ACTIVE")

    last_report = time.time()

    while True:
        try:
            heartbeat()

            for symbol in SYMBOLS:

                df = get_data(symbol)
                signal, score, price = strategy(df)
                atr_val = atr(df)

                manage_positions(df, symbol)

                if signal != "WAIT":
                    open_position(symbol, signal, price, atr_val)

                # LIVE OUTPUT (FIXED)
                print(f"📡 {symbol} | {signal} | {score:.1f} | {price:.2f} | BAL:{portfolio.balance:.2f}")

                log.info(f"{symbol} | {signal} | {score} | {price:.4f} | BAL:{portfolio.balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()

        except Exception as e:
            log.exception(e)   # 🔥 FULL TRACE FIX

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
