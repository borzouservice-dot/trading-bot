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
    print(f"🌐 Flask started on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# =========================
# 💰 Price (FIXED)
# =========================
def get_price():
    try:
        print("📡 Fetching BTC price...")
        # استفاده از data.binance.com که کمتر بلاک می‌شه
        r = requests.get(
            "https://data.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=10
        )
        r.raise_for_status()
        price = float(r.json()["price"])
        print(f"✅ Price: {price}")
        return price
    except Exception as e:
        print("❌ PRICE ERROR:", str(e))
        traceback.print_exc()
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
    print(f"📊 PRICE: {price:.2f} | RSI: {rsi:.2f}")
    
    if rsi < 30:
        return f"🟢 **BUY SIGNAL**\nBTC: {price:.2f} USDT\nRSI: {rsi:.2f}"
    elif rsi > 70:
        return f"🔴 **SELL SIGNAL**\nBTC: {price:.2f} USDT\nRSI: {rsi:.2f}"
    return None

# =========================
# 🔁 Loop
# =========================
def run_bot():
    print("🔄 Bot loop started")
    last_signal = None

    while True:
        try:
            price = get_price()
            if price:
                msg = generate_signal(price)
                if msg and msg != last_signal:
                    print("📣 Sending signal to Telegram...")
                    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                    print("✅ Signal sent!")
                    last_signal = msg
        except Exception as e:
            print("🔥 LOOP ERROR:", e)
            traceback.print_exc()
        
        time.sleep(60)

# =========================
# 🚀 Start
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
