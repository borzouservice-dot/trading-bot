import os
import time
import random
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "SOL/USDT"

INTERVAL = 20
STATUS_INTERVAL = 300

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger(__name__)

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= STATE =================
q_table = {}
active_trade = None

stats = {"wins": 0, "losses": 0, "total": 0}


# ================= INDICATORS =================
def sma(data, n):
    return sum(data[-n:]) / n if len(data) >= n else None


def rsi(data, n=14):
    if len(data) < n + 1:
        return None

    gains, losses = [], []

    for i in range(1, len(data)):
        diff = data[i] - data[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[-n:]) / n
    avg_loss = sum(losses[-n:]) / n

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(highs, lows, closes, n=14):
    if len(closes) < n + 1:
        return None

    trs = []
    for i in range(1, len(closes)):
        trs.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        ))

    return sum(trs[-n:]) / n


# ================= STATE (MARKET) =================
def get_state(fast, slow, rsi_val, atr_val):

    return (
        int(fast > slow),
        int(rsi_val > 50),
        int(atr_val > 0)
    )


# ================= Q TABLE =================
ACTIONS = ["LONG", "SHORT", "HOLD"]


def get_q(state, action):
    return q_table.get((state, action), 0.0)


def choose_action(state, epsilon=0.1):

    if random.random() < epsilon:
        return random.choice(ACTIONS)

    q_values = [get_q(state, a) for a in ACTIONS]

    return ACTIONS[q_values.index(max(q_values))]


def update_q(state, action, reward, alpha=0.1):

    old = q_table.get((state, action), 0.0)

    q_table[(state, action)] = old + alpha * (reward - old)


# ================= DATA =================
def get_data():

    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe="1m", limit=100)

    closes = [c[4] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]

    return closes, highs, lows


# ================= REWARD =================
def get_reward(win, profit):

    return profit * 2 if win else -profit


# ================= AI ENGINE =================
def ai_engine(price, closes, highs, lows):

    fast = sma(closes, 8)
    slow = sma(closes, 21)
    r = rsi(closes, 14)
    a = atr(highs, lows, closes, 14)

    if None in [fast, slow, r, a]:
        return None, None, None

    state = get_state(fast, slow, r, a)

    action = choose_action(state)

    if action == "HOLD":
        return None, state, None

    sl = price - a * 1.5 if action == "LONG" else price + a * 1.5

    tp = [
        price + a if action == "LONG" else price - a,
        price + a * 2 if action == "LONG" else price - a * 2,
    ]

    return {
        "state": state,
        "action": action,
        "entry": price,
        "sl": sl,
        "tp": tp,
        "time": time.time()
    }, state, action


# ================= SIMULATION TRADE CHECK =================
def check_trade(price):

    global active_trade, stats

    if not active_trade:
        return

    t = active_trade

    if t["action"] == "LONG":

        if price >= t["tp"][0]:
            finish_trade(True, price)

        elif price <= t["sl"]:
            finish_trade(False, price)

    elif t["action"] == "SHORT":

        if price <= t["tp"][0]:
            finish_trade(True, price)

        elif price >= t["sl"]:
            finish_trade(False, price)


def finish_trade(win, price):

    global active_trade, stats

    entry = active_trade["entry"]

    profit = abs(price - entry)

    reward = get_reward(win, profit)

    update_q(active_trade["state"], active_trade["action"], reward)

    if win:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

    stats["total"] += 1

    active_trade["result"] = "WIN" if win else "LOSS"

    active_trade = None


# ================= FORMAT =================
def format_signal(t):

    emoji = "🟢" if t["action"] == "LONG" else "🔴"

    return f"""
🚀 BTC/USDT

{emoji} {t['action']} (RL AGENT)

📍 Entry: {t['entry']:.2f}

⛔ SL: {t['sl']:.2f}

🎯 TP1: {t['tp'][0]:.2f}
🎯 TP2: {t['tp'][1]:.2f}

🧠 State: {t['state']}
🤖 Mode: Q-Learning RL

""".strip()


# ================= REPORT =================
def report():

    if stats["total"] == 0:
        return "📊 No trades yet"

    wr = (stats["wins"] / stats["total"]) * 100

    return f"""
📊 RL PERFORMANCE

✅ Wins: {stats['wins']}
❌ Losses: {stats['losses']}
📈 WinRate: {wr:.2f}%

📦 Trades: {stats['total']}
Q-STATES: {len(q_table)}
""".strip()


# ================= TELEGRAM =================
async def send(msg):

    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.error(e)


# ================= MAIN LOOP =================
async def run():

    global active_trade

    await send("🚀 LEVEL 7 RL BOT ONLINE\n🧠 Q-Learning Agent ACTIVE")

    last_report = time.time()

    while True:

        closes, highs, lows = get_data()

        price = closes[-1]

        check_trade(price)

        if not active_trade:

            trade, state, action = ai_engine(price, closes, highs, lows)

            if trade:

                active_trade = trade

                await send(f"🚨 NEW RL TRADE\n\n{format_signal(trade)}")

        if time.time() - last_report > STATUS_INTERVAL:

            await send(report())

            last_report = time.time()

        await asyncio.sleep(INTERVAL)


# ================= START =================
if __name__ == "__main__":

    try:
        asyncio.run(run())
    except Exception as e:
        log.critical(e)
