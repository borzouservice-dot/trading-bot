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
CHAT_ID = os.getenv("CHAT_ID")

print("Bot starting...")
print(f"TOKEN exists: {bool(TOKEN)}")
print(f"CHAT_ID exists: {bool(CHAT_ID)}")

if not TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN is not set!")
if not CHAT_ID:
    print("❌ ERROR: CHAT_ID is not set!")

bot = Bot(token=TOKEN)
CHAT_ID = int(CHAT_ID) if CHAT_ID else None

# =========================
# 🌐 Flask
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

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
            timeout=10
        )
        r.raise_for_status()
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
        return 50.0
    df = pd.DataFrame(prices, columns=["c"])
    delta = df["c"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    return float(rsi)

# =========================
# 🎯 Signal
# =========================
def generate_signal(price):
    price_history.append(price)
    if len(price_history) > 100:   # افزایش ظرفیت تاریخچه
        price_history.pop(0)
    
    rsi = calculate_rsi(price_history)
    print(f"PRICE: {price} | RSI: {rsi:.2f}")
    
    if rsi < 30:
        return f"🟢 **BUY SIGNAL**\nBTC: {price:.2f} USDT\nRSI: {rsi:.2f}"
    elif rsi > 70:
        return f"🔴 **SELL SIGNAL**\nBTC: {price:.2f} USDT\nRSI: {rsi:.2f}"
    return None

# =========================
# 🔁 Bot loop
# =========================
def run_bot():
    print("run_bot started")
    last_signal = None
    
    while True:
        try:
            price = get_price()
            if price:
                msg = generate_signal(price)
                if msg and msg != last_signal:   # جلوگیری از تکرار سیگنال
                    print("SIGNAL:", msg)
                    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                    last_signal = msg
                # else:
                #     print("No signal or duplicate")
        except Exception as e:
            print("LOOP ERROR:", e)
            import traceback
            traceback.print_exc()
        
        time.sleep(60)

# =========================
# 🚀 MAIN
# =========================
if __name__ == "__main__":
    if not TOKEN or not CHAT_ID:
        print("❌ Cannot start bot: Missing environment variables")
    else:
        threading.Thread(target=run_web, daemon=True).start()
        run_bot()
