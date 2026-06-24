```python
import ccxt
import asyncio
import pandas as pd
import logging
import time
from telegram import Bot
from dotenv import load_dotenv
import os

# ================= CONFIG =================
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

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("LEVEL22.5")

# ================= DATA =================
def get_data(limit=150):

    ohlcv = exchange.fetch_ohlcv(
        SYMBOL,
        timeframe="1m",
        limit=limit
    )

    return pd.DataFrame(
        ohlcv,
        columns=["t", "o", "h", "l", "c", "v"]
    )

# ================= AI SCORE =================
def strategy_score(df):

    price = float(df["c"].iloc[-1])

    ema_fast = df["c"].ewm(span=9).mean().iloc[-1]
    ema_slow = df["c"].ewm(span=21).mean().iloc[-1]

    returns = df["c"].pct_change()
    vol = returns.std()

    score = 50

    if ema_fast > ema_slow:
        score += 20
        trend = "BULLISH"
    else:
        score -= 20
        trend = "BEARISH"

    if vol < 0.002:
        score += 10
    else:
        score -= 10

    high_mean = df["h"].rolling(20).mean().iloc[-1]
    low_mean = df["l"].rolling(20).mean().iloc[-1]

    if price > high_mean:
        score += 10

    if price < low_mean:
        score -= 10

    if score >= 70:
        signal = "LONG"
    elif score <= 30:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return signal, score, price, trend

# ================= WIN EST =================
def pseudo_backtest(df):

    returns = df["c"].pct_change()

    wr = (
        (returns > 0)
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    if pd.isna(wr):
        return 0.50

    return float(wr)

# ================= REGIME =================
def market_regime(df):

    volatility = df["c"].pct_change().std()

    if volatility < 0.001:
        return "RANGE"

    if volatility > 0.005:
        return "VOLATILE"

    return "TREND"

# ================= FORMAT SIGNAL =================
def format_signal(signal,
                  score,
                  price,
                  trend,
                  win_rate,
                  regime):

    sl = price * 0.99

    if signal == "LONG":

        tp1 = price * 1.01
        tp2 = price * 1.02
        tp3 = price * 1.03

        side = "🟢 LONG 📈"

    elif signal == "SHORT":

        tp1 = price * 0.99
        tp2 = price * 0.98
        tp3 = price * 0.97

        side = "🔴 SHORT 📉"

    else:

        return f"""
📊 SOL/USDT

⚪ WAIT

⚡ AI Score: {score}/100
📈 Trend: {trend}

🧠 Regime: {regime}

📡 LEVEL 22.5 AI ENGINE
"""

    return f"""
🚀 SOL/USDT

{side}

📍 Entry: Market

⚡ AI Score: {score}/100
📊 Trend: {trend}
📈 Win Est: {win_rate:.2f}

🔥 Risk: 1%
⚖️ Leverage: x1

⛔ Stop Loss: {sl:.2f}

🎯 TP1: {tp1:.2f}
🎯 TP2: {tp2:.2f}
🎯 TP3: {tp3:.2f}

🧠 Market Regime: {regime}

📡 LEVEL 22.5 AI ENGINE
"""

# ================= STATUS =================
def format_status(score):

    return f"""
📊 SYSTEM STATUS

🟢 ONLINE

🚀 Symbol: SOL/USDT

📈 Last Score: {score}

🧠 Engine: LEVEL 22.5

⏰ Running Normally
"""

# ================= TELEGRAM =================
async def send(msg):

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=msg
        )

    except Exception as e:
        log.error(f"Telegram Error: {e}")

# ================= LOOP =================
async def run():

    await send(
"""
🚀 BOT STARTED

🧠 LEVEL 22.5 ACTIVE

🚀 SYMBOL: SOL/USDT

📡 SYSTEM ONLINE
⚡ READY FOR SIGNALS
"""
    )

    last_signal = None
    last_status = time.time()

    while True:

        try:

            df = get_data()

            signal, score, price, trend = strategy_score(df)

            win_rate = pseudo_backtest(df)

            regime = market_regime(df)

            current_signal = f"{signal}_{score}"

            log.info(
                f"{signal} | Score:{score} | Price:{price}"
            )

            if current_signal != last_signal:

                msg = format_signal(
                    signal,
                    score,
                    price,
                    trend,
                    win_rate,
                    regime
                )

                await send(msg)

                last_signal = current_signal

            if time.time() - last_status > STATUS_INTERVAL:

                await send(
                    format_status(score)
                )

                last_status = time.time()

        except Exception as e:

            log.error(f"ERROR: {e}")

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
```
