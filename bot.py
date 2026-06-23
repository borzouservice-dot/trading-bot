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

# ================= DATA =================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=100)
    return [c[4] for c in ohlcv]

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

# ================= TRADE ENGINE =================
def open_trade(side, price):
    global active_trade

    active_trade = {
        "side": side,
        "entry": price,
        "sl": price * (0.998 if side == "LONG" else 1.002),
        "tp1": price * (1.0025 if side == "LONG" else 0.9975),
        "tp2": price * (1.006 if side == "LONG" else 0.994),
        "trail": None,
        "tp1_hit": False
    }

# ================= TRAILING STOP =================
def update_trailing(price):
    global active_trade

    if not active_trade:
        return

    t = active_trade

    if t["side"] == "LONG":

        if price > t["entry"] * 1.002:
            t["trail"] = price * 0.999

        if t["trail"] and price <= t["trail"]:
            close_trade()

    else:

        if price < t["entry"] * 0.998:
            t["trail"] = price * 1.001

        if t["trail"] and price >= t["trail"]:
            close_trade()

# ================= EXIT LOGIC =================
def check_trade(price):
    global active_trade

    if not active_trade:
        return

    t = active_trade

    # 🟢 TP1 partial
    if not t["tp1_hit"]:
        if (t["side"] == "LONG" and price >= t["tp1"]) or \
           (t["side"] == "SHORT" and price <= t["tp1"]):
            t["tp1_hit"] = True

    # 🟢 TP2 full exit
    if (t["side"] == "LONG" and price >= t["tp2"]) or \
       (t["side"] == "SHORT" and price <= t["tp2"]):
        close_trade()

    # ⛔ SL exit
    if (t["side"] == "LONG" and price <= t["sl"]) or \
       (t["side"] == "SHORT" and price >= t["sl"]):
        close_trade()

    update_trailing(price)

# ================= CLOSE TRADE =================
def close_trade():
    global active_trade
    active_trade = None

# ================= UI =================
def format_signal(symbol, side, price):

    emoji = "🟢" if side == "LONG" else "🔴"

    return f"""
🚀 {symbol} SIGNAL (LEVEL 9)

{emoji} {side} ENTRY

📍 Entry: {price:.2f}

🎯 TP1 (partial)
🎯 TP2 (full)
⛔ SL active

📈 Trailing Stop: ON
🧠 Execution Engine ACTIVE
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():

    global last_signal

    await send("🚀 LEVEL 9 STARTED\n🧠 EXECUTION INTELLIGENCE ACTIVE")

    while True:

        closes = get_data()
        price = closes[-1]

        check_trade(price)

        if not active_trade:

            sig = signal(closes)

            if sig and sig != last_signal:

                open_trade(sig, price)
                last_signal = sig

                await send(format_signal(SYMBOL, sig, price))

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
