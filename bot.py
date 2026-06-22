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
# 💰 Price Fetcher - چند API با timeout کوتاه
# =========================
def get_price():
    apis = [
        ("Binance", "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"),
        ("Binance Mirror", "https://api1.binance.com/api/v3/ticker/price?symbol=BTCUSDT"),
        ("CoinGecko", "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"),
        ("CoinPaprika", "https://api.coinpaprika.com/v1/tickers/btc-bitcoin"),
    ]
    
    for name, url in apis:
        try:
            print(f"📡 Trying {name}...")
            r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
            
            print(f"   {name} Status: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                if name == "Binance" or name == "Binance Mirror":
                    price = float(data["price"])
                elif name == "CoinGecko":
                    price = float(data["bitcoin"]["usd"])
                else:  # CoinPaprika
                    price = float(data["quotes"]["USD"]["price"])
                
                print(f"✅ {name} Success → ${price:,.2f}")
                return price
        except Exception as e:
            print(f"   {name} Failed: {type(e).__name__}")
            continue  # بعدی رو امتحان کن
    
    print("❌ All price APIs failed")
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
    print("🔄 Bot loop started (every 2 minutes)")
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
                except Exception as te:
                    print("Telegram Error:", te)
            else:
                print("ℹ️ No new signal")
        else:
            print("⚠️ Price fetch failed this round")

        time.sleep(120)

# =========================
# 🚀 Start
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
