import os
import time
import requests
import pandas as pd
from flask import Flask
from telegram import Bot
import threading
import traceback

# =========================
# 🔐 Config
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("🚀 Bot starting...")
print(f"✅ TOKEN: {bool(TOKEN)} | CHAT_ID: {bool(CHAT_ID)}")

if not TOKEN or not CHAT_ID:
    print("❌ Missing env variables!")
    exit(1)

bot = Bot(token=TOKEN)
CHAT_ID = int(CHAT_ID)

# =========================
# 🌐 Flask
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Trading Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# =========================
# 💰 Price - استفاده از Binance + Proxy fallback
# =========================
def get_price():
    try:
        print("📡 Trying Binance...")
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            price = float(r.json()["price"])
            print(f"✅ Binance Success: ${price:,.2f}")
            return price
    except:
        pass

    # Fallback به CoinGecko با تاخیر
    try:
        print("📡 Trying CoinGecko...")
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            price = float(r.json()["bitcoin"]["usd"])
            print(f"✅ CoinGecko Success: ${price:,.2f}")
            return price
    except:
        pass

    print("❌ All APIs failed")
    return None

# =========================
# 📊 RSI
# =========================
price_history = []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    try:
        df = pd.DataFrame(prices, columns=["c"])
        delta = df["c"].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        return float(rsi)
    except:
        return 50.0

# =========================
# 🎯 Signal
# =========================
def generate_signal(price):
    price_history.append(price)
    if len(price_history) > 100:
        price_history.pop(0)
    
    rsi = calculate_rsi(price_history)
    print(f"📊 PRICE: ${price:,.2f} | RSI: {rsi:.2f}")
    
    if rsi < 30:
        return f"🟢 **BUY SIGNAL**\nBTC: ${price:,.2f}\nRSI: {rsi:.2f}"
    elif rsi > 70:
        return f"🔴 **SELL SIGNAL**\nBTC: ${price:,.2f}\nRSI: {rsi:.2f}"
    return None

# =========================
# 🔁 Loop
# =========================
def run_bot():
    print("🔄 Bot loop started")
    last_signal = None

    while True:
        price = get_price()
        if price is not None:
            msg = generate_signal(price)
            if msg and msg != last_signal:
                try:
                    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                    print("✅ Signal sent to Telegram!")
                    last_signal = msg
                except Exception as e:
                    print("Telegram send error:", e)
            else:
                print("ℹ️ No signal this time")
        else:
            print("⚠️ Could not fetch price this cycle")

        time.sleep(120)  # ۲ دقیقه یکبار

# =========================
# 🚀 Start
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
