import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
from dataclasses import dataclass
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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL26")

# ================= SAFE =================
def f(x):
    try:
        return float(x.iloc[-1]) if hasattr(x, "iloc") else float(x)
    except:
        return 0.0

# ================= DATA =================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    return df

# ================= REGIME =================
def regime(df):
    ema_fast = df["c"].ewm(10).mean().iloc[-1]
    ema_slow = df["c"].ewm(30).mean().iloc[-1]
    vol = df["c"].pct_change().std()

    if abs(ema_fast - ema_slow) / ema_slow > 0.002:
        return "TREND"
    if vol > 0.005:
        return "VOLATILE"
    return "CHOP"

# ================= ATR =================
def atr(df):
    h, l, c = df["h"], df["l"], df["c"]

    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)

    val = tr.rolling(14).mean().iloc[-1]
    return float(val) if not np.isnan(val) else float(c.iloc[-1] * 0.01)

# ================= SIGNAL ENGINE =================
def signal_engine(df):
    price = float(df["c"].iloc[-1])

    ema9 = df["c"].ewm(9).mean().iloc[-1]
    ema21 = df["c"].ewm(21).mean().iloc[-1]
    rsi = 50  # ساده نگه داشتیم (قابل ارتقا)

    vol = df["c"].pct_change().std()
    rg = regime(df)

    score = 50
    signal = "WAIT"

    # trend
    if ema9 > ema21:
        score += 25
        signal = "LONG"
    else:
        score -= 25
        signal = "SHORT"

    # regime filter
    if rg == "CHOP":
        score -= 30
    if rg == "VOLATILE":
        score -= 10

    # volatility filter
    if vol < 0.0015:
        score += 10
    elif vol > 0.005:
        score -= 20

    # final decision
    if score < 75:
        signal = "WAIT"

    return signal, score, price, rg

# ================= EXECUTION =================
@dataclass
class Position:
    symbol: str
    entry: float
    side: str
    sl: float
    tp: float

portfolio = {
    "balance": 1000.0,
    "position": {}
}

def open_pos(symbol, signal, price, atrv):
    if symbol in portfolio["position"]:
        return

    sl = price - atrv*2 if signal=="LONG" else price + atrv*2
    tp = price + atrv*3 if signal=="LONG" else price - atrv*3

    portfolio["position"][symbol] = Position(symbol, price, signal, sl, tp)
    log.info(f"OPEN {symbol} {signal} @ {price}")

def close_pos(symbol, price):
    pos = portfolio["position"][symbol]

    pnl = (price - pos.entry) if pos.side=="LONG" else (pos.entry - price)
    pnl *= 10

    portfolio["balance"] += pnl
    del portfolio["position"][symbol]

    log.info(f"CLOSE {symbol} PnL={pnl:.2f}")

# ================= LOOP =================
async def run():
    while True:
        try:
            for s in SYMBOLS:
                df = get_data(s)

                signal, score, price, rg = signal_engine(df)
                atrv = atr(df)

                if signal != "WAIT":
                    open_pos(s, signal, price, atrv)

                log.info(f"{s} | {signal} | {score:.1f} | {rg} | {price}")

            await asyncio.sleep(INTERVAL)

        except Exception as e:
            log.error(e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
