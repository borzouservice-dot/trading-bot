import time
import random
import asyncio
import logging
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SOL/USDT"
INTERVAL = 20
REPORT_INTERVAL = 300

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STRATEGIES =================
STRATEGIES = {
    "S1": {"fast": 5, "slow": 20},
    "S2": {"fast": 8, "slow": 21},
    "S3": {"fast": 10, "slow": 30},
}

results = defaultdict(lambda: {"wins": 0, "losses": 0, "equity": 1000})

active_trades = {}

# ================= INDICATORS =================
def sma(data, n):
    return sum(data[-n:]) / n if len(data) >= n else None

def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=100)
    return [c[4] for c in ohlcv]

# ================= SIGNAL =================
def signal(closes, fast, slow):
    f = sma(closes, fast)
    s = sma(closes, slow)

    if None in [f, s]:
        return None

    if f > s:
        return "LONG"
    if f < s:
        return "SHORT"
    return None

# ================= EXECUTION SIM =================
def open_trade(strategy, side, price):
    results[strategy]["entry"] = price
    results[strategy]["side"] = side

def close_trade(strategy, price):
    entry = results[strategy]["entry"]
    side = results[strategy]["side"]

    pnl = price - entry if side == "LONG" else entry - price

    if pnl > 0:
        results[strategy]["wins"] += 1
        results[strategy]["equity"] += pnl
    else:
        results[strategy]["losses"] += 1
        results[strategy]["equity"] -= abs(pnl)

# ================= SCORING =================
def score(strategy):
    w = results[strategy]["wins"]
    l = results[strategy]["losses"]
    t = w + l

    if t == 0:
        return 0

    winrate = w / t
    equity = results[strategy]["equity"]

    return winrate * 0.7 + (equity / 1000) * 0.3

def best_strategy():
    return max(STRATEGIES.keys(), key=lambda s: score(s))

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():

    await send("""
🚀 LEVEL 8.7 STARTED

🧠 STRATEGY OPTIMIZER ACTIVE
📊 MULTI-STRATEGY MODE ON
""")

    last_report = time.time()

    while True:

        closes = get_data()
        price = closes[-1]

        best = best_strategy()
        params = STRATEGIES[best]

        sig = signal(closes, params["fast"], params["slow"])

        if sig:
            open_trade(best, sig, price)

        # simulate close (simple)
        for s in STRATEGIES:
            if "entry" in results[s]:
                close_trade(s, price)

        if time.time() - last_report > REPORT_INTERVAL:

            msg = "📊 STRATEGY REPORT\n\n"

            for s in STRATEGIES:
                msg += f"""
{s}
Win: {results[s]['wins']}
Loss: {results[s]['losses']}
Equity: {results[s]['equity']:.2f}
Score: {score(s):.2f}
"""

            msg += f"\n🏆 BEST: {best_strategy()}"

            await send(msg)

            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
