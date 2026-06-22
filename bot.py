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

# تنظیمات ربات
SYMBOL = "bitcoin"          # می‌تونی تغییر بدی به ethereum و ...
INTERVAL = 60               # چک کردن هر ۶۰ ثانیه
STATUS_INTERVAL = 600       # پیام وضعیت هر ۱۰ دقیقه
HISTORY_LENGTH = 50         # تعداد داده‌های تاریخی برای محاسبه میانگین

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

print("🚀 ربات تریدینگ حرفه‌ای در حال شروع...")
print(f"✅ TOKEN: {bool(TOKEN)} | CHAT_ID: {bool(CHAT_ID)}")

if not TOKEN or not CHAT_ID:
    logger.error("❌ متغیرهای محیطی TOKEN یا CHAT_ID تنظیم نشده‌اند!")
    exit(1)

bot = Bot(token=TOKEN)

# ذخیره تاریخچه قیمت برای محاسبه سیگنال
price_history = []

def get_current_price():
    """دریافت قیمت واقعی از CoinGecko API"""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={SYMBOL}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        price = data[SYMBOL]["usd"]
        return float(price)
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت: {e}")
        return None

def generate_signal(price):
    """تولید سیگنال ساده با Moving Average Crossover"""
    global price_history
    price_history.append(price)
    if len(price_history) > HISTORY_LENGTH:
        price_history.pop(0)
    
    if len(price_history) < 20:
        return "HOLD", "⏳ در حال جمع‌آوری داده..."

    # محاسبه میانگین‌های متحرک
    short_ma = sum(price_history[-10:]) / 10    # MA10
    long_ma = sum(price_history[-20:]) / 20     # MA20
    
    # تشخیص کراس‌اوور
    if len(price_history) >= 21:
        prev_short = sum(price_history[-11:-1]) / 10
        prev_long = sum(price_history[-21:-1]) / 20
        
        if prev_short <= prev_long and short_ma > long_ma:
            return "BUY", f"🟢 <b>سیگنال خرید قوی!</b>\nقیمت: <b>${price:,.2f}</b>\nMA10: {short_ma:,.2f} > MA20: {long_ma:,.2f}"
        elif prev_short >= prev_long and short_ma < long_ma:
            return "SELL", f"🔴 <b>سیگنال فروش!</b>\nقیمت: <b>${price:,.2f}</b>\nMA10: {short_ma:,.2f} < MA20: {long_ma:,.2f}"
    
    return "HOLD", f"🔄 وضعیت: HOLD\nقیمت: <b>${price:,.2f}</b>\nMA10: {short_ma:,.2f} | MA20: {long_ma:,.2f}"

async def send_message(text):
    try:
        await bot.send_message(
            chat_id=CHAT_ID, 
            text=text, 
            parse_mode=ParseMode.HTML
        )
        logger.info(f"📤 پیام ارسال شد: {text[:100]}...")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال پیام: {e}")

async def run_bot():
    await send_message(
        "✅ <b>ربات تریدینگ حرفه‌ای شروع به کار کرد!</b>\n\n"
        f"نماد: <b>{SYMBOL.upper()}</b>\n"
        "استراتژی: Moving Average Crossover (MA10/MA20)\n"
        "ربات آنلاین است 🚀\n\n"
        "هر ۶۰ ثانیه چک می‌کند و در صورت سیگنال قوی اطلاع می‌دهد."
    )
    
    last_status_time = time.time()
    
    while True:
        try:
            price = get_current_price()
            if price is None:
                await asyncio.sleep(INTERVAL)
                continue
            
            signal, message = generate_signal(price)
            
            # ارسال سیگنال قوی
            if signal in ["BUY", "SELL"]:
                await send_message(f"🚨 <b>سیگنال جدید!</b>\n\n{message}")
            
            # پیام وضعیت دوره‌ای
            if time.time() - last_status_time >= STATUS_INTERVAL:
                await send_message(f"📊 <b>گزارش وضعیت</b>\n\nقیمت فعلی: <b>${price:,.2f}</b>\nزمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                last_status_time = time.time()
                
        except Exception as e:
            logger.error(f"خطای کلی: {e}")
            try:
                await send_message(f"⚠️ خطا در ربات: {str(e)[:200]}")
            except:
                pass
        
        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("ربات با موفقیت متوقف شد.")
    except Exception as e:
        logger.critical(f"خطای بحرانی: {e}")
