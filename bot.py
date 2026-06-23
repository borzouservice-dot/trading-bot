import os
import time
import asyncio
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SOL/USDT"
INTERVAL = 10

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
positions = []
history = []

equity = 1000  # starting capital

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

# ================= PRICE =================
def get_price():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=1)
    return ohlcv[-1][4]

# ================= POSITION =================
def open_position(side, price):

    return {
        "side": side,
        "entry": price,
        "tp": price * (1.003),
        "sl": price * (0.998),
        "size": equity * 0.1,  # 10% risk
        "open_time": time.time()
    }

# ================= CLOSE =================
def close_position(pos, price):

    global equity, stats, history

    pnl = (price - pos["entry"]) if pos["side"] == "LONG" else (pos["entry"] - price)

    equity += pnl

    stats["total"] += 1

    if pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

    history.append({
        "side": pos["side"],
        "entry": pos["entry"],
        "exit": price,
        "pnl": pnl
    })

# ================= CHECK POSITIONS =================
def check_positions(price):

    global positions

    new_positions = []

    for p in positions:

        if p["side"] == "LONG":

            if price >= p["tp"] or price <= p["sl"]:
                close_position(p, price)
                continue

        else:

            if price <= p["tp"] or price >= p["sl"]:
                close_position(p, price)
                continue

        new_positions.append(p)

    positions = new_positions

# ================= STATS =================
def report():

    wr = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0

    return f"""
📊 PORTFOLIO REPORT (9.2)

💰 Equity: {equity:.2f}
📦 Open Positions: {len(positions)}
📈 Total Trades: {stats["total"]}
🟢 Wins: {stats["wins"]}
🔴 Losses: {stats["losses"]}
📊 WinRate: {wr:.2f}%

🧠 SYSTEM: MULTI-POSITION ACTIVE
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

    await send("🚀 LEVEL 9.2 STARTED\n📊 PORTFOLIO ENGINE ACTIVE")

    last_report = time.time()

    while True:

        price = get_price()

        check_positions(price)

        # 🟢 open new positions (demo logic)
        if len(positions) < 3:
            side = "LONG" if price % 2 > 1 else "SHORT"

            positions.append(open_position(side, price))

            await send(f"""
🚨 NEW POSITION (9.2)

🚀 {SYMBOL}
{side}

📍 Entry: {price:.2f}
📦 Size: 10% equity
""".strip())

        # 📊 periodic report
        if time.time() - last_report > 60:

            await send(report())
            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
