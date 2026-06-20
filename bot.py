import os
import ccxt
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

exchange = ccxt.bybit({"enableRateLimit": True})


def get_price(symbol="BTC/USDT"):
    return exchange.fetch_ticker(symbol)["last"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ربات آنلاین شد")


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_price()

    if price % 2 == 0:
        sig = "🟢 BUY"
    else:
        sig = "🔴 SELL"

    await update.message.reply_text(f"💰 {price}\n🎯 {sig}")


app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("signal", signal))

print("Bot running...")
app.run_polling()
