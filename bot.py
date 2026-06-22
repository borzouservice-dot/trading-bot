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

if CHAT_ID:
    CHAT_ID = int(CHAT_ID)

print("TOKEN LOADED:", bool(TOKEN))
print("CHAT_ID LOADED:", CHAT_ID)

bot = Bot(token=TOKEN)

# =========================
# 🌐 Flask (برای Render)
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
# 💰 گرفتن قیمت BTC (پایدار Binance)
# =========================
def get_price():
    try:
        print("Getting price...")

        url = "https://api.binance.com/api/v3/ticker/price"

        r = requests.get(
            url,
            params={"symbol": "BTCUSDT"},
            timeout=(3, 5),
            headers={"Connection": "close"}
        )

        data = r.json()
        price = float(data["price"])

        print("PRICE:", price)
        return price

    except Exception as e:
        print("PRICE ERROR:", repr(e))
        return None


# =========================
# 📊 RSI
# =========================
price_history = []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50

    df = pd.DataFrame(prices, columns=["c"])
    delta = df["c"].diff()

    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1]


# =========================
# 🎯 سیگنال
# =========================
def generate_signal(price):
    price_history.append(price)

    if len(price_history) > 30:
        price_history.pop(0)

    rsi = calculate_rsi(price_history)

    print(f"RSI: {rsi:.2f}")

    if rsi < 30:
        return f"🟢 BUY SIGNAL\n💰 BTC: {price}\n📊 RSI: {rsi:.2f}"

    if rsi > 70:
        return f"🔴 SELL SIGNAL\n💰 BTC: {price}\n📊 RSI: {rsi:.2f}"

    return None


# =========================
# 🔁 Bot Loop
# =========================
async def run_bot():
    print("run_bot started")

    while True:
        try:
            print("Loop is running")

            price = get_price()

            if price:
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
            print("LOOP ERROR:", repr(e))

        await asyncio.sleep(60)


# =========================
# 🚀 Run both Flask + Bot
# =========================
if __name__ == "__main__":
    print("Bot started...")

    threading.Thread(target=run_web).start()

    asyncio.run(run_bot())
