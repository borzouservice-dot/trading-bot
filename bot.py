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

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

INTERVAL = 20
STATUS_INTERVAL = 300

MA_SHORT = 8
MA_LONG = 21
RSI_PERIOD = 14

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

if not TOKEN or not CHAT_ID:
    logger.error("TOKEN یا CHAT_ID تنظیم نشده!")
    exit(1)

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

price_history = {s: [] for s in SYMBOLS}


# ================= INDICATORS =================
def sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def rsi(data, period=14):
    if len(data) < period + 1:
        return None

    gains = []
    losses = []

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


# ================= DATA =================
def get_price(symbol):
    try:
        return float(exchange.fetch_ticker(symbol)["last"])
    except Exception as e:
        logger.error(f"Price error {symbol}: {e}")
        return None


# ================= SIGNAL ENGINE =================
def generate_signal(symbol, price):
    history = price_history[symbol]

    history.append(price)
    if len(history) > 300:
        history.pop(0)

    if len(history) < MA_LONG:
        return None

    short = sma(history, MA_SHORT)
    long = sma(history, MA_LONG)
    r = rsi(history, RSI_PERIOD)

    if short is None or long is None or r is None:
        return None

    # LONG
    if short > long and r < 70:
        return build_signal(symbol, "LONG", price, r)

    # SHORT
    if short < long and r > 30:
        return build_signal(symbol, "SHORT", price, r)

    return None


# ================= SIGNAL BUILDER =================
def build_signal(symbol, direction, price, rsi_value):

    is_long = direction == "LONG"

    sl = price * (0.97 if is_long else 1.03)

    tp = [
        price * (1.02 if is_long else 0.98),
        price * (1.04 if is_long else 0.96),
        price * (1.06 if is_long else 0.94),
        price * (1.08 if is_long else 0.92),
    ]

    confidence = 0.7

    return {
        "symbol": symbol,
        "direction": direction,
        "entry": "MARKET",
        "risk": 0.03,
        "leverage": 20,
        "sl": sl,
        "tp": tp,
        "confidence": confidence,
        "rsi": rsi_value
    }


# ================= FORMATTER =================
def format_signal(s):
    emoji = "🟢" if s["direction"] == "LONG" else "🔴"

    tp_text = ""
    for i, t in enumerate(s["tp"], 1):
        tp_text += f"• TP{i}: {t:.2f}\n"

    return f"""
🚀 {s['symbol']}

{emoji} {s['direction']} SIGNAL

📍 Entry: {s['entry']}
💰 Risk: {s['risk']*100:.1f}% | Leverage: x{s['leverage']}
📊 RSI: {s['rsi']:.1f}
🎯 Confidence: {s['confidence']*100:.0f}%

━━━━━━━━━━━━━━━
⛔ Stop Loss: {s['sl']:.2f}

🎯 Take Profits:
{tp_text}
━━━━━━━━━━━━━━━
🕒 {datetime.utcnow().strftime('%H:%M UTC')}
""".strip()


# ================= TELEGRAM =================
async def send(text):
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Telegram error: {e}")


# ================= MAIN LOOP =================
async def run():
    await send("✅ Bot v4 ONLINE - Signal Engine Active")

    last_status = time.time()

    while True:
        for symbol in SYMBOLS:
            price = get_price(symbol)
            if not price:
                continue

            signal = generate_signal(symbol, price)

            if signal:
                msg = format_signal(signal)
                await send(f"🚨 NEW SIGNAL\n\n{msg}")

        # status update
        if time.time() - last_status > STATUS_INTERVAL:
            status = "📊 LIVE STATUS\n\n"
            for s in SYMBOLS:
                p = price_history[s][-1] if price_history[s] else 0
                status += f"{s}: {p:.2f}\n"
            await send(status)
            last_status = time.time()

        await asyncio.sleep(INTERVAL)


# ================= START =================
if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
