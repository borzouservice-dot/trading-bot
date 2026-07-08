# ==========================================
# TELEGRAM UI V4.2
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

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in .env")

# ==========================================
# APP
# ==========================================

app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)

# ==========================================
# STATUS
# ==========================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    s = load_state()

    trades = s.get("trades", 0)
    wins = s.get("wins", 0)
    losses = s.get("losses", 0)

    wr = 0
    if trades:
        wr = round((wins / trades) * 100, 1)

    text = (
        "🤖 TradingBot V4\n\n"
        f"💰 Balance : {s.get('balance',0):.2f}\n"
        f"📈 Trades  : {trades}\n"
        f"✅ Wins    : {wins}\n"
        f"❌ Losses  : {losses}\n"
        f"🎯 WR      : {wr}%\n"
        f"📌 Open    : {len(s.get('positions', {}))}"
    )

    await update.message.reply_text(text)


# ==========================================
# BALANCE
# ==========================================

async def balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    s = load_state()

    await update.message.reply_text(
        f"💰 Balance : {s.get('balance',0):.2f}"
    )


# ==========================================
# POSITIONS
# ==========================================

async def positions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    s = load_state()

    pos = s.get("positions", {})

    if not pos:
        await update.message.reply_text(
            "📭 No Open Positions"
        )
        return

    msg = "📊 Open Positions\n\n"

    for symbol, p in pos.items():

        msg += (
            f"{symbol}\n"
            f"Side : {p['side']}\n"
            f"Entry: {p['entry']}\n\n"
        )

    await update.message.reply_text(msg)


# ==========================================
# HEALTH
# ==========================================

async def health(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    cpu = psutil.cpu_percent()

    ram = int(
        psutil.Process().memory_info().rss
        / 1024
        / 1024
    )

    await update.message.reply_text(

        f"❤️ System Health\n\n"
        f"CPU : {cpu}%\n"
        f"RAM : {ram} MB"
    )

# ==========================================
# LOGS
# ==========================================

async def logs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = logs_bot(30)

    if not text:
        text = "No logs."

    if len(text) > 3900:
        text = text[-3900:]

    await update.message.reply_text(
        f"📄 Last Logs\n\n{text}"
    )

# ==========================================
# SERVICE
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
        f"{icon} TradingBot Service\n\nStatus : {state}"
    )

# ==========================================
# START
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    ok = start_bot()

    if ok:
        await update.message.reply_text(
            "✅ TradingBot Started"
        )
    else:
        await update.message.reply_text(
            "❌ Failed To Start"
        )

# ==========================================
# STOP
# ==========================================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    ok = stop_bot()

    if ok:
        await update.message.reply_text(
            "🛑 TradingBot Stopped"
        )
    else:
        await update.message.reply_text(
            "❌ Failed To Stop"
        )

# ==========================================
# RESTART
# ==========================================

async def restart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    ok = restart_bot()

    if ok:
        await update.message.reply_text(
            "♻️ TradingBot Restarted"
        )
    else:
        await update.message.reply_text(
            "❌ Restart Failed"
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
# MAIN
# ==========================================

if __name__ == "__main__":

    print("🤖 Telegram UI V4.2 Started")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

