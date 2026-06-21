import os
import asyncio
import requests
import pandas as pd
from flask import Flask
from telegram import Bot
import threading

# =========================
# 🔐 تنظیمات تلگرام
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

# =========================
# 🌐 Flask برای Render (حل مشکل port)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================
# 💰 گرفتن قیمت Bitcoin
# =========================
def get_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        r = requests.get(url, timeout=10).json()
        return r["bitcoin"]["usd"]
    except Exception as e:
        print("Price error:", e)
        return None


# =========================
# 📊 RSI ساده
# =========================
def rsi(values, period=14):
    df = pd.DataFrame(values, columns=["c"])

    delta = df["c"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


# =========================
# 🎯 تولید سیگنال
# =========================
def generate_signal(price):
    prices = [price] * 25
    r = rsi(prices).iloc[-1]

    if r < 30:
        return f"🟢 BUY SIGNAL\n💰 BTC: {price}\n📊 RSI: {r:.2f}"

    if r > 70:
        return f"🔴 SELL SIGNAL\n💰 BTC: {price}\n📊 RSI: {r:.2f}"

    return None


# =========================
# 🔁 حلقه اصلی ربات
# =========================
async def run_bot():
    while True:
        try:
            price = get_price()

            if price:
                msg = generate_signal(price)

                if msg:
                    await bot.send_message(chat_id=CHAT_ID, text=msg)

        except Exception as e:
            print("Loop error:", e)
            try:
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error: {e}")
            except:
                pass

        await asyncio.sleep(60)  # هر 1 دقیقه


# =========================
# 🚀 اجرای همزمان Flask + Bot
# =========================
if __name__ == "__main__":
    print("Bot started...")

    # اجرای وب‌سرور برای Render
    threading.Thread(target=run_web).start()

    # اجرای ربات
    asyncio.run(run_bot())
