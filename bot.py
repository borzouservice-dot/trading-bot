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

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0,
    "equity": 1000
}

# 🧠 RISK ENGINE STATE
risk_state = {
    "loss_streak": 0,
    "cooldown": 0,
    "max_loss_streak": 3,
    "max_drawdown": 0.90,   # 10% stop
    "trading_paused": False
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

# ================= RISK CHECK =================
def risk_check():
    global risk_state, stats

    # 💣 equity protection
    if stats["equity"] < 1000 * risk_state["max_drawdown"]:
        risk_state["trading_paused"] = True

    # 💣 loss streak protection
    if risk_state["loss_streak"] >= risk_state["max_loss_streak"]:
        risk_state["cooldown"] = 10  # skip cycles

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
    global active_trade, stats, risk_state

    entry = active_trade["entry"]
    side = active_trade["side"]

    pnl = (price - entry) if side == "LONG" else (entry - price)

    stats["equity"] += pnl
    stats["total"] += 1

    if pnl > 0:
        stats["wins"] += 1
        risk_state["loss_streak"] = 0
    else:
        stats["losses"] += 1
        risk_state["loss_streak"] += 1

    active_trade = None

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():

    await send("🚀 LEVEL 8.9.2 STARTED\n🛡 RISK ENGINE ACTIVE")

    while True:

        risk_check()

        if risk_state["trading_paused"]:
            await send("🛑 TRADING PAUSED (RISK LIMIT HIT)")
            await asyncio.sleep(60)
            continue

        if risk_state["cooldown"] > 0:
            risk_state["cooldown"] -= 1
            await asyncio.sleep(INTERVAL)
            continue

        closes = get_data()
        price = closes[-1]

        if active_trade:
            # check TP/SL
            t = active_trade
            if t["side"] == "LONG":
                if price >= t["tp"] or price <= t["sl"]:
                    close_trade(price)
            else:
                if price <= t["tp"] or price >= t["sl"]:
                    close_trade(price)

        else:
            sig = signal(closes)

            if sig:
                open_trade(sig, price)

                await send(f"""
🚨 TRADE OPEN (8.9.2)

🚀 {SYMBOL}
🟢 {sig}

📍 Entry: {price:.2f}
🛡 Risk Engine ON
""".strip())

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
