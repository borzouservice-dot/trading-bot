import os
import asyncio
import requests
import pandas as pd
from flask import Flask
from telegram import Bot
import threading

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

app = Flask(__name__)


# 🌐 برای Render (حتماً لازم است)
@app.route("/")
def home():
    return "Bot is running"


# 💰 قیمت بیتکوین
def get_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    r = requests.get(url).json()
    return r["bitcoin"]["usd"]


# 📊 RSI ساده
def rsi(values, period=14):
    df = pd.DataFrame(values, columns=["c"])
    delta = df["c"].diff()

    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


# 🎯 سیگنال
def signal():
    price = get_price()

    prices = [price] * 20
    r = rsi(prices).iloc[-1]

    if r < 30:
        return f"🟢 BUY\nPrice: {price}\nRSI: {r:.2f}"

    if r > 70:
        return f"🔴 SELL\nPrice: {price}\nRSI: {r:.2f}"

    return None


# 🔁 حلقه ارسال سیگنال
async def run_bot():
    while True:
        try:
            msg = signal()

            if msg:
                await bot.send_message(chat_id=CHAT_ID, text=msg)

            await asyncio.sleep(300)

        except Exception as e:
            await bot.send_message(chat_id=CHAT_ID, text=str(e))
            await asyncio.sleep(60)


# 🌐 اجرای Flask
def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


# 🚀 اجرا همزمان
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    asyncio.run(run_bot())
