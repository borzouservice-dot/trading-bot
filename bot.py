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

RISK_PER_TRADE = 0.01   # 1%
MAX_POSITIONS = 3

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("V2PRO")

# ================= STATE =================
@dataclass
class Position:
    symbol: str
    entry: float
    size: float
    side: str
    sl: float
    tp: float
    trail: float

class Portfolio:
    def __init__(self):
        self.balance = 1000.0
        self.positions = {}
        self.trades = []
        self.equity = [1000.0]
        self.last_signal_time = {}

portfolio = Portfolio()

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])

    for col in ["o","h","l","c"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna()

# ================= INDICATORS =================
def atr(df, period=14):
    h, l, c = df["h"], df["l"], df["c"]

    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)

    return float(tr.rolling(period).mean().iloc[-1])

def trend_score(df):
    ema9 = df["c"].ewm(9).mean().iloc[-1]
    ema21 = df["c"].ewm(21).mean().iloc[-1]
    vol = df["c"].pct_change().tail(30).std()

    score = 50

    if ema9 > ema21:
        score += 35
        signal = "LONG"
    else:
        score -= 35
        signal = "SHORT"

    # anti chop
    if vol < 0.0015:
        score -= 20
        signal = "WAIT"

    return signal, score

# ================= RISK =================
def position_size(balance, atr_val, price):
    risk = balance * RISK_PER_TRADE
    stop_dist = atr_val * 2

    if stop_dist == 0:
        return 0

    size_usdt = risk / stop_dist * price
    return round(size_usdt / price, 4)

# ================= EXECUTION =================
def open_position(symbol, signal, price, atr_val):
    if symbol in portfolio.positions:
        return

    size = position_size(portfolio.balance, atr_val, price)
    if size <= 0:
        return

    sl = price - atr_val * 2 if signal == "LONG" else price + atr_val * 2
    tp = price + atr_val * 3 if signal == "LONG" else price - atr_val * 3

    portfolio.positions[symbol] = Position(
        symbol, price, size, signal, sl, tp, sl
    )

    log.info(f"OPEN {symbol} {signal} @ {price:.2f}")

def close_position(symbol, price, reason):
    pos = portfolio.positions[symbol]

    pnl = (price - pos.entry) * pos.size if pos.side == "LONG" else (pos.entry - price) * pos.size

    fee = abs(pnl) * 0.002
    pnl -= fee

    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)

    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} {reason} PnL:{pnl:.2f}")

def manage(symbol, df):
    if symbol not in portfolio.positions:
        return

    pos = portfolio.positions[symbol]
    price = df["c"].iloc[-1]
    atr_val = atr(df)

    # trailing stop
    if pos.side == "LONG":
        new_sl = price - atr_val * 2
        if new_sl > pos.trail:
            pos.trail = new_sl
            pos.sl = max(pos.sl, new_sl)
    else:
        new_sl = price + atr_val * 2
        if new_sl < pos.trail:
            pos.trail = new_sl
            pos.sl = min(pos.sl, new_sl)

    # SL
    if (pos.side == "LONG" and price <= pos.sl) or (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price, "SL")

    # TP
    if (pos.side == "LONG" and price >= pos.tp) or (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price, "TP")

# ================= METRICS =================
def metrics():
    if not portfolio.trades:
        return 0.0, 0.0

    winrate = len([t for t in portfolio.trades if t > 0]) / len(portfolio.trades)

    eq = np.array(portfolio.equity)
    dd = np.max(np.maximum.accumulate(eq) - eq)

    return winrate, dd

# ================= DASHBOARD =================
def dashboard():
    wr, dd = metrics()

    open_p = len(portfolio.positions)

    return f"""
🚀 V2 PRO ENGINE

💰 Balance: {portfolio.balance:.2f}
📊 WinRate: {wr:.1%}
📉 Drawdown: {dd:.2f}
📦 Open Positions: {open_p}
📈 Trades: {len(portfolio.trades)}
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= MAIN LOOP =================
async def run():
    await send("🚀 V2 PRO STARTED")

    last_report = time.time()

    while True:
        try:
            for symbol in SYMBOLS:

                df = get_data(symbol)
                signal, score = trend_score(df)
                price = df["c"].iloc[-1]
                atr_val = atr(df)

                manage(symbol, df)

                if signal != "WAIT":
                    open_position(symbol, signal, price, atr_val)

                log.info(f"{symbol} | {signal} | {score:.1f} | {price:.2f} | BAL:{portfolio.balance:.2f}")

            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
