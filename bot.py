import os
import time
import requests
import pandas as pd
from flask import Flask
from telegram import Bot
import threading

# =========================
# 🔐 Telegram
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

print("Bot starting...")

bot = Bot(token=TOKEN)

# =========================
# 🌐 Flask
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# =========================
# 💰 Price
# =========================
def get_price():
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=5
        )
        return float(r.json()["price"])
    except Exception as e:
        print("PRICE ERROR:", e)
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
    return 100 - (100 / (1 + rs)).iloc[-1]

# =========================
# 🎯 Signal
# =========================
def generate_signal(price):
    price_history.append(price)

    if len(price_history) > 30:
        price_history.pop(0)

    rsi = calculate_rsi(price_history)

    print("RSI:", rsi)

    if rsi < 30:
        return f"🟢 BUY\nBTC: {price}\nRSI: {rsi:.2f}"

    if rsi > 70:
        return f"🔴 SELL\nBTC: {price}\nRSI: {rsi:.2f}"

    return None

# =========================
# 🔁 Bot loop (IMPORTANT: بدون asyncio)
# =========================
def run_bot():
    print("run_bot started")

    while True:
        try:
            price = get_price()

            if price:
                print("PRICE:", price)

                msg = generate_signal(price)

                if msg:
                    print("SIGNAL:", msg)

                    bot.send_message(
                        chat_id=CHAT_ID,
                        text=msg
                    )
                else:
                    print("No signal")

        except Exception as e:
            print("LOOP ERROR:", e)

        time.sleep(60)

# =========================
# 🚀 MAIN
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
