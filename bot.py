import os
import time
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

print("🔧 ENV CHECK:", TOKEN is not None, CHAT_ID is not None)

SYMBOL = "SOL/USDT"
INTERVAL = 20

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= SAFETY STATE =================
STRATEGIES = {
    "S1": {"fast": 5, "slow": 20},
    "S2": {"fast": 8, "slow": 21},
}

results = defaultdict(lambda: {"wins": 0, "losses": 0, "equity": 1000})

# ================= DATA =================
def sma(data, n):
    return sum(data[-n:]) / n if len(data) >= n else None

def get_data():
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=100)
        return [c[4] for c in ohlcv]
    except Exception as e:
        print("DATA ERROR:", e)
        return None

# ================= SIGNAL =================
def signal(closes, fast, slow):
    f = sma(closes, fast)
    s = sma(closes, slow)

    if f is None or s is None:
        return None

    if f > s:
        return "LONG"
    if f < s:
        return "SHORT"
    return None

# ================= TELEGRAM SAFE =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
        print("MSG SENT:", msg[:30])
    except Exception as e:
        print("TELEGRAM ERROR:", e)

# ================= LOOP =================
async def run():

    print("🚀 BOT LOOP STARTING...")

    await send("🚀 LEVEL 8.7 STARTED")

    while True:

        closes = get_data()
        if not closes:
            await asyncio.sleep(5)
            continue

        price = closes[-1]

        for name, p in STRATEGIES.items():
            sig = signal(closes, p["fast"], p["slow"])

            if sig:
                await send(f"🚨 {name} SIGNAL: {sig} | {price:.2f}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        print("FATAL ERROR:", e)
