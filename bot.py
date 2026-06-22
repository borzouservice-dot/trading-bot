import os
import time
from dotenv import load_dotenv

# ==================== لود کردن متغیرهای محیطی ====================
load_dotenv()  # این خط خیلی مهمه! فایل .env را لود می‌کند

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ==================== چک کردن متغیرها ====================
print("🚀 Bot starting...")
print(f"✅ TOKEN: {bool(TOKEN)} | CHAT_ID: {bool(CHAT_ID)}")

if not TOKEN or not CHAT_ID:
    print("❌ Missing env variables!")
    print("لطفاً فایل .env را چک کنید یا متغیرها را export کنید.")
    exit(1)

print("✅ همه متغیرها اوکی هستن!")
print("Bot started...")

# ==================== اینجا کد اصلی بات شما ====================

def get_price():
    print("Before get_price")
    print("Getting price...")
    # کد گرفتن قیمت را اینجا بگذارید
    return 0  # فعلاً تست

def run_bot():
    print("run_bot started")
    while True:
        print("Loop is running")
        try:
            get_price()
            # بقیه منطق تریدینگ شما اینجا...
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(60)  # هر ۶۰ ثانیه یکبار (می‌توانید تغییر دهید)

if __name__ == "__main__":
    run_bot()
