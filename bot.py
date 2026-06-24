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

# ================= CONFIG =================
load_dotenv()

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("LEVEL24_FIX")

# ================= STATE =================
@dataclass
class Position:
    symbol: str
    entry: float
    size: float
    side: str
    sl: float
    tp: float
    trailing: float = 0.0

class Portfolio:
    def __init__(self):
        self.balance = 1000.0
        self.positions = {}
        self.trades = []
        self.equity = [1000.0]

portfolio = Portfolio()

# ================= DATA =================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    df["c"] = df["c"].astype(float)
    return df

# ================= ATR =================
def atr(df, period=14):
    high = df["h"]
    low = df["l"]
    close = df["c"]

    tr = np.maximum(
        high - low,
        np.maximum(abs(high - close.shift()), abs(low - close.shift()))
    )

    val = tr.rolling(period).mean().iloc[-1]

    if np.isnan(val):
        return float(df["c"].iloc[-1] * 0.002)

    return float(val)

# ================= STRATEGY =================
def strategy(df):
    price = float(df["c"].iloc[-1])

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().std()

    score = 50
    signal = "WAIT"

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

    return signal, float(score), price

# ================= POSITION MANAGEMENT =================
def position_size(balance, atr_val):
    risk = 0.01 * balance
    size = risk / (atr_val * 100)
    return max(1.0, size)

def open_position(symbol, signal, price, atr_val):
    if symbol in portfolio.positions:
        return

    size = position_size(portfolio.balance, atr_val)

    sl = price - atr_val * 2 if signal == "LONG" else price + atr_val * 2
    tp = price + atr_val * 3 if signal == "LONG" else price - atr_val * 3

    portfolio.positions[symbol] = Position(
        symbol=symbol,
        entry=price,
        size=size,
        side=signal,
        sl=sl,
        tp=tp,
        trailing=sl
    )

    log.info(f"OPEN {symbol} {signal} @ {price:.2f}")

def close_position(symbol, price, reason="EXIT"):
    pos = portfolio.positions[symbol]

    if pos.side == "LONG":
        pnl = (price - pos.entry) * pos.size
    else:
        pnl = (pos.entry - price) * pos.size

    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)

    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} PnL:{pnl:.2f} ({reason})")

def manage_positions(df, symbol):
    price = float(df["c"].iloc[-1])

    if symbol not in portfolio.positions:
        return

    pos = portfolio.positions[symbol]
    atr_val = atr(df)

    # SL
    if (pos.side == "LONG" and price <= pos.sl) or (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price, "SL")
        return

    # TP
    if (pos.side == "LONG" and price >= pos.tp) or (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price, "TP")
        return

# ================= METRICS =================
def metrics():
    if not portfolio.trades:
        return 0, 0, portfolio.balance

    wins = [t for t in portfolio.trades if t > 0]
    winrate = len(wins) / len(portfolio.trades)

    eq = np.array(portfolio.equity)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq

    return winrate, float(np.max(dd)), portfolio.balance

# ================= DASHBOARD =================
def dashboard():
    winrate, dd, eq = metrics()

    open_pos = len(portfolio.positions)

    return f"""
🚀 LEVEL 24 FIXED ENGINE

💰 Equity: {portfolio.balance:.2f}
🟢 WinRate: {winrate:.2%}
📉 Max DD: {dd:.2f}
📦 Trades: {len(portfolio.trades)}
📌 Open Positions: {open_pos}

🔥 SYSTEM: ACTIVE
"""

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("🚀 LEVEL 24 FIXED STARTED\n📡 FULL OBSERVABILITY ACTIVE")

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

                # 🔥 LIVE OUTPUT (FIX اصلی مشکل تو)
                print(f"📡 {symbol} | {signal} | {score:.1f} | {price:.2f} | BAL:{portfolio.balance:.2f}")

                log.info(f"{symbol} | {signal} | {score:.1f} | {price:.2f}")

            # REPORT
            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
