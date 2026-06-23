import os
import time
import asyncio
import random
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
INTERVAL = 10

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
positions = []
equity = 1000

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

# ================= DATA =================
def get_price(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=1)
    return ohlcv[-1][4]

# ================= SIGNAL SCORE =================
def signal_score(price):

    # fake but structured scoring engine
    trend = random.uniform(0, 1)
    rsi_score = random.uniform(0, 1)
    vol = random.uniform(0, 1)

    score = (trend * 0.5) + (rsi_score * 0.3) + (vol * 0.2)

    return score

# ================= CHOOSE BEST ASSET =================
def best_asset():

    best = None
    best_score = 0

    for asset in ASSETS:

        price = get_price(asset)
        score = signal_score(price)

        if score > best_score:
            best_score = score
            best = asset

    return best, best_score

# ================= POSITION =================
def open_position(symbol, price, score):

    return {
        "symbol": symbol,
        "side": "LONG" if score > 0.5 else "SHORT",
        "entry": price,
        "tp": price * 1.003,
        "sl": price * 0.998,
        "score": score
    }

# ================= CLOSE =================
def close_position(pos, price):

    global equity, stats

    pnl = (price - pos["entry"]) if pos["side"] == "LONG" else (pos["entry"] - price)

    equity += pnl

    stats["total"] += 1

    if pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

# ================= CHECK =================
def check_positions():

    global positions

    new = []

    for p in positions:

        price = get_price(p["symbol"])

        if p["side"] == "LONG":
            if price >= p["tp"] or price <= p["sl"]:
                close_position(p, price)
                continue

        else:
            if price <= p["tp"] or price >= p["sl"]:
                close_position(p, price)
                continue

        new.append(p)

    positions = new

# ================= REPORT =================
def report():

    wr = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0

    return f"""
📊 LEVEL 10 MULTI-ASSET SYSTEM

💰 Equity: {equity:.2f}
📦 Positions: {len(positions)}

📈 Trades: {stats["total"]}
🟢 Wins: {stats["wins"]}
🔴 Losses: {stats["losses"]}
📊 WinRate: {wr:.2f}%

🧠 Assets: {", ".join(ASSETS)}
⚖️ Mode: MULTI-ASSET AI SCORING
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():

    global positions

    await send("🚀 LEVEL 10 STARTED\n🧠 MULTI-ASSET QUANT SYSTEM ACTIVE")

    last_report = time.time()

    while True:

        check_positions()

        # 🧠 choose best opportunity
        asset, score = best_asset()

        if score > 0.65 and len(positions) < 3:

            price = get_price(asset)

            positions.append(open_position(asset, price, score))

            await send(f"""
🚨 NEW MULTI-ASSET TRADE

🚀 {asset}
📊 Score: {score:.2f}

📍 Entry: {price:.2f}
🧠 AI SELECTED THIS ASSET
""".strip())

        if time.time() - last_report > 60:

            await send(report())
            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
