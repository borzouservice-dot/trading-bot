import os
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ====================== CONFIG ======================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# تنظیمات
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
INTERVAL = 30                    # چک هر ۳۰ ثانیه
STATUS_INTERVAL = 300            # گزارش هر ۵ دقیقه

MA_SHORT = 10
MA_LONG = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 72
RSI_OVERSOLD = 28

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

if not TOKEN or not CHAT_ID:
    logger.error("❌ TOKEN یا CHAT_ID تنظیم نشده!")
    exit(1)

bot = Bot(token=TOKEN)

# راه‌اندازی صرافی
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

price_histories = {symbol: [] for symbol in SYMBOLS}

def get_current_price(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return float(ticker['last'])
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت {symbol}: {e}")
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
    if len(history) > 200:
        history.pop(0)

    if len(history) < MA_LONG:
        return "WARMUP", f"⏳ در حال جمع‌آوری داده...\n{symbol}: ${price:,.2f} | {len(history)}/{MA_LONG}"

    ma_short = sum(history[-MA_SHORT:]) / MA_SHORT
    ma_long = sum(history[-MA_LONG:]) / MA_LONG
    rsi = calculate_rsi(history, RSI_PERIOD)

    if ma_short > ma_long and rsi and rsi < RSI_OVERBOUGHT:
        return "BUY", f"🟢 <b>سیگنال خرید قوی!</b> {symbol}\nقیمت: <b>${price:,.2f}</b>\nMA{MA_SHORT} > MA{MA_LONG}\nRSI: {rsi:.1f}"
    elif ma_short < ma_long and rsi and rsi > RSI_OVERSOLD:
        return "SELL", f"🔴 <b>سیگنال فروش!</b> {symbol}\nقیمت: <b>${price:,.2f}</b>\nMA{MA_SHORT} < MA{MA_LONG}\nRSI: {rsi:.1f}"
    
    return "HOLD", None

async def send_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
        logger.info(f"پیام ارسال شد")
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")

async def run_bot():
    await send_message(
        "✅ <b>ربات تریدینگ v3.0</b> با CCXT + Binance فعال شد!\n\n"
        f"نمادها: {', '.join(SYMBOLS)}\n"
        f"استراتژی: MA + RSI\n"
        "Real-time قیمت از صرافی بایننس 🚀\n"
        "در حال جمع‌آوری داده اولیه..."
    )

    last_status = time.time()

    while True:
        for symbol in SYMBOLS:
            try:
                price = get_current_price(symbol)
                if price is None:
                    continue

                signal, msg = generate_signal(symbol, price)

                if signal in ["BUY", "SELL"] and msg:
                    await send_message(f"🚨 <b>سیگنال جدید!</b>\n\n{msg}")

                # گزارش وضعیت هر ۵ دقیقه
                if time.time() - last_status >= STATUS_INTERVAL:
                    status = f"📊 <b>گزارش وضعیت - {datetime.now().strftime('%H:%M:%S')}</b>\n\n"
                    for s in SYMBOLS:
                        p = price_histories[s][-1] if price_histories[s] else "در حال بارگذاری..."
                        status += f"<b>{s}</b>: ${float(p):,.2f}\n" if isinstance(p, (int, float)) else f"<b>{s}</b>: {p}\n"
                    await send_message(status)
                    last_status = time.time()

            except Exception as e:
                logger.error(f"خطا در پردازش {symbol}: {e}")

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("ربات متوقف شد.")
    except Exception as e:
        logger.critical(f"خطای بحرانی: {e}")
