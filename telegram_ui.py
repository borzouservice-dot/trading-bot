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

    import asyncio
    import subprocess

    await update.message.reply_text(
        "♻️ Restart command sent..."
    )

    subprocess.Popen([
        "sudo",
        "systemctl",
        "restart",
        "tradingbot"
    ])

    await asyncio.sleep(3)

    try:

        status = subprocess.check_output(
            [
                "systemctl",
                "is-active",
                "tradingbot"
            ]
        ).decode().strip()

        if status == "active":

            await update.message.reply_text(
                "✅ TradingBot restarted successfully"
            )

        else:

            await update.message.reply_text(
                f"❌ Restart failed\n{status}"
            )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Restart check error\n{e}"
        )
async def stop(update, context):

    import asyncio
    import subprocess

    await update.message.reply_text(
        "🛑 Stop command sent..."
    )

    subprocess.Popen([
        "sudo",
        "systemctl",
        "stop",
        "tradingbot"
    ])

    await asyncio.sleep(3)

    try:

        status = subprocess.check_output(
            [
                "systemctl",
                "is-active",
                "tradingbot"
            ]
        ).decode().strip()

        if status == "inactive":

            await update.message.reply_text(
                "✅ TradingBot stopped"
            )

        else:

            await update.message.reply_text(
                f"❌ Stop failed\n{status}"
            )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Stop check error\n{e}"
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


print("Telegram UI Started")

app.run_polling()
