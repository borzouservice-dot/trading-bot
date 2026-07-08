# ==========================================
# TELEGRAM UI V4
# ==========================================

# ==========================================
# IMPORTS
# ==========================================

# ==========================================
# TELEGRAM UI V4.2
# ==========================================

# ==========================================
# IMPORTS
# ==========================================

import os
import psutil
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from storage import load_state

from controller import (
    start_bot,
    stop_bot,
    restart_bot,
    status_bot,
    logs_bot,
)

# ==========================================
# CONFIG
# ==========================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ==========================================
# STATUS
# ==========================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    s = load_state()

    trades = s["trades"]

    wr = 0

    if trades > 0:
        wr = round(
            s["wins"] /
            trades *
            100,
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

# ==========================================
# BALANCE
# ==========================================

async def balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    s = load_state()

    await update.message.reply_text(
        f"💰 Balance: {s['balance']:.2f}"
    )

# ==========================================
# POSITIONS
# ==========================================

async def positions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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

# ==========================================
# HEALTH
# ==========================================

async def health(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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
# ==========================================
# LOGS
# ==========================================

async def logs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = logs_bot(30)

    if not text.strip():

        text = "No logs available."

    if len(text) > 3900:

        text = text[-3900:]

    await update.message.reply_text(
        f"📄 Last Logs\n\n{text}"
    )

# ==========================================
# SERVICE STATUS
# ==========================================

async def service(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = status_bot()

    icon = "🟢"

    if state != "active":
        icon = "🔴"

    await update.message.reply_text(
        f"{icon} Service Status\n\n{state.upper()}"
    )

# ==========================================
# RESTART BOT
# ==========================================

async def restart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "♻️ Restarting TradingBot..."
    )

    ok = restart_bot()

    if ok:
        await update.message.reply_text(
            "✅ TradingBot restarted successfully"
        )
    else:
        await update.message.reply_text(
            "❌ Restart failed"
        )

# ==========================================
# START BOT
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "▶️ Starting TradingBot..."
    )

    ok = start_bot()

    if ok:
        await update.message.reply_text(
            "✅ TradingBot started"
        )
    else:
        await update.message.reply_text(
            "❌ Start failed"
        )

# ==========================================
# STOP BOT
# ==========================================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🛑 Stopping TradingBot..."
    )

    ok = stop_bot()

    if ok:
        await update.message.reply_text(
            "✅ TradingBot stopped"
        )
    else:
        await update.message.reply_text(
            "❌ Stop failed"
        )

  

# ==========================================
# APP
# ==========================================

app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)

# ==========================================
# HANDLERS
# ==========================================

app.add_handler(CommandHandler("status", status))

app.add_handler(CommandHandler("service", service))

app.add_handler(CommandHandler("balance", balance))

app.add_handler(CommandHandler("positions", positions))

app.add_handler(CommandHandler("health", health))

app.add_handler(CommandHandler("logs", logs))

app.add_handler(CommandHandler("start", start))

app.add_handler(CommandHandler("stop", stop))

app.add_handler(CommandHandler("restart", restart))

# ==========================================
# START UI
# ==========================================

print("Telegram UI V4.2 Started")

app.run_polling()

# ==========================================
# START UI
# ==========================================

print(
    "Telegram UI Started"
)

app.run_polling()
