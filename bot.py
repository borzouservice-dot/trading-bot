import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
from dataclasses import dataclass
from typing import Optional

# ================= CONFIG =================
SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 30

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL24")

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
        self.positions: dict[str, Position] = {}
        self.equity_curve = [1000.0]
        self.trades = []

portfolio = Portfolio()

# ================= DATA =================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    df["c"] = df["c"].astype(float)
    return df

# ================= INDICATORS =================
def atr(df, period=14):
    high = df["h"]
    low = df["l"]
    close = df["c"]

    tr = np.maximum(high - low,
         np.maximum(abs(high - close.shift()), abs(low - close.shift())))

    return tr.rolling(period).mean().iloc[-1]

# ================= STRATEGY =================
def strategy(df):

    price = df["c"].iloc[-1]

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

    return signal, score, float(price)

# ================= POSITION SIZING =================
def position_size(balance, atr_val):

    risk_per_trade = 0.01  # 1%

    risk_amount = balance * risk_per_trade

    size = risk_amount / (atr_val * 100)

    return max(1, size)

# ================= EXECUTION =================
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

def close_position(symbol, price, reason="TP/SL"):

    pos = portfolio.positions[symbol]

    if pos.side == "LONG":
        pnl = (price - pos.entry) * pos.size
    else:
        pnl = (pos.entry - price) * pos.size

    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity_curve.append(portfolio.balance)

    del portfolio.positions[symbol]

    log.info(f"CLOSE {symbol} PnL:{pnl:.2f} ({reason})")

# ================= TRAILING STOP =================
def update_trailing(pos, price, atr_val):

    if pos.side == "LONG":
        pos.trailing = max(pos.trailing, price - atr_val)
    else:
        pos.trailing = min(pos.trailing, price + atr_val)

# ================= RISK ENGINE =================
def manage_positions(df, symbol):

    price = df["c"].iloc[-1]

    if symbol not in portfolio.positions:
        return

    pos = portfolio.positions[symbol]

    atr_val = atr(df)

    update_trailing(pos, price, atr_val)

    # SL hit
    if (pos.side == "LONG" and price <= pos.sl) or \
       (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price, "SL")
        return

    # TP hit
    if (pos.side == "LONG" and price >= pos.tp) or \
       (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price, "TP")
        return

    # trailing stop
    if (pos.side == "LONG" and price <= pos.trailing) or \
       (pos.side == "SHORT" and price >= pos.trailing):
        close_position(symbol, price, "TRAIL")
        return

# ================= METRICS =================
def metrics():

    if not portfolio.trades:
        return 0, 0, portfolio.balance

    wins = [t for t in portfolio.trades if t > 0]

    winrate = len(wins) / len(portfolio.trades)

    eq = np.array(portfolio.equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq

    return winrate, float(np.max(dd)), portfolio.balance

# ================= LOOP =================
async def run():

    log.info("🚀 LEVEL 24 STARTED")

    while True:

        try:

            for symbol in SYMBOLS:

                df = get_data(symbol)

                signal, score, price = strategy(df)

                atr_val = atr(df)

                manage_positions(df, symbol)

                if signal != "WAIT":
                    open_position(symbol, signal, price, atr_val)

                log.info(f"{symbol} | {signal} | {score:.1f} | {price:.2f}")

            await asyncio.sleep(INTERVAL)

        except Exception as e:
            log.error(e)
            await asyncio.sleep(5)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
