import os
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ====================== CONFIG ======================
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
INTERVAL = 30  # ثانیه
STATUS_INTERVAL = 300

# ====================== LOGGING ======================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(), logging.FileHandler("trading_bot.log")])
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)

# راه‌اندازی Binance با CCXT
exchange = ccxt.binance({
    'enableRateLimit': True,   # مهم: خودکار مدیریت rate limit
})

price_histories = {symbol: [] for symbol in SYMBOLS}

def get_current_price(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return float(ticker['last'])
    except Exception as e:
        logger.error(f"خطا در قیمت {symbol}: {e}")
        return None

# تابع generate_signal رو مثل قبل نگه دار (MA + RSI)

async def send_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"خطا ارسال: {e}")

async def run_bot():
    await send_message("✅ <b>ربات v3.0 با CCXT + Binance فعال شد!</b>\nReal-time قیمت از صرافی اصلی")

    last_status = time.time()

    while True:
        for symbol in SYMBOLS:
            price = get_current_price(symbol)
            if not price:
                continue

            # generate_signal(symbol, price)  ← تابع قبلی رو اینجا صدا بزن

            if time.time() - last_status >= STATUS_INTERVAL:
                # گزارش وضعیت
                pass

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run_bot())
