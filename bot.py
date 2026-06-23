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
equity = 1000

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

positions = []

# ================= RISK ENGINE =================
def get_winrate():
    if stats["total"] == 0:
        return 0.5
    return stats["wins"] / stats["total"]

def risk_per_trade():
    wr = get_winrate()

    # 🧠 adaptive risk logic
    if wr > 0.6:
        return 0.02   # 2% aggressive
    elif wr > 0.45:
        return 0.01   # 1% normal
    else:
        return 0.005  # 0.5% safe

def position_size():
    risk = risk_per_trade()
    return equity * risk

# ================= PRICE =================
def get_price():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=1)
    return ohlcv[-1][4]

# ================= POSITION =================
def open_position(side, price):

    size = position_size()

    return {
        "side": side,
        "entry": price,
        "tp": price * (1.003),
        "sl": price * (0.998),
        "size": size,
        "open_time": time.time()
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

# ================= DRAWDOWN CONTROL =================
def risk_guard():

    wr = get_winrate()

    if equity < 800:   # hard stop
        return False

    if wr < 0.3 and stats["total"] > 10:
        return False

    return True

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

    wr = get_winrate() * 100

    return f"""
📊 LEVEL 9.3 RISK ENGINE

💰 Equity: {equity:.2f}
📦 Positions: {len(positions)}

📈 WinRate: {wr:.2f}%
📊 Trades: {stats["total"]}

🧠 Risk per trade: {risk_per_trade()*100:.2f}%
⚖️ Mode: ADAPTIVE RISK
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

    await send("🚀 LEVEL 9.3 STARTED\n🧠 ADAPTIVE RISK ENGINE ACTIVE")

    last_report = time.time()

    while True:

        if not risk_guard():
            await send("🛑 RISK LIMIT ACTIVE - TRADING PAUSED")
            await asyncio.sleep(30)
            continue

        price = get_price()

        check_positions(price)

        # 🟢 open positions
        if len(positions) < 2:

            side = "LONG" if price % 2 > 1 else "SHORT"

            positions.append(open_position(side, price))

            await send(f"""
🚨 NEW POSITION (9.3)

🚀 {SYMBOL}
{side}

📍 Entry: {price:.2f}
📦 Size: {position_size():.2f} USDT
⚖️ Risk: {risk_per_trade()*100:.2f}%
""".strip())

        # 📊 report
        if time.time() - last_report > 60:

            await send(report())
            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
