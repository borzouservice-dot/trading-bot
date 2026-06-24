import ccxt
import asyncio
import pandas as pd
import numpy as np
import logging
import time
from dataclasses import dataclass
from typing import Optional
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
INTERVAL = 30
REPORT_INTERVAL = 600

bot = Bot(token=TOKEN)
exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("LEVEL24.1")

# ================= STATE =================
@dataclass
class Position:
    symbol: str
    entry: float
    size: float
    side: str
    sl: float
    tp: float
    trailing_sl: float

class Portfolio:
    def __init__(self):
        self.balance = 1000.0
        self.positions: dict[str, Position] = {}
        self.trades: list[float] = []      # closed PnLs
        self.equity: list[float] = [1000.0]

portfolio = Portfolio()

# ================= DATA =================
def get_data(symbol: str):
    ohlcv = exchange.fetch_ohlcv(symbol, "1m", limit=200)
    df = pd.DataFrame(ohlcv, columns=["t", "o", "h", "l", "c", "v"])
    df[["o", "h", "l", "c"]] = df[["o", "h", "l", "c"]].astype(float)
    return df

# ================= INDICATORS =================
def atr(df, period=14):
    high = df["h"]
    low = df["l"]
    close = df["c"]
    tr = np.maximum.reduce([
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift())
    ])
    val = tr.rolling(period).mean().iloc[-1]
    return float(val) if not np.isnan(val) else float(df["c"].iloc[-1] * 0.015)

# ================= STRATEGY =================
def strategy(df):
    price = float(df["c"].iloc[-1])
    
    ema9 = df["c"].ewm(span=9, adjust=False).mean().iloc[-1]
    ema21 = df["c"].ewm(span=21, adjust=False).mean().iloc[-1]
    
    vol = df["c"].pct_change().tail(30).std()
    
    score = 50
    if ema9 > ema21:
        score += 30
        signal = "LONG"
    else:
        score -= 30
        signal = "SHORT"
    
    if vol < 0.0018:
        score += 15
    elif vol > 0.0045:
        score -= 20
    
    if score < 68:
        signal = "WAIT"
    
    return signal, round(score, 1), price

# ================= POSITION MANAGEMENT =================
def position_size(balance: float, atr_val: float, price: float) -> float:
    risk_amount = 0.01 * balance          # 1% risk per trade
    stop_distance = atr_val * 2.0
    size_in_usdt = risk_amount / stop_distance * price   # درست
    return max(5.0, round(size_in_usdt / price, 4))      # حداقل اندازه منطقی

def open_position(symbol: str, signal: str, price: float, atr_val: float):
    if symbol in portfolio.positions:
        return
    
    size = position_size(portfolio.balance, atr_val, price)
    risk_dist = atr_val * 2.0
    
    sl = price - risk_dist if signal == "LONG" else price + risk_dist
    tp = price + risk_dist * 3 if signal == "LONG" else price - risk_dist * 3
    
    portfolio.positions[symbol] = Position(
        symbol=symbol,
        entry=price,
        size=size,
        side=signal,
        sl=sl,
        tp=tp,
        trailing_sl=sl
    )
    log.info(f"OPEN {symbol} {signal} | Size: {size:.4f} | Entry: {price:.4f}")

def close_position(symbol: str, price: float, reason: str = "EXIT"):
    pos = portfolio.positions[symbol]
    if pos.side == "LONG":
        pnl = (price - pos.entry) * pos.size
    else:
        pnl = (pos.entry - price) * pos.size
    
    fee = abs(pnl) * 0.002  # 0.1% round trip
    pnl -= fee
    
    portfolio.balance += pnl
    portfolio.trades.append(pnl)
    portfolio.equity.append(portfolio.balance)
    del portfolio.positions[symbol]
    
    log.info(f"CLOSE {symbol} | {reason} | PnL: {pnl:.2f} USDT")

def manage_positions(df: pd.DataFrame, symbol: str):
    if symbol not in portfolio.positions:
        return
    
    price = float(df["c"].iloc[-1])
    pos = portfolio.positions[symbol]
    atr_val = atr(df)
    
    # Trailing Stop (بهبود یافته)
    if pos.side == "LONG":
        new_sl = price - atr_val * 2
        if new_sl > pos.trailing_sl:
            pos.trailing_sl = new_sl
            pos.sl = max(pos.sl, new_sl)
    else:
        new_sl = price + atr_val * 2
        if new_sl < pos.trailing_sl:
            pos.trailing_sl = new_sl
            pos.sl = min(pos.sl, new_sl)
    
    # Stop Loss
    if (pos.side == "LONG" and price <= pos.sl) or (pos.side == "SHORT" and price >= pos.sl):
        close_position(symbol, price, "SL")
        return
    
    # Take Profit
    if (pos.side == "LONG" and price >= pos.tp) or (pos.side == "SHORT" and price <= pos.tp):
        close_position(symbol, price, "TP")
        return

# ================= METRICS =================
def metrics():
    if not portfolio.trades:
        return 0.0, 0.0, portfolio.balance
    wins = [t for t in portfolio.trades if t > 0]
    winrate = len(wins) / len(portfolio.trades)
    eq = np.array(portfolio.equity)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    return winrate, float(np.max(dd)), portfolio.balance

# ================= DASHBOARD =================
def dashboard():
    winrate, dd, eq = metrics()
    open_pos = len(portfolio.positions)
    total_pnl = sum(portfolio.trades)
    
    return f"""
🚀 **LEVEL 24.1 MULTI-ASSET ENGINE**
💰 Equity: **{eq:.2f} USDT**
📈 Total PnL: **{total_pnl:.2f}**
🟢 WinRate: **{winrate:.1%}**
📉 Max Drawdown: **{dd:.2f}**
📊 Closed Trades: **{len(portfolio.trades)}**
📌 Open Positions: **{open_pos}**
"""

# ================= TELEGRAM =================
async def send(msg: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ================= MAIN LOOP =================
async def run():
    await send("🚀 **LEVEL 24.1 STARTED**\nMulti-Symbol + ATR + SL/TP/Trailing Active")
    
    last_report = time.time()
    
    while True:
        try:
            for symbol in SYMBOLS:
                df = get_data(symbol)
                signal, score, price = strategy(df)
                atr_val = atr(df)
                
                manage_positions(df, symbol)
                
                if signal != "WAIT":
                    open_position(symbol, signal, price, atr_val)
                
                # Live Log
                pos_status = f"POS:{portfolio.positions[symbol].side}" if symbol in portfolio.positions else "NO_POS"
                print(f"📡 {symbol:<10} | {signal:5} | Score:{score:5.1f} | Price:{price:.4f} | Bal:{portfolio.balance:.2f} | {pos_status}")
                log.info(f"{symbol} | {signal} | Score:{score} | Price:{price:.4f} | Bal:{portfolio.balance:.2f}")
            
            if time.time() - last_report > REPORT_INTERVAL:
                await send(dashboard())
                last_report = time.time()
                
        except Exception as e:
            log.error(f"Main loop error: {e}")
            await asyncio.sleep(10)
        
        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(run())
