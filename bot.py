import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
import os

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 10

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

log = logging.getLogger("LEVEL22")

# ================= DATA =================
def get_data(symbol, limit=150):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= SIMPLE STRATEGY CORE =================
def strategy_score(df):

    price = df["c"].iloc[-1]

    ema_fast = df["c"].ewm(span=9).mean().iloc[-1]
    ema_slow = df["c"].ewm(span=21).mean().iloc[-1]

    returns = df["c"].pct_change()
    vol = returns.std()

    score = 50

    if ema_fast > ema_slow:
        score += 20
    else:
        score -= 20

    if vol < 0.002:
        score += 10
    else:
        score -= 10

    if price > df["h"].rolling(20).mean().iloc[-1]:
        score += 10

    if price < df["l"].rolling(20).mean().iloc[-1]:
        score -= 10

    if score >= 70:
        signal = "LONG"
    elif score <= 30:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price

# ================= BACKTEST LIGHT (rolling win estimate) =================
def pseudo_backtest(df):

    closes = df["c"]
    returns = closes.pct_change()

    win_rate = (returns > 0).rolling(20).mean().iloc[-1]

    return float(win_rate)

# ================= ANALYZE ALL SYMBOLS =================
def analyze_all():

    results = []

    for symbol in SYMBOLS:

        df = get_data(symbol)

        signal, score, price = strategy_score(df)
        win_rate = pseudo_backtest(df)

        results.append({
            "symbol": symbol,
            "signal": signal,
            "score": score,
            "price": price,
            "win_rate": win_rate
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)

# ================= FORMAT =================
def format_report(best, all_results):

    msg = f"""
🚀 LEVEL 22 AI PORTFOLIO ENGINE

🏆 BEST SETUP:
{best['symbol']}

{ "🟢 LONG" if best['signal']=="LONG" else "🔴 SHORT" if best['signal']=="SHORT" else "⚪ WAIT" }

📍 Price: {best['price']:.2f}
🧠 Score: {best['score']}/100
📊 Win Est: {best['win_rate']:.2f}

------------------------

📊 ALL MARKETS:

"""

    for r in all_results:
        msg += f"""
• {r['symbol']}
  ➜ {r['signal']} | {r['score']} | WR:{r['win_rate']:.2f}
"""

    msg += "\n📡 Mode: PORTFOLIO AI DECISION ENGINE"

    return msg.strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= LOOP =================
async def run():

    await send("🚀 LEVEL 22 STARTED\n🧠 MULTI-ASSET AI PORTFOLIO ENGINE")

    last_best = None

    while True:

        try:

            results = analyze_all()
            best = results[0]

            log.info(f"BEST: {best['symbol']} | {best['score']}")

            if last_best != best["symbol"]:

                msg = format_report(best, results)
                await send(msg)

                last_best = best["symbol"]

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
