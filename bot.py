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
INTERVAL = 20

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
active_trade = None
last_signal = None
cooldown = 0

# ================= INDICATORS =================
def sma(data, n):
    return sum(data[-n:]) / n if len(data) >= n else None

def rsi(data, n=14):
    if len(data) < n + 1:
        return None

    gains, losses = [], []

    for i in range(1, len(data)):
        diff = data[i] - data[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[-n:]) / n
    avg_loss = sum(losses[-n:]) / n

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================= DATA =================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=100)
    return [c[4] for c in ohlcv]

# ================= SIGNAL =================
def signal(closes):
    fast = sma(closes, 8)
    slow = sma(closes, 21)
    r = rsi(closes, 14)

    if None in [fast, slow, r]:
        return None

    if fast > slow and r < 70:
        return "LONG"

    if fast < slow and r > 30:
        return "SHORT"

    return None

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= TRADE ENGINE =================
def open_trade(side, price):
    global active_trade

    active_trade = {
        "side": side,
        "entry": price,
        "tp": price * (1.003 if side == "LONG" else 0.997),
        "sl": price * (0.998 if side == "LONG" else 1.002)
    }

def close_trade():
    global active_trade
    active_trade = None

def check_trade(price):
    global active_trade

    if not active_trade:
        return

    t = active_trade

    if t["side"] == "LONG":
        if price >= t["tp"]:
            close_trade()
        elif price <= t["sl"]:
            close_trade()

    elif t["side"] == "SHORT":
        if price <= t["tp"]:
            close_trade()
        elif price >= t["sl"]:
            close_trade()

# ================= LOOP =================
async def run():

    global last_signal, cooldown

    await send("🚀 LEVEL 8.8 STARTED\n🧠 TRADE MEMORY ACTIVE")

    while True:

        closes = get_data()
        price = closes[-1]

        # 💣 check open trade first
        check_trade(price)

        # 🟢 cooldown logic
        if cooldown > 0:
            cooldown -= 1
            await asyncio.sleep(INTERVAL)
            continue

        # 🧠 generate signal
        sig = signal(closes)

        # 🚫 no duplicate signal
        if sig == last_signal:
            await asyncio.sleep(INTERVAL)
            continue

        # 🚀 open trade only if none active
        if sig and not active_trade:

            open_trade(sig, price)
            last_signal = sig
            cooldown = 3

            await send(f"""
🚨 NEW TRADE (8.8)

🚀 {SYMBOL}
🟢 {sig}

📍 Entry: {price:.2f}
🎯 TP/SL ACTIVE

🧠 TRADE LOCKED
""".strip())

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
