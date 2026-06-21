import os
import asyncio
import requests
import pandas as pd
from telegram import Bot

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)


# 💰 گرفتن قیمت از CoinGecko (بدون محدودیت)
def get_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd"
    }
    data = requests.get(url).json()
    return data["bitcoin"]["usd"]


# 📊 ساخت دیتا ساده برای RSI
def fake_ohlcv(price):
    return pd.DataFrame([price] * 20, columns=["c"])


def rsi(series, period=14):
    delta = series.diff()

    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


# 🎯 سیگنال
def signal():
    price = get_price()

    df = fake_ohlcv(price)
    df["rsi"] = rsi(df["c"])

    last_rsi = df["rsi"].iloc[-1]

    if last_rsi < 30:
        return f"🟢 BUY\nPrice: {price}\nRSI: {last_rsi:.2f}"

    if last_rsi > 70:
        return f"🔴 SELL\nPrice: {price}\nRSI: {last_rsi:.2f}"

    return None


# 🔁 اجرا
async def run():
    while True:
        try:
            msg = signal()

            if msg:
                await bot.send_message(chat_id=CHAT_ID, text=msg)

            await asyncio.sleep(300)

        except Exception as e:
            await bot.send_message(chat_id=CHAT_ID, text=str(e))
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run())
