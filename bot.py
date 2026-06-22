import os
import asyncio
import requests
import pandas as pd
from flask import Flask
from telegram import Bot
import threading
import time

# =========================
# 🔐 تنظیمات تلگرام
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")

# تبدیل امن CHAT_ID به int
CHAT_ID = os.getenv("CHAT_ID")
if CHAT_ID:
    CHAT_ID = int(CHAT_ID)

# برای تست


bot = Bot(token=TOKEN)

# =========================
# 🌐 Flask (حل مشکل Render port)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


# =========================
# 💰 گرفتن قیمت Bitcoin
# =========================

def get_price():
    try:
        print("Getting price...")

        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=(5, 10)
        )

        print("Status:", r.status_code)

        data = r.json()
        print(data)

        return float(data["price"])

    except Exception as e:
        print("Price error:", repr(e))
        return None

# =========================
# 📊 RSI واقعی‌تر (با history ساده)
# =========================
price_history = []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50  # مقدار خنثی

    df = pd.DataFrame(prices, columns=["c"])
    delta = df["c"].diff()

    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1]


# =========================
# 🎯 تولید سیگنال
# =========================
def generate_signal(price):
    price_history.append(price)

    # نگه داشتن آخرین 30 قیمت
    if len(price_history) > 30:
        price_history.pop(0)

    rsi = calculate_rsi(price_history)

    if rsi < 30:
        return f"🟢 BUY SIGNAL\n💰 BTC: {price}\n📊 RSI: {rsi:.2f}"

    if rsi > 70:
        return f"🔴 SELL SIGNAL\n💰 BTC: {price}\n📊 RSI: {rsi:.2f}"

    return None


# =========================
# 🔁 loop اصلی
# =========================
async def run_bot():
    print("run_bot started")
    while True:
        print("Loop is running")
        try:
            print("Before get_price")
            price = get_price()
            print("After get_price")
            print("Price =", price)
            if price:
                print("PRICE:", price)

                msg = generate_signal(price)

                if msg:
                    print("SIGNAL:", msg)

                    await bot.send_message(
                        chat_id=CHAT_ID,
                        text=msg
                    )
                else:
                    print("No signal")

        except Exception as e:
            print("Loop error:", e)

        await asyncio.sleep(60)


# =========================
# 🚀 اجرا همزمان Flask + Bot
# =========================
if __name__ == "__main__":
    print("Bot started...")

    # جلوگیری از مشکل Render port
    threading.Thread(target=run_web).start()

    # شروع ربات
    asyncio.run(run_bot())
