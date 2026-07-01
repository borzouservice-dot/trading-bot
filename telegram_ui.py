import os
import psutil
import subprocess
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from storage import load_state

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    s = load_state()

    trades = s["trades"]

    wr = 0
    if trades > 0:
        wr = round(
            s["wins"] / trades * 100,
            1
        )

    msg = (
        "🤖 TradingBot V4\n\n"
        f"Balance: {s['balance']:.2f}\n"
        f"Trades: {trades}\n"
        f"Wins: {s['wins']}\n"
        f"Losses: {s['losses']}\n"
        f"WR: {wr}%\n"
        f"Open: {len(s['positions'])}"
    )

    await update.message.reply_text(msg)


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    s = load_state()

    await update.message.reply_text(
        f"💰 Balance: {s['balance']:.2f}"
    )


async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    s = load_state()

    if not s["positions"]:
        await update.message.reply_text(
            "No open positions"
        )
        return

    txt = "📊 Open Positions\n\n"

    for sym, p in s["positions"].items():

        txt += (
            f"{sym}\n"
            f"{p['side']}\n"
            f"Entry: {p['entry']}\n\n"
        )

    await update.message.reply_text(txt)


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cpu = psutil.cpu_percent()

    ram = int(
        psutil.Process()
        .memory_info()
        .rss
        / 1024 / 1024
    )

    await update.message.reply_text(
        f"❤️ HEALTH\n"
        f"CPU: {cpu}%\n"
        f"RAM: {ram}MB"
    )

async def restart(update, context):

    await update.message.reply_text(
        "♻️ Restarting TradingBot..."
    )

    subprocess.Popen(
        [
            "sudo",
            "systemctl",
            "restart",
            "tradingbot"
        ]
    )


async def stop(update, context):

    await update.message.reply_text(
        "🛑 Stopping TradingBot..."
    )

    subprocess.Popen(
        [
            "sudo",
            "systemctl",
            "stop",
            "tradingbot"
        ]
    )
app.add_handler(
    CommandHandler(
        "restart",
        restart
    )
)

app.add_handler(
    CommandHandler(
        "stop",
        stop
    )
)

app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)

app.add_handler(
    CommandHandler("status", status)
)

app.add_handler(
    CommandHandler("balance", balance)
)

app.add_handler(
    CommandHandler("positions", positions)
)

app.add_handler(
    CommandHandler("health", health)
)

print("Telegram UI Started")

app.run_polling()
