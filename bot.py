import ccxt
import asyncio
import pandas as pd
import logging
import time
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SOL/USDT"

INTERVAL = 30
STATUS_INTERVAL = 1800

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL22.5")

def get_data(limit=150):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    return pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

def strategy_score(df):
    price = df["c"].iloc[-1]

    ema_fast = df["c"].ewm(span=9).mean().iloc[-1]
    ema_slow = df["c"].ewm(span=21).mean().iloc[-1]

    score = 50

    if ema_fast > ema_slow:
        score += 20
    else:
        score -= 20

    signal = "WAIT"
    if score >= 70:
        signal = "LONG"
    elif score <= 30:
        signal = "SHORT"

    return signal, score, price

async def send(msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        log.error(e)

async def run():

    await send("🚀 LEVEL 22.5 STARTED")

    last_signal = None

    while True:

        try:
            df = get_data()

            signal, score, price = strategy_score(df)

            current = f"{signal}_{score}"

            log.info(f"{signal} | {score} | {price}")

            if current != last_signal:

                msg = f"""
🚀 SOL/USDT

{signal}

📊 Score: {score}
📍 Price: {price}

LEVEL 22.5
"""

                await send(msg)
                last_signal = current

        except Exception as e:
            log.error(e)

        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
