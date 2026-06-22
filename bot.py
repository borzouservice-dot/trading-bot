import os
import time
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

def send_message(text):
    try:
        bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
        print(f"📤 پیام ارسال شد: {text[:50]}...")
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")

def get_price():
    print("Before get_price")
    print("Getting price...")
    # بعداً کد واقعی قیمت رو اینجا می‌ذاریم
    return 65000

def run_bot():
    print("run_bot started")
    send_message("✅ <b>ربات تریدینگ شروع به کار کرد!</b>\n\nربات آنلاین است 🚀")
    
    while True:
        print("Loop is running")
        try:
            price = get_price()
            # هر ۱۰ بار یک پیام تست بفرست (برای جلوگیری از اسپم)
            if int(time.time()) % 600 == 0:   # هر ۱۰ دقیقه یک پیام
                send_message(f"🔄 قیمت فعلی: <b>${price}</b>")
        except Exception as e:
            print(f"Error: {e}")
            send_message(f"⚠️ خطا: {e}")
        
        time.sleep(60)  # هر ۶۰ ثانیه

if __name__ == "__main__":
    run_bot()
