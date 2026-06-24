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
log = logging.getLogger("LEVEL25")

# ================= SAFE CAST =================
def f(x):
    try:
        if isinstance(x, pd.Series):
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
        df = df.apply(pd.to_numeric, errors="coerce").dropna()
        return df
    except:
        return pd.DataFrame()

# ================= ATR =================
def atr(df):
    if df.empty or len(df) < 20:
        return 0.0

    h = df["h"]
    l = df["l"]
    c = df["c"]

    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)

    val = tr.rolling(14).mean().iloc[-1]
    return f(val if not np.isnan(val) else df["c"].iloc[-1] * 0.01)

# ================= REGIME DETECTION (NEW CORE) =================
def market_regime(df):
    ema_fast = df["c"].ewm(10).mean().iloc[-1]
    ema_slow = df["c"].ewm(30).mean().iloc[-1]
    volatility = df["c"].pct_change().tail(30).std()

    if abs(ema_fast - ema_slow) / ema_slow > 0.002:
        if volatility < 0.004:
            return "TREND"
        else:
            return "VOLATILE_TREND"
    return "CHOP"

# ================= STRATEGY =================
def strategy(df):
    if df.empty:
        return "WAIT", 0.0, 0.0

    price = f(df["c"].iloc[-1])

    ema9 = f(df["c"].ewm(9).mean().iloc[-1])
    ema21 = f(df["c"].ewm(21).mean().iloc[-1])

    vol = f(df["c"].pct_change().tail(30).std())

    regime = market_regime(df)

    score = 50
    signal = "WAIT"

    # trend logic
    if ema9 > ema21:
        score += 25
        signal = "LONG"
    else:
        score -= 25
        signal = "SHORT"

    # regime filter (IMPORTANT)
    if regime == "CHOP":
        score -= 25
    elif regime == "VOLATILE_TREND":
        score -= 10

    # volatility filter
    if vol < 0.0015:
        score += 10
    elif vol > 0.005:
        score -= 20

    # final gate
    if score < 70:
        signal = "WAIT"

    return signal, f(score), price, regime

# ================= POSITION =================
def open_position(symbol, signal, price, atr_val):
    if symbol in portfolio.positions or atr_val <= 0:
        return

    size = max(5.0, (0.01 * portfolio.balance) / atr_val)

    sl = price - atr_val * 2 if signal == "LONG" else price + atr_val * 2
    tp = price + atr_val * 3 if signal == "LONG" else price - atr_val * 3

    portfolio.positions[symbol] = Position(symbol, price, size, signal, sl, tp)

    log.info(f"OPEN {symbol} {signal} @ {price:.2f}")

def close_position(symbol, price, reason):
    pos = portfolio.positions[symbol]

    pnl = (price - pos.entry) * pos.size if pos.side == "LONG" else (pos.entry - price) * pos.size
    pnl -= abs(pnl) * 0.002

    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)

    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} {reason} PnL:{pnl:.2f}")

def manage(df, symbol):
    if symbol not in portfolio.positions or df.empty:
        return

    price = f(df["c"].iloc[-1])
    pos = portfolio.positions[symbol]

    if (pos.side == "LONG" and price <= pos.sl) or (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price, "SL")
    elif (pos.side == "LONG" and price >= pos.tp) or (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price, "TP")

# ================= METRICS =================
def metrics():
    if not portfolio.trades:
        return 0.0, 0.0, portfolio.balance

    win = len([x for x in portfolio.trades if x > 0])
    wr = win / len(portfolio.trades)

    eq = np.array(portfolio.equity)
    dd = np.max(np.maximum.accumulate(eq) - eq)

    return wr, dd, portfolio.balance

# ================= DASHBOARD =================
def dashboard():
    wr, dd, bal = metrics()

    return f"""
🚀 LEVEL 25 SMART REGIME ENGINE

💰 Balance: {bal:.2f}
🟢 WinRate: {wr:.1%}
📉 Drawdown: {dd:.2f}

📊 Positions: {len(portfolio.positions)}

🧠 STATUS: REGIME-AWARE AI ACTIVE
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():
    await send("🚀 LEVEL 25 STARTED")

    last_report = time.time()

    while True:
        try:
            for symbol in SYMBOLS:

                df = get_data(symbol)
                signal, score, price, regime = strategy(df)
                atr_val = atr(df)

                manage(df, symbol)

                if signal != "WAIT":
                    open_position(symbol, signal, price, atr_val)

                log.info(f"{symbol} | {signal} | {score} | {price:.2f} | {regime} | BAL:{portfolio.balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()

        except Exception as e:
            log.exception(e)

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
