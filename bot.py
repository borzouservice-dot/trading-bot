import os
import ccxt
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------- ENV ----------------
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---------------- EXCHANGE ----------------
exchange = ccxt.bybit({
    "enableRateLimit": True
})

# ---------------- DATA ----------------
def get_data(symbol="BTC/USDT"):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=100)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    return df

# ---------------- ANALYSIS ----------------
def analyze():
    df = get_data()

    df["ema20"] = EMAIndicator(df["c"], 20).ema_indicator()
    df["ema50"] = EMAIndicator(df["c"], 50).ema_indicator()
    df["rsi"] = RSIIndicator(df["c"], 14).rsi()

    last = df.iloc[-1]

    price = last["c"]
    rsi = last["rsi"]

    signal = "⚪ NO TRADE"

    # روند
    uptrend = last["ema20"] > last["ema50"]
    downtrend = last["ema20"] < last["ema50"]

    # منطق سیگنال
    if uptrend and 40 < rsi < 70:
        signal = "🟢 BUY"

    elif downtrend and 30 < rsi < 60:
        signal = "🔴 SELL"

    return price, rsi, signal

# ---------------- TELEGRAM COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ربات سیگنال فعال شد")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price, rsi, sig = analyze()

    msg = f"""
📊 SIGNAL BOT

💰 Price: {price}
📈 RSI: {rsi:.2f}

🎯 Signal: {sig}
"""
    await update.message.reply_text(msg)

# ---------------- BOT SETUP ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("signal", signal))

print("Bot is running...")
app.run_polling()