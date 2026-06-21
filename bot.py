import os
import time
import asyncio
import ccxt
import pandas as pd
from telegram import Bot

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

exchange = ccxt.binance({"enableRateLimit": True})


# 📊 گرفتن دیتا
def get_ohlcv(symbol="BTC/USDT", timeframe="5m", limit=50):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["t", "o", "h", "l", "c", "v"])
    return df


# 📈 RSI ساده
def rsi(df, period=14):
    delta = df["c"].diff()

    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


# 🎯 تولید سیگنال
def get_signal():
    df = get_ohlcv()
    df["rsi"] = rsi(df)

    last_rsi = df["rsi"].iloc[-1]

    price = df["c"].iloc[-1]

    if last_rsi < 30:
        return f"🟢 BUY SIGNAL\n💰 Price: {price}\n📊 RSI: {last_rsi:.2f}"

    elif last_rsi > 70:
        return f"🔴 SELL SIGNAL\n💰 Price: {price}\n📊 RSI: {last_rsi:.2f}"

    else:
        return None


# 🔁 حلقه اتوماتیک
async def run_bot():
    while True:
        try:
            signal = get_signal()

            if signal:
                await bot.send_message(chat_id=CHAT_ID, text=signal)

            await asyncio.sleep(300)  # هر 5 دقیقه

        except Exception as e:
            await bot.send_message(chat_id=CHAT_ID, text=str(e))
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_bot())
