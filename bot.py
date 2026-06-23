import os
import time
import asyncio
import csv
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

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0,
    "equity": 1000
}

TRADE_FILE = "trades.csv"

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
    global active_trade, stats

    entry = active_trade["entry"]
    side = active_trade["side"]

    # 📊 PnL calculation
    pnl = (price - entry) if side == "LONG" else (entry - price)

    stats["equity"] += pnl
    stats["total"] += 1

    if pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

    # 💾 log trade
    write_trade(side, entry, price, pnl)

    active_trade = None

def write_trade(side, entry, exit_price, pnl):
    file_exists = os.path.isfile(TRADE_FILE)

    with open(TRADE_FILE, "a", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["time", "side", "entry", "exit", "pnl"])

        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            side,
            entry,
            exit_price,
            pnl
        ])

def check_trade(price):
    global active_trade

    if not active_trade:
        return

    t = active_trade

    if t["side"] == "LONG":
        if price >= t["tp"]:
            close_trade(price)
        elif price <= t["sl"]:
            close_trade(price)

    elif t["side"] == "SHORT":
        if price <= t["tp"]:
            close_trade(price)
        elif price >= t["sl"]:
            close_trade(price)

# ================= REPORT =================
def report():
    if stats["total"] == 0:
        return "📊 No trades yet"

    winrate = (stats["wins"] / stats["total"]) * 100

    return f"""
📊 PERFORMANCE REPORT (LEVEL 8.9)

💰 Equity: {stats['equity']:.2f}
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
🚀 LEVEL 8.9 STARTED

🧠 REAL PnL ENGINE ACTIVE
📊 TRADE TRACKING ON
🚀 SYMBOL: {SYMBOL}
""".strip())

    last_report = time.time()

    while True:

        closes = get_data()
        price = closes[-1]

        check_trade(price)

        # open new trade
        if not active_trade:
            sig = signal(closes)

            if sig:
                open_trade(sig, price)

                await send(f"""
🚨 NEW TRADE (8.9)

🚀 {SYMBOL}
🟢 {sig}

📍 Entry: {price:.2f}
🎯 TP/SL ACTIVE
""".strip())

        # periodic report
        if time.time() - last_report > 300:
            await send(report())
            last_report = time.time()

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
