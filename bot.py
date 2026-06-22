import os
import time
import requests
import pandas as pd
from flask import Flask
from telegram import Bot
import threading
import traceback
import random

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
# 💰 Price - CoinGecko + Retry
# =========================
def get_price(max_retries=3):
    for attempt in range(max_retries):
        try:
            print(f"📡 Fetching BTC price (attempt {attempt+1})...")
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if r.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"⏳ Rate limit (429), waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
                
            r.raise_for_status()
            price = float(r.json()["bitcoin"]["usd"])
            print(f"✅ Price: ${price:,.2f}")
            return price
            
        except Exception as e:
            print(f"❌ PRICE ERROR (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
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
        
        time.sleep(60)   # هر ۶۰ ثانیه

# =========================
# 🚀 Start
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
