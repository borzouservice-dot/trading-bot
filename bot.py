import ccxt
import asyncio
import time
import random
import logging
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
import os

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

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

log = logging.getLogger("LEVEL12.1")

# ================= STATE =================
positions = []
equity = 1000

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

MAX_POSITIONS = 2

# ================= PRICE =================
def get_price():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=1)
    return ohlcv[-1][4]

# ================= SIGNAL ENGINE =================
def signal_engine(price):

    r = random.random()

    if r > 0.55:
        return "LONG"
    elif r < 0.45:
        return "SHORT"
    return "HOLD"

# ================= POSITION =================
def open_position(side, price):

    return {
        "side": side,
        "entry": price,
        "tp": price * 1.003,
        "sl": price * 0.998,
        "time": time.time()
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

    wr = (stats["wins"] / stats["total"] * 100) if stats["total"] else 0

    return f"""
📊 LEVEL 12.1 STATUS

💰 Equity: {equity:.2f}
📦 Positions: {len(positions)}

📈 Trades: {stats["total"]}
🟢 Wins: {stats["wins"]}
🔴 Losses: {stats["losses"]}
📊 WinRate: {wr:.2f}%

⚡ Mode: VISUAL ENGINE ACTIVE
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= START MESSAGE =================
async def start_message():

    msg = f"""
🚀 BOT STARTED

🧠 LEVEL 12.1 ACTIVE
📡 SYMBOL: {SYMBOL}
⚡ MODE: VISUAL SIGNAL ENGINE

📊 SYSTEM ONLINE
    """.strip()

    await send(msg)
    log.info("BOT STARTED")

# ================= LOOP =================
async def run():

    await start_message()

    last_report = time.time()

    while True:

        try:

            price = get_price()

            check_positions(price)

            signal = signal_engine(price)

            # 🚨 anti-overtrade
            if signal != "HOLD" and len(positions) < MAX_POSITIONS:

                pos = open_position(signal, price)
                positions.append(pos)

                msg = f"""
🚨 NEW SIGNAL (12.1)

🚀 {SYMBOL}
📊 {signal}

📍 Entry: {price:.2f}
🎯 TP: {pos['tp']:.2f}
⛔ SL: {pos['sl']:.2f}

📦 Positions: {len(positions)}/{MAX_POSITIONS}
""".strip()

                await send(msg)

                log.info(f"{signal} | {price:.2f}")

            else:
                log.info(f"LIVE | {price:.2f} | Pos: {len(positions)}")

            if time.time() - last_report > 60:

                await send(report())
                last_report = time.time()

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
