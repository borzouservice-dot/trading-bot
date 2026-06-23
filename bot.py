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

SYMBOL = "SOL/USDT"
INTERVAL = 10

FEE_RATE = 0.001  # 0.1% fee (binance spot approx)
SLIPPAGE = 0.0005  # 0.05%

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
equity = 1000
positions = []
stats = {"wins": 0, "losses": 0, "total": 0}

# ================= PRICE =================
def get_price():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=1)
    base_price = ohlcv[-1][4]

    # 📉 market noise simulation
    noise = random.uniform(-0.0003, 0.0003)
    return base_price * (1 + noise)

# ================= EXECUTION ENGINE =================
def apply_slippage(price, side):

    if side == "LONG":
        return price * (1 + SLIPPAGE)
    else:
        return price * (1 - SLIPPAGE)

# ================= POSITION =================
def open_position(side, price):

    exec_price = apply_slippage(price, side)

    return {
        "side": side,
        "entry": exec_price,
        "tp": exec_price * (1.003),
        "sl": exec_price * (0.998),
        "open_time": time.time()
    }

# ================= CLOSE POSITION =================
def close_position(pos, price):

    global equity, stats

    exec_price = apply_slippage(price, pos["side"])

    pnl = (exec_price - pos["entry"]) if pos["side"] == "LONG" else (pos["entry"] - exec_price)

    fee = (pos["entry"] + exec_price) * FEE_RATE

    net_pnl = pnl - fee

    equity += net_pnl

    stats["total"] += 1

    if net_pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

# ================= CHECK =================
def check_positions(price):

    global positions

    new = []

    for p in positions:

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
📊 LEVEL 9.4 EXECUTION ENGINE

💰 Equity: {equity:.2f}
📦 Positions: {len(positions)}

📈 Trades: {stats["total"]}
🟢 Wins: {stats["wins"]}
🔴 Losses: {stats["losses"]}
📊 WinRate: {wr:.2f}%

💸 Fee included: {FEE_RATE*100:.2f}%
📉 Slippage model: ACTIVE
🧠 MARKET REALISM ON
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

    await send("🚀 LEVEL 9.4 STARTED\n📉 EXECUTION + MARKET REALISM ACTIVE")

    last_report = time.time()

    while True:

        price = get_price()

        check_positions(price)

        # 🟢 open positions
        if len(positions) < 2:

            side = "LONG" if random.random() > 0.5 else "SHORT"

            positions.append(open_position(side, price))

            await send(f"""
🚨 NEW EXECUTION (9.4)

🚀 {SYMBOL}
{side}

📍 Market Price: {price:.2f}
📉 Slippage: {SLIPPAGE*100:.2f}%
💸 Fee: {FEE_RATE*100:.2f}%
""".strip())

        # 📊 report
        if time.time() - last_report > 60:

            await send(report())
            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
