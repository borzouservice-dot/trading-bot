import ccxt
import asyncio
import time
import logging
import pandas as pd
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

log = logging.getLogger("LEVEL14")

# ================= STATE =================
equity = 1000
risk_per_trade = 0.01  # 1%
max_drawdown = -0.1    # -10%

positions = []

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

MAX_POSITIONS = 2

# ================= DATA =================
def get_data(tf="1m", limit=100):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, tf, limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

# ================= INDICATORS =================
def ema(series, n):
    return series.ewm(span=n).mean()

# ================= SIGNAL =================
def analyze(df_1m, df_5m):

    df_1m["ema_fast"] = ema(df_1m["c"], 9)
    df_1m["ema_slow"] = ema(df_1m["c"], 21)

    df_5m["ema_fast"] = ema(df_5m["c"], 9)
    df_5m["ema_slow"] = ema(df_5m["c"], 21)

    last1 = df_1m.iloc[-1]
    last5 = df_5m.iloc[-1]

    trend_1m = last1["ema_fast"] > last1["ema_slow"]
    trend_5m = last5["ema_fast"] > last5["ema_slow"]

    price = last1["c"]

    if trend_1m and trend_5m:
        return "LONG", price

    if not trend_1m and not trend_5m:
        return "SHORT", price

    return "HOLD", price

# ================= POSITION SIZING =================
def position_size(price):

    global equity

    risk_amount = equity * risk_per_trade

    size = risk_amount / price

    return size

# ================= OPEN POSITION =================
def open_position(side, price):

    size = position_size(price)

    return {
        "side": side,
        "entry": price,
        "size": size,
        "tp": price * 1.005,
        "sl": price * 0.995,
        "time": time.time()
    }

# ================= CLOSE =================
def close_position(pos, price):

    global equity, stats

    pnl = (price - pos["entry"]) * pos["size"] if pos["side"] == "LONG" else (pos["entry"] - price) * pos["size"]

    equity += pnl

    stats["total"] += 1

    if pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

# ================= RISK CONTROL =================
def risk_check():

    global equity

    dd = (equity - 1000) / 1000

    if dd < max_drawdown:
        return False

    return True

# ================= CHECK POSITIONS =================
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
📊 LEVEL 14 PRO QUANT SYSTEM

💰 Equity: {equity:.2f}
📦 Positions: {len(positions)}

📈 Trades: {stats["total"]}
🟢 Wins: {stats["wins"]}
🔴 Losses: {stats["losses"]}
📊 WinRate: {wr:.2f}%

⚖️ Risk per trade: {risk_per_trade*100:.1f}%
📉 Drawdown limit: {max_drawdown*100:.1f}%

🧠 Mode: MULTI-TIMEFRAME QUANT
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)

# ================= START =================
async def start_msg():

    msg = f"""
🚀 BOT STARTED

🧠 LEVEL 14 ACTIVE
📡 MULTI-TIMEFRAME ENGINE

⚖️ RISK CONTROL ENABLED
📉 DRAWDOWN PROTECTION ON
""".strip()

    await send(msg)
    log.info("STARTED")

# ================= MAIN LOOP =================
async def run():

    await start_msg()

    last_report = time.time()

    while True:

        try:

            if not risk_check():
                log.warning("🚨 RISK LIMIT HIT - STOP TRADING")
                await asyncio.sleep(INTERVAL)
                continue

            df_1m = get_data("1m")
            df_5m = get_data("5m")

            signal, price = analyze(df_1m, df_5m)

            check_positions(price)

            if signal != "HOLD" and len(positions) < MAX_POSITIONS:

                pos = open_position(signal, price)
                positions.append(pos)

                msg = f"""
🚨 LEVEL 14 TRADE

🚀 {SYMBOL}
📊 {signal}

📍 Entry: {price:.2f}
📦 Size: {pos['size']:.6f}

🎯 TP: {pos['tp']:.2f}
⛔ SL: {pos['sl']:.2f}

⚖️ Multi-Timeframe CONFIRMED
""".strip()

                await send(msg)

                log.info(f"{signal} | {price:.2f}")

            else:
                log.info(f"WAIT | {price:.2f} | Pos: {len(positions)}")

            if time.time() - last_report > 60:

                await send(report())
                last_report = time.time()

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
