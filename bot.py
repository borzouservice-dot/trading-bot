import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 30

exchange = ccxt.binance({"enableRateLimit": True})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL27")

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df = df.apply(pd.to_numeric)
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

# ================= CONFIDENCE ENGINE =================
def confidence(df):
    ema9 = df["c"].ewm(9).mean().iloc[-1]
    ema21 = df["c"].ewm(21).mean().iloc[-1]

    trend_score = 60 if ema9 > ema21 else 40

    momentum = df["c"].pct_change().tail(10).mean()
    momentum_score = 60 if momentum > 0 else 40

    vol = df["c"].pct_change().std()
    vol_score = 80 if vol < 0.003 else 50 if vol < 0.005 else 30

    reg = regime(df)
    reg_score = 80 if reg == "TREND" else 40 if reg == "VOLATILE" else 20

    total = (
        trend_score * 0.35 +
        momentum_score * 0.25 +
        vol_score * 0.20 +
        reg_score * 0.20
    )

    return round(total, 1), reg

# ================= KELLY SIZE =================
def kelly(winrate, balance, confidence):
    base_risk = 0.01

    adj = (confidence / 100)
    risk = base_risk * adj

    return balance * risk

# ================= STRATEGY =================
def signal(df):
    price = df["c"].iloc[-1]

    ema9 = df["c"].ewm(9).mean().iloc[-1]
    ema21 = df["c"].ewm(21).mean().iloc[-1]

    if ema9 > ema21:
        return "LONG", price
    elif ema9 < ema21:
        return "SHORT", price
    return "WAIT", price

# ================= STATE =================
state = {
    "balance": 1000.0,
    "trades": 0
}

# ================= EXECUTION =================
def execute(symbol, sig, price, conf, reg):

    if conf < 78:
        return

    if reg == "CHOP":
        return

    if sig == "WAIT":
        return

    risk_amount = kelly(0.55, state["balance"], conf)

    pnl = np.random.normal(0.002, 0.01) * risk_amount

    state["balance"] += pnl
    state["trades"] += 1

    log.info(f"{symbol} | {sig} | Conf:{conf} | Reg:{reg} | PnL:{pnl:.2f} | Bal:{state['balance']:.2f}")

# ================= LOOP =================
async def run():

    while True:
        try:
            for s in SYMBOLS:

                df = get_data(s)

                conf, reg = confidence(df)
                sig, price = signal(df)

                execute(s, sig, price, conf, reg)

            await asyncio.sleep(INTERVAL)

        except Exception as e:
            log.error(e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run())
