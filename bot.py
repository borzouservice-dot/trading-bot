import os
import time
import asyncio
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

# لود متغیرها
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("🚀 Bot starting...")
print(f"✅ TOKEN: {bool(TOKEN)} | CHAT_ID: {bool(CHAT_ID)}")

if not TOKEN or not CHAT_ID:
    print("❌ Missing env variables!")
    exit(1)

print("✅ همه متغیرها اوکی هستن!")
print("Bot started...")

bot = Bot(token=TOKEN)

async def send_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
        print(f"📤 پیام ارسال شد: {text[:60]}...")
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")

def get_price():
    print("Before get_price")
    print("Getting price...")
    return 65000  # بعداً واقعی می‌کنیم

async def run_bot():
    print("run_bot started")
    await send_message("✅ <b>ربات تریدینگ شروع به کار کرد!</b>\n\nربات آنلاین است 🚀")
    
    while True:
        print("Loop is running")
        try:
            price = get_price()
            # هر ۱۰ دقیقه یک پیام وضعیت
            if int(time.time()) % 600 == 0:
                await send_message(f"🔄 قیمت فعلی: <b>${price}</b>")
        except Exception as e:
            print(f"Error: {e}")
            await send_message(f"⚠️ خطا: {e}")
        
        await asyncio.sleep(60)  # هر ۶۰ ثانیه

if __name__ == "__main__":
    asyncio.run(run_bot())
