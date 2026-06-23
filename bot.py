import os
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "BTC/USDT"

INTERVAL = 20
STATUS_INTERVAL = 300

MA_FAST = 8
MA_SLOW = 21
RSI_PERIOD = 14
ATR_PERIOD = 14

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

log = logging.getLogger(__name__)

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
active_trades = []
stats = {"wins": 0, "losses": 0, "total": 0}


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


def atr(highs, lows, closes, n=14):
    if len(closes) < n + 1:
        return None

    trs = []
    for i in range(1, len(closes)):
        trs.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        ))

    return sum(trs[-n:]) / n


# ================= DATA =================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe="1m", limit=100)

    closes = [c[4] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]

    return closes, highs, lows


# ================= STRATEGY =================
def signal_engine(price, closes, highs, lows):

    fast = sma(closes, MA_FAST)
    slow = sma(closes, MA_SLOW)
    r = rsi(closes, RSI_PERIOD)
    a = atr(highs, lows, closes, ATR_PERIOD)

    if None in [fast, slow, r, a]:
        return None

    # ❌ بازار رنج = هیچ سیگنال
    if abs(fast - slow) < a * 0.25:
        return None

    # 🟢 LONG
    if fast > slow and r < 70:

        sl = price - (a * 1.5)
        tp = [price + a, price + a * 2, price + a * 3]

        return build_signal(price, "LONG", r, sl, tp)

    # 🔴 SHORT
    if fast < slow and r > 30:

        sl = price + (a * 1.5)
        tp = [price - a, price - a * 2, price - a * 3]

        return build_signal(price, "SHORT", r, sl, tp)

    return None


def build_signal(price, direction, rsi_val, sl, tp):

    return {
        "symbol": SYMBOL,
        "direction": direction,
        "entry": price,
        "rsi": rsi_val,
        "sl": sl,
        "tp": tp,
        "confidence": 0.8,
        "status": "OPEN",
        "time": time.time()
    }


# ================= FORMAT =================
def format_signal(s):

    emoji = "🟢" if s["direction"] == "LONG" else "🔴"

    risk = abs(s["entry"] - s["sl"])

    tp_text = ""
    for i, t in enumerate(s["tp"], 1):
        rr = abs(t - s["entry"]) / risk
        tp_text += f"• TP{i}: {t:.2f} ({rr:.1f}R)\n"

    return f"""
🚀 BTC/USDT

{emoji} {s['direction']} SIGNAL

📍 Entry: {s['entry']:.2f}
📊 RSI: {s['rsi']:.1f}
🎯 Confidence: {s['confidence']*100:.0f}%

━━━━━━━━━━━━━━━
⛔ Stop Loss: {s['sl']:.2f}

🎯 Take Profits:
{tp_text}
━━━━━━━━━━━━━━━
🧠 Engine: ATR + Trend Filter + RSI
⚡ Mode: FINAL PRO SYSTEM
🕒 {datetime.utcnow().strftime('%H:%M UTC')}
""".strip()


# ================= TRACKING =================
def check_trades(price):

    global stats

    for t in active_trades:

        if t["status"] != "OPEN":
            continue

        if t["direction"] == "LONG":

            if price >= t["tp"][0]:
                t["status"] = "WIN"
                stats["wins"] += 1
                stats["total"] += 1

            elif price <= t["sl"]:
                t["status"] = "LOSS"
                stats["losses"] += 1
                stats["total"] += 1

        else:

            if price <= t["tp"][0]:
                t["status"] = "WIN"
                stats["wins"] += 1
                stats["total"] += 1

            elif price >= t["sl"]:
                t["status"] = "LOSS"
                stats["losses"] += 1
                stats["total"] += 1


def report():

    if stats["total"] == 0:
        return "📊 No trades yet"

    wr = (stats["wins"] / stats["total"]) * 100

    return f"""
📊 PERFORMANCE

✅ Wins: {stats['wins']}
❌ Losses: {stats['losses']}
📈 WinRate: {wr:.2f}%

📦 Trades: {stats['total']}
""".strip()


# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)


# ================= LOOP =================
async def run():

    await send("🚀 FINAL PRO BOT ONLINE\n🧠 BTC Engine Active")

    last_report = time.time()

    while True:

        closes, highs, lows = get_data()

        price = closes[-1]

        check_trades(price)

        signal = signal_engine(price, closes, highs, lows)

        if signal:

            active_trades.append(signal)

            msg = format_signal(signal)

            await send(f"🚨 SIGNAL\n\n{msg}")

        if time.time() - last_report > STATUS_INTERVAL:

            await send(report())

            last_report = time.time()

        await asyncio.sleep(INTERVAL)


# ================= START =================
if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        log.critical(e)
