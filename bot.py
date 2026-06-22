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

# تنظیمات اصلی
SYMBOLS = ["bitcoin", "ethereum", "solana"]  # می‌تونی اضافه کنی
INTERVAL = 60                    # ثانیه
STATUS_INTERVAL = 600            # هر ۱۰ دقیقه
HISTORY_LENGTH = 100

# پارامترهای استراتژی
MA_SHORT = 10
MA_LONG = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# مدیریت ریسک
STOP_LOSS_PCT = 3.0     # ۳٪
TAKE_PROFIT_PCT = 6.0   # ۶٪

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("trading_bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

print("🚀 ربات تریدینگ حرفه‌ای v2.0 شروع به کار کرد...")

if not TOKEN or not CHAT_ID:
    logger.error("❌ TOKEN یا CHAT_ID تنظیم نشده!")
    exit(1)

bot = Bot(token=TOKEN)

# ذخیره تاریخچه هر نماد
price_histories = {symbol: [] for symbol in SYMBOLS}
positions = {}  # برای مدیریت پوزیشن‌های مجازی

def get_current_price(symbol):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return float(response.json()[symbol]["usd"])
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت {symbol}: {e}")
        return None

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def generate_signal(symbol, price):
    history = price_histories[symbol]
    history.append(price)
    if len(history) > HISTORY_LENGTH:
        history.pop(0)

    if len(history) < MA_LONG + 5:
        return "HOLD", f"⏳ جمع‌آوری داده برای {symbol.upper()}..."

    # محاسبات
    ma_short = sum(history[-MA_SHORT:]) / MA_SHORT
    ma_long = sum(history[-MA_LONG:]) / MA_LONG
    rsi = calculate_rsi(history, RSI_PERIOD)

    signal = "HOLD"
    message = f"📊 <b>{symbol.upper()}</b> | ${price:,.2f}\n"

    # استراتژی ترکیبی
    if ma_short > ma_long and rsi and rsi < RSI_OVERBOUGHT:
        signal = "BUY"
        message += f"🟢 <b>سیگنال خرید قوی!</b>\nMA{MA_SHORT} > MA{MA_LONG}\nRSI: {rsi:.1f}"
    elif ma_short < ma_long and rsi and rsi > RSI_OVERSOLD:
        signal = "SELL"
        message += f"🔴 <b>سیگنال فروش!</b>\nMA{MA_SHORT} < MA{MA_LONG}\nRSI: {rsi:.1f}"

    message += f"\nRSI: {rsi:.1f if rsi else 'N/A'}"

    return signal, message

async def send_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
        logger.info(f"پیام ارسال شد: {text[:80]}...")
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")

async def run_bot():
    await send_message(
        "✅ <b>ربات تریدینگ حرفه‌ای v2.0 فعال شد!</b>\n\n"
        f"نمادها: {', '.join(s.upper() for s in SYMBOLS)}\n"
        f"استراتژی: MA + RSI\n"
        f"چک هر {INTERVAL} ثانیه\n"
        "🚀 آماده دریافت سیگنال..."
    )

    last_status = time.time()

    while True:
        for symbol in SYMBOLS:
            try:
                price = get_current_price(symbol)
                if not price:
                    continue

                signal, msg = generate_signal(symbol, price)

                if signal in ["BUY", "SELL"]:
                    await send_message(f"🚨 <b>سیگنال {symbol.upper()}!</b>\n\n{msg}")

                # گزارش وضعیت دوره‌ای
                if time.time() - last_status >= STATUS_INTERVAL:
                    await send_message(
                        f"📈 <b>گزارش وضعیت - {datetime.now().strftime('%H:%M')}</b>\n\n"
                        f"نماد: <b>{symbol.upper()}</b>\n"
                        f"قیمت: <b>${price:,.2f}</b>\n"
                        f"تعداد داده: {len(price_histories[symbol])}"
                    )
                    last_status = time.time()

            except Exception as e:
                logger.error(f"خطا در پردازش {symbol}: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("ربات با موفقیت متوقف شد.")
    except Exception as e:
        logger.critical(f"خطای بحرانی: {e}")
