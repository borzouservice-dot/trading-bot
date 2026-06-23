import os
import time
import asyncio
import logging
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
REPORT_INTERVAL = 300

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= PAPER ACCOUNT =================
balance = 1000.0
equity = 1000.0

active_trade = None

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

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

# ================= STRATEGY =================
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

# ================= POSITION SIZE =================
def position_size(price):
    risk = equity * 0.02  # 2%
    return risk / price

# ================= PAPER TRADE =================
def open_trade(side, price):
    global active_trade

    qty = position_size(price)

    active_trade = {
        "side": side,
        "entry": price,
        "qty": qty,
        "sl": price * (0.998 if side == "LONG" else 1.002),
        "tp": price * (1.003 if side == "LONG" else 1.997)
    }

def close_trade(price, win):
    global active_trade, equity, stats

    entry = active_trade["entry"]
    qty = active_trade["qty"]

    pnl = (price - entry) * qty if active_trade["side"] == "LONG" else (entry - price) * qty

    equity += pnl

    stats["total"] += 1
    if win:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

    active_trade = None

# ================= CHECK TRADE =================
def check_trade(price):
    global active_trade

    if not active_trade:
        return

    t = active_trade

    if t["side"] == "LONG":
        if price >= t["tp"]:
            close_trade(price, True)
        elif price <= t["sl"]:
            close_trade(price, False)

    elif t["side"] == "SHORT":
        if price <= t["tp"]:
            close_trade(price, True)
        elif price >= t["sl"]:
            close_trade(price, False)

# ================= REPORT =================
def report():
    if stats["total"] == 0:
        return "📊 No trades yet"

    winrate = (stats["wins"] / stats["total"]) * 100

    return f"""
📊 PAPER TRADING REPORT

💰 Equity: {equity:.2f} USDT
📈 Winrate: {winrate:.2f}%

✅ Wins: {stats['wins']}
❌ Losses: {stats['losses']}
📦 Trades: {stats['total']}
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():

    await send(f"""
🚀 PAPER TRADING STARTED

🧠 LEVEL 8.6 ACTIVE
🚀 SYMBOL: {SYMBOL}

💰 VIRTUAL BALANCE: {equity}
""".strip())

    last_report = time.time()

    while True:

        closes = get_data()
        price = closes[-1]

        check_trade(price)

        if not active_trade:
            sig = signal(closes)

            if sig:
                open_trade(sig, price)

                await send(f"""
🚨 PAPER TRADE

🚀 {SYMBOL}
🟢 {sig}

📍 Entry: {price:.2f}
💰 Equity: {equity:.2f}

🧠 LEVEL 8.6
""".strip())

        if time.time() - last_report > REPORT_INTERVAL:
            await send(report())
            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
