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
INTERVAL = 10  # 🔥 faster for live monitoring

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
active_trade = None
last_update_time = 0

# ================= DATA =================
def get_price():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=1)
    return ohlcv[-1][4]

# ================= TRADE =================
def open_trade(side, price):
    return {
        "side": side,
        "entry": price,
        "tp1": price * (1.002),
        "tp2": price * (1.006),
        "sl": price * (0.998 if side == "LONG" else 1.002),
        "trail": None,
        "tp1_hit": False
    }

def pnl(trade, price):
    if trade["side"] == "LONG":
        return price - trade["entry"]
    else:
        return trade["entry"] - price

# ================= TRAILING =================
def update_trailing(trade, price):
    if trade["side"] == "LONG":
        if price > trade["entry"] * 1.002:
            trade["trail"] = price * 0.999

    else:
        if price < trade["entry"] * 0.998:
            trade["trail"] = price * 1.001

# ================= STATUS =================
def trade_status(trade, price):

    profit = pnl(trade, price)

    if profit > 0:
        status = "IN PROFIT 🟢"
    elif profit < 0:
        status = "IN LOSS 🔴"
    else:
        status = "BREAK EVEN ⚪"

    tp1_progress = abs((price - trade["entry"]) / (trade["tp1"] - trade["entry"])) * 100

    return f"""
📊 LIVE TRADE STATUS (9.1)

{trade['side']} {status}

📍 Entry: {trade['entry']:.2f}
💰 Price: {price:.2f}
📈 PnL: {profit:.4f}

🎯 TP1 Progress: {tp1_progress:.1f}%

🛡 SL: {trade['sl']:.2f}
📉 Trail: {trade['trail'] if trade['trail'] else 'OFF'}

🧠 LIVE EXECUTION MODE
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():

    global active_trade, last_update_time

    await send("🚀 LEVEL 9.1 STARTED\n📊 LIVE TRADE MONITOR ACTIVE")

    while True:

        price = get_price()

        # 🟢 open trade once
        if not active_trade:
            active_trade = open_trade("LONG", price)

            await send(f"""
🚨 TRADE OPEN (9.1)

🚀 {SYMBOL}
🟢 LONG

📍 Entry: {price:.2f}
""".strip())

        # 📊 update live every few seconds
        if active_trade and time.time() - last_update_time > 10:

            update_trailing(active_trade, price)

            await send(trade_status(active_trade, price))

            last_update_time = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
