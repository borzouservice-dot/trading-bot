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
def get_data(timeframe="1m"):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe, limit=100)
    return [c[4] for c in ohlcv]

# ================= INDICATOR =================
def sma(data, n):
    return sum(data[-n:]) / n if len(data) >= n else None

# ================= SINGLE TF SIGNAL =================
def single_signal(closes):
    fast = sma(closes, 8)
    slow = sma(closes, 21)

    if fast is None or slow is None:
        return None

    if fast > slow:
        return "LONG"
    elif fast < slow:
        return "SHORT"
    return None

# ================= MULTI TIMEFRAME ENGINE =================
def get_mtf_signal():

    s1 = single_signal(get_data("1m"))
    s2 = single_signal(get_data("5m"))
    s3 = single_signal(get_data("15m"))

    signals = [s1, s2, s3]

    long_count = signals.count("LONG")
    short_count = signals.count("SHORT")

    # 🔥 Confidence logic
    if long_count == 3:
        return "LONG", 95
    if short_count == 3:
        return "SHORT", 95

    if long_count == 2:
        return "LONG", 75
    if short_count == 2:
        return "SHORT", 75

    if long_count == 1 and short_count == 0:
        return "LONG", 55

    if short_count == 1 and long_count == 0:
        return "SHORT", 55

    return None, 0

# ================= TRADE ENGINE =================
def open_trade(side, price):
    global active_trade

    active_trade = {
        "side": side,
        "entry": price,
        "tp": price * (1.003 if side == "LONG" else 0.997),
        "sl": price * (0.998 if side == "LONG" else 1.002)
    }

def close_trade(price):
    global active_trade
    active_trade = None

def check_trade(price):
    global active_trade

    if not active_trade:
        return

    t = active_trade

    if t["side"] == "LONG":
        if price >= t["tp"] or price <= t["sl"]:
            close_trade(price)
    else:
        if price <= t["tp"] or price >= t["sl"]:
            close_trade(price)

# ================= UI FORMAT =================
def format_signal(symbol, side, price, confidence):

    emoji = "🟢" if side == "LONG" else "🔴"

    bar = "█" * int(confidence / 10)

    return f"""
🚀 {symbol} SIGNAL (8.9.4 MTF)

{emoji} {side} ENTRY

📍 Entry: {price:.2f}
📊 Confidence: {confidence}%
📈 Strength: {bar}

🧠 Timeframes: 1m / 5m / 15m

📦 Status: VALIDATED SIGNAL
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

    await send("🚀 LEVEL 8.9.4 STARTED\n🧠 MULTI-TIMEFRAME AI ACTIVE")

    while True:

        closes = get_data("1m")
        price = closes[-1]

        check_trade(price)

        side, confidence = get_mtf_signal()

        # ❌ filter weak signals
        if confidence < 70:
            await asyncio.sleep(INTERVAL)
            continue

        # 🚫 avoid duplicates
        if side == last_signal:
            await asyncio.sleep(INTERVAL)
            continue

        if side and not active_trade:

            open_trade(side, price)
            last_signal = side

            await send(format_signal(SYMBOL, side, price, confidence))

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
