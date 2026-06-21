import os
import asyncio
import requests
import pandas as pd
from telegram import Bot

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)


# 💰 قیمت بیتکوین
def get_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        r = requests.get(url, timeout=10).json()
        return r["bitcoin"]["usd"]
    except Exception as e:
        print("Price error:", e)
        return None


# 📊 RSI ساده (با داده مصنوعی سبک ولی پایدار)
def rsi(values, period=14):
    df = pd.DataFrame(values, columns=["c"])

    delta = df["c"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


# 🎯 سیگنال
def generate_signal(price):
    prices = [price] * 25
    r = rsi(prices).iloc[-1]

    if r < 30:
        return f"🟢 BUY SIGNAL\nBTC: {price}\nRSI: {r:.2f}"

    if r > 70:
        return f"🔴 SELL SIGNAL\nBTC: {price}\nRSI: {r:.2f}"

    return None


# 🔁 loop پایدار
async def run():
    while True:
        try:
            price = get_price()

            if price:
                msg = generate_signal(price)

                if msg:
                    await bot.send_message(chat_id=CHAT_ID, text=msg)

        except Exception as e:
            print("Loop error:", e)

            # جلوگیری از crash کامل
            try:
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error: {e}")
            except:
                pass

        await asyncio.sleep(60)  # هر 1 دقیقه


if __name__ == "__main__":
    print("Bot started...")
    asyncio.run(run())
