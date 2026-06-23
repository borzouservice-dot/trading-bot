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

SYMBOLS = ["BTC/USDT"]

INTERVAL = 20
STATUS_INTERVAL = 300

MA_FAST = 8
MA_SLOW = 21
RSI_PERIOD = 14
ATR_PERIOD = 14

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("trading_bot.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
price_history = {s: [] for s in SYMBOLS}
high_history = {s: [] for s in SYMBOLS}
low_history = {s: [] for s in SYMBOLS}

active_signals = []

stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

# ================= INDICATORS =================
def sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def rsi(data, period=14):
    if len(data) < period + 1:
        return None

    gains, losses = [], []

    for i in range(1, len(data)):
        diff = data[i] - data[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return None

    trs = []

    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)

    return sum(trs[-period:]) / period


# ================= PRICE =================
def get_ohlcv(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1m", limit=100)
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        return closes, highs, lows
    except Exception as e:
        logger.error(f"OHLCV error: {e}")
        return None, None, None


# ================= SIGNAL ENGINE =================
def generate_signal(symbol, price, rsi_val, atr_val, fast_ma, slow_ma):

    # ❌ بازار رنج → سیگنال نده
    if abs(fast_ma - slow_ma) < atr_val * 0.2:
        return None

    # 🟢 LONG
    if fast_ma > slow_ma and rsi_val < 70:

        sl = price - atr_val * 1.5

        tp = [
            price + atr_val * 1,
            price + atr_val * 2,
            price + atr_val * 3,
        ]

        return {
            "symbol": symbol,
            "direction": "LONG",
            "entry": price,
            "sl": sl,
            "tp": tp,
            "confidence": 0.8,
            "rsi": rsi_val
        }

    # 🔴 SHORT
    if fast_ma < slow_ma and rsi_val > 30:

        sl = price + atr_val * 1.5

        tp = [
            price - atr_val * 1,
            price - atr_val * 2,
            price - atr_val * 3,
        ]

        return {
            "symbol": symbol,
            "direction": "SHORT",
            "entry": price,
            "sl": sl,
            "tp": tp,
            "confidence": 0.8,
            "rsi": rsi_val
        }

    return None


# ================= FORMAT =================
def format_signal(s):

    emoji = "🟢" if s["direction"] == "LONG" else "🔴"

    risk = abs(s["entry"] - s["sl"])

    tp_text = ""
    for i, t in enumerate(s["tp"], 1):
        rr = abs(t - s["entry"]) / risk
        tp_text += f"• TP{i}: {t:.2f} ({rr:.1f}R)\n"

    return f"""
🚀 {s['symbol']}

{emoji} {s['direction']} PRO SIGNAL

📍 Entry: {s['entry']:.2f}
📊 RSI: {s['rsi']:.1f}
🎯 Confidence: {s['confidence']*100:.0f}%

━━━━━━━━━━━━━━━
⛔ Stop Loss: {s['sl']:.2f}

🎯 Take Profits:
{tp_text}
━━━━━━━━━━━━━━━
🧠 Engine: ATR + Trend Filter
⚡ Mode: PRO SCALPING
🕒 {datetime.utcnow().strftime('%H:%M UTC')}
""".strip()


# ================= PERFORMANCE =================
def check_signals(price):

    global stats

    for s in active_signals:
        if s["status"] != "OPEN":
            continue

        if s["direction"] == "LONG":

            if price >= s["tp"][0]:
                s["status"] = "WIN"
                stats["wins"] += 1
                stats["total"] += 1

            elif price <= s["sl"]:
                s["status"] = "LOSS"
                stats["losses"] += 1
                stats["total"] += 1

        else:

            if price <= s["tp"][0]:
                s["status"] = "WIN"
                stats["wins"] += 1
                stats["total"] += 1

            elif price >= s["sl"]:
                s["status"] = "LOSS"
                stats["losses"] += 1
                stats["total"] += 1


def performance_report():

    if stats["total"] == 0:
        return "📊 No trades yet"

    winrate = (stats["wins"] / stats["total"]) * 100

    return f"""
📊 PERFORMANCE REPORT

✅ Wins: {stats['wins']}
❌ Losses: {stats['losses']}
📈 Win Rate: {winrate:.2f}%

📦 Total Trades: {stats['total']}
""".strip()


# ================= TELEGRAM =================
async def send(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Telegram error: {e}")


# ================= MAIN LOOP =================
async def run():

    await send("🚀 PRO Bot ONLINE (BTC ONLY)\n🧠 ATR + Trend Engine ACTIVE")

    last_status = time.time()

    while True:

        closes, highs, lows = get_ohlcv("BTC/USDT")

        if not closes:
            await asyncio.sleep(INTERVAL)
            continue

        price = closes[-1]

        fast_ma = sma(closes, MA_FAST)
        slow_ma = sma(closes, MA_SLOW)
        rsi_val = rsi(closes, RSI_PERIOD)
        atr_val = atr(highs, lows, closes, ATR_PERIOD)

        if None in [fast_ma, slow_ma, rsi_val, atr_val]:
            await asyncio.sleep(INTERVAL)
            continue

        # check active trades
        check_signals(price)

        signal = generate_signal("BTC/USDT", price, rsi_val, atr_val, fast_ma, slow_ma)

        if signal:

            active_signals.append({
                **signal,
                "status": "OPEN",
                "time": time.time()
            })

            msg = format_signal(signal)
            await send(f"🚨 NEW PRO SIGNAL\n\n{msg}")

        if time.time() - last_status > STATUS_INTERVAL:
            await send(performance_report())
            last_status = time.time()

        await asyncio.sleep(INTERVAL)


# ================= START =================
if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
