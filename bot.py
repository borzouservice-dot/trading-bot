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
REPORT_INTERVAL = 600

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("V4.1_PRO")

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
        self.last_signal = {}

portfolio = Portfolio()

# ================= TELEGRAM =================
def send(msg):
    try:
        bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df["c"] = df["c"].astype(float)
    return df

# ================= STRATEGY =================
def strategy(df):
    price = df["c"].iloc[-1]

    ema9 = df["c"].ewm(span=9).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21).mean().iloc[-1]

    vol = df["c"].pct_change().tail(30).std()

    score = 50

    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"

    if vol < 0.0018:
        score += 15
    elif vol > 0.004:
        score -= 20

    if score < 70:
        signal = "WAIT"

    return signal, score, price

# ================= POSITION =================
def open_position(symbol, signal, price):
    if symbol in portfolio.positions:
        return

    sl = price * (0.99 if signal == "LONG" else 1.01)
    tp = price * (1.03 if signal == "LONG" else 0.97)

    portfolio.positions[symbol] = Position(symbol, price, 10, signal, sl, tp)

    send(f"""
🚀 OPEN POSITION

Symbol: {symbol}
Side: {signal}
Entry: {price:.2f}
SL: {sl:.2f}
TP: {tp:.2f}
""")

def close_position(symbol, price, reason):
    pos = portfolio.positions[symbol]

    pnl = (price - pos.entry) * pos.size if pos.side == "LONG" else (pos.entry - price) * pos.size

    portfolio.balance += pnl
    portfolio.trades.append(pnl)

    del portfolio.positions[symbol]

    send(f"""
❌ CLOSE POSITION ({reason})

Symbol: {symbol}
Side: {pos.side}
PnL: {pnl:.2f}
Balance: {portfolio.balance:.2f}
""")

# ================= MANAGE =================
def manage(symbol, price):
    if symbol not in portfolio.positions:
        return

    pos = portfolio.positions[symbol]

    if pos.side == "LONG":
        if price <= pos.sl:
            close_position(symbol, price, "SL")
        elif price >= pos.tp:
            close_position(symbol, price, "TP")

    else:
        if price >= pos.sl:
            close_position(symbol, price, "SL")
        elif price <= pos.tp:
            close_position(symbol, price, "TP")

# ================= SIGNAL CONTROL =================
def signal_controller(symbol, signal):
    last = portfolio.last_signal.get(symbol)

    # فقط اگر تغییر کرده باشد
    if last == signal:
        return False

    portfolio.last_signal[symbol] = signal
    return True

# ================= LOOP =================
async def run():
    send("🚀 V4.1 PRO STARTED")

    last_report = time.time()

    while True:
        try:
            for s in SYMBOLS:

                df = get_data(s)
                signal, score, price = strategy(df)

                manage(s, price)

                # signal change filter
                if signal_controller(s, signal):

                    log.info(f"NEW SIGNAL {s} {signal}")

                    if signal != "WAIT":
                        open_position(s, signal, price)

                log.info(f"{s} | {signal} | {score:.1f} | {price:.2f}")

            # periodic report
            if time.time() - last_report > REPORT_INTERVAL:
                send(f"""
📊 V4.1 REPORT

Balance: {portfolio.balance:.2f}
Open Positions: {len(portfolio.positions)}
Trades: {len(portfolio.trades)}
""")
                last_report = time.time()

        except Exception as e:
            log.error(f"Loop error: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
