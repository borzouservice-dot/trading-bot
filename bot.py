import os
import time
import pickle
import asyncio
import random
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
import ccxt

# ================= CONFIG =================
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
INTERVAL = 10

bot = Bot(token=TOKEN)

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= PERSISTENT Q TABLE =================
Q_FILE = "qtable.pkl"

def load_q():
    if os.path.exists(Q_FILE):
        try:
            with open(Q_FILE, "rb") as f:
                return pickle.load(f)
        except:
            return {}
    return {}

def save_q():
    with open(Q_FILE, "wb") as f:
        pickle.dump(q_table, f)

q_table = load_q()

# ================= STATE =================
positions = []
equity = 1000

stats = {"wins": 0, "losses": 0, "total": 0}

ACTIONS = ["LONG", "SHORT", "HOLD"]

# ================= MARKET =================
def get_price(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=1)
    return ohlcv[-1][4]

# ================= STATE ENCODING =================
def get_state(price):
    return (
        int(price % 2 > 1),
        int(price % 3 > 1),
        int(price % 5 > 1)
    )

# ================= Q =================
def get_q(state, action):
    return q_table.get((state, action), 0.0)

def choose_action(state):
    if random.random() < 0.1:
        return random.choice(ACTIONS)

    q_vals = [get_q(state, a) for a in ACTIONS]
    return ACTIONS[q_vals.index(max(q_vals))]

def update_q(state, action, reward):
    old = q_table.get((state, action), 0.0)
    q_table[(state, action)] = old + 0.1 * (reward - old)

# ================= TRADE =================
def open_trade(symbol, action, price):
    return {
        "symbol": symbol,
        "action": action,
        "entry": price,
        "tp": price * (1.003),
        "sl": price * (0.998),
        "state": get_state(price)
    }

def close_trade(trade, price):
    global equity, stats

    pnl = (price - trade["entry"]) if trade["action"] == "LONG" else (trade["entry"] - price)

    reward = pnl

    update_q(trade["state"], trade["action"], reward)

    equity += pnl

    stats["total"] += 1

    if pnl > 0:
        stats["wins"] += 1
    else:
        stats["losses"] += 1

    save_q()

# ================= CHECK =================
def check_trades():

    global positions

    new = []

    for p in positions:

        price = get_price(p["symbol"])

        if price >= p["tp"] or price <= p["sl"]:
            close_trade(p, price)
            continue

        new.append(p)

    positions = new

# ================= BACKTEST (SIMPLE) =================
def quick_backtest():

    results = []

    for _ in range(50):

        price = random.uniform(50, 100)

        state = get_state(price)

        action = choose_action(state)

        reward = random.uniform(-1, 1)

        update_q(state, action, reward)

        results.append(reward)

    return sum(results)

# ================= REPORT =================
def report():

    wr = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0

    return f"""
📊 LEVEL 11 — HEDGE FUND MODE

💰 Equity: {equity:.2f}
📦 Positions: {len(positions)}

📈 Trades: {stats["total"]}
🟢 Wins: {stats["wins"]}
🔴 Losses: {stats["losses"]}
📊 WinRate: {wr:.2f}%

🧠 Q-STATES: {len(q_table)}

⚙️ Mode: REINFORCEMENT LEARNING ACTIVE
""".strip()

# ================= TELEGRAM =================
async def send(msg):
    try:
        await bot.send_message(CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ================= LOOP =================
async def run():

    global positions

    await send("🚀 LEVEL 11 STARTED\n🧠 HEDGE FUND RL ENGINE ACTIVE")

    quick_backtest()

    while True:

        check_trades()

        for symbol in SYMBOLS:

            price = get_price(symbol)

            state = get_state(price)

            action = choose_action(state)

            if action != "HOLD" and len(positions) < 5:

                trade = open_trade(symbol, action, price)
                positions.append(trade)

        if random.random() < 0.3 and positions:
            positions.pop(0)

        await asyncio.sleep(INTERVAL)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
