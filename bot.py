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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("LEVEL26")

# ================= SAFE VALUE =================
def v(x):
    try:
        if isinstance(x, pd.Series):
            return float(x.iloc[-1])
        return float(x)
    except:
        return 0.0

# ================= DATA =================
def get_data(symbol):
    df = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    return df

# ================= INDICATORS =================
def indicators(df):
    close = df["c"]

    ema9 = close.ewm(span=9).mean().iloc[-1]
    ema21 = close.ewm(span=21).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]

    rsi = compute_rsi(close, 14)
    vol = close.pct_change().tail(30).std()

    return ema9, ema21, ema50, rsi, vol

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs)).iloc[-1]

# ================= MARKET REGIME =================
def regime(df):
    vol = df["c"].pct_change().tail(50).std()
    trend = abs(df["c"].ewm(20).mean().iloc[-1] - df["c"].ewm(50).mean().iloc[-1])

    if vol < 0.002:
        return "SLOW"
    if vol > 0.01:
        return "CHAOS"
    if trend > 0:
        return "TREND"
    return "RANGE"

# ================= SIGNAL ENGINE =================
def signal_engine(df):
    price = v(df["c"].iloc[-1])
    ema9, ema21, ema50, rsi, vol = indicators(df)
    reg = regime(df)

    score = 50
    signal = "WAIT"

    # 1. Trend structure
    if ema9 > ema21 > ema50:
        score += 35
        signal = "LONG"
    elif ema9 < ema21 < ema50:
        score += 35
        signal = "SHORT"
    else:
        score -= 20

    # 2. RSI filter (important)
    if rsi > 70:
        score -= 20
    if rsi < 30:
        score += 10

    # 3. Market regime filter (VERY IMPORTANT)
    if reg in ["CHAOS", "SLOW"]:
        score -= 30

    # 4. volatility sanity
    if vol > 0.01:
        score -= 25

    # FINAL DECISION GATE (critical)
    if score < 75:
        signal = "WAIT"

    confidence = min(100, max(0, score))

    return signal, confidence, price, reg

# ================= LOG =================
def log_line(symbol, signal, conf, price, reg):
    log.info(f"{symbol} | {signal} | {conf:.1f} | {price:.2f} | {reg}")

# ================= DASHBOARD =================
def dashboard(results):
    txt = "🚀 LEVEL 26 PROFESSIONAL SIGNAL ENGINE\n\n"

    for r in results:
        txt += f"""
📊 {r['symbol']}
➡ Signal: {r['signal']}
🧠 Confidence: {r['conf']:.1f}
📍 Price: {r['price']:.2f}
📡 Regime: {r['reg']}
-------------------------
"""
    return txt

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():
    await send("🚀 LEVEL 26 STARTED\nPRO TRADING ENGINE ACTIVE")

    last_report = time.time()

    while True:
        try:
            results = []

            for s in SYMBOLS:
                df = get_data(s)

                signal, conf, price, reg = signal_engine(df)

                log_line(s, signal, conf, price, reg)

                results.append({
                    "symbol": s,
                    "signal": signal,
                    "conf": conf,
                    "price": price,
                    "reg": reg
                })

            # فقط اگر سیگنال قوی بود گزارش بده
            strong = [r for r in results if r["conf"] >= 80]

            if time.time() - last_report > REPORT_INTERVAL and strong:
                await send(dashboard(strong))
                last_report = time.time()

        except Exception as e:
            log.exception(e)

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
