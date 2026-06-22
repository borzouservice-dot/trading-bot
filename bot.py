import os
import time
import asyncio
import logging
from datetime import datetime
import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

# ====================== CONFIG ======================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["bitcoin", "ethereum", "solana"]
INTERVAL = 60
STATUS_INTERVAL = 300          # حالا هر ۵ دقیقه گزارش وضعیت
HISTORY_LENGTH = 100

MA_SHORT = 10
MA_LONG = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 72
RSI_OVERSOLD = 28

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("trading_bot.log", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

if not TOKEN or not CHAT_ID:
    logger.error("❌ TOKEN یا CHAT_ID تنظیم نشده!")
    exit(1)

bot = Bot(token=TOKEN)
price_histories = {symbol: [] for symbol in SYMBOLS}

def get_current_price(symbol):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        return float(r.json()[symbol]["usd"])
    except Exception as e:
        logger.error(f"خطا قیمت {symbol}: {e}")
        return None

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
    losses = [max(prices[i-1] - prices[i], 0) for i in range(1, len(prices))]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def generate_signal(symbol, price):
    history = price_histories[symbol]
    history.append(price)
    if len(history) > HISTORY_LENGTH:
        history.pop(0)

    data_count = len(history)
    
    if data_count < MA_LONG:
        return "WARMUP", f"⏳ گرم شدن ربات...\n{symbol.upper()}: ${price:,.2f} | داده: {data_count}/{MA_LONG}"

    ma_short = sum(history[-MA_SHORT:]) / MA_SHORT
    ma_long = sum(history[-MA_LONG:]) / MA_LONG
    rsi = calculate_rsi(history, RSI_PERIOD)

    if ma_short > ma_long and rsi and rsi < RSI_OVERBOUGHT:
        return "BUY", f"🟢 <b>سیگنال خرید</b> {symbol.upper()}\nقیمت: ${price:,.2f}\nMA{MA_SHORT} > MA{MA_LONG}\nRSI: {rsi:.1f}"
    elif ma_short < ma_long and rsi and rsi > RSI_OVERSOLD:
        return "SELL", f"🔴 <b>سیگنال فروش</b> {symbol.upper()}\nقیمت: ${price:,.2f}\nMA{MA_SHORT} < MA{MA_LONG}\nRSI: {rsi:.1f}"
    
    return "HOLD", f"🔄 {symbol.upper()} | ${price:,.2f} | RSI: {rsi:.1f if rsi else 'N/A'}"

async def send_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"خطا ارسال: {e}")

async def run_bot():
    # پیام شروع + قیمت اولیه
    await send_message("✅ <b>ربات تریدینگ v2.1 فعال شد</b>\nدر حال جمع‌آوری داده...\n")

    last_status = time.time()

    while True:
        for symbol in SYMBOLS:
            price = get_current_price(symbol)
            if not price:
                continue

            signal, msg = generate_signal(symbol, price)

            # ارسال سیگنال‌های مهم
            if signal in ["BUY", "SELL"]:
                await send_message(f"🚨 <b>سیگنال جدید!</b>\n\n{msg}")

            # گزارش وضعیت هر ۵ دقیقه (یک بار برای همه نمادها)
            if time.time() - last_status >= STATUS_INTERVAL:
                status_text = f"📊 <b>گزارش وضعیت - {datetime.now().strftime('%H:%M')}</b>\n\n"
                for s in SYMBOLS:
                    p = price_histories[s][-1] if price_histories[s] else "N/A"
                    status_text += f"<b>{s.upper()}</b>: ${p:,.0f if isinstance(p, float) else p}\n"
                await send_message(status_text)
                last_status = time.time()

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("ربات متوقف شد.")
    except Exception as e:
        logger.critical(f"خطای بحرانی: {e}")
