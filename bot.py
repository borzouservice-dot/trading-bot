import ccxt
import pandas as pd
import numpy as np
import logging
import traceback

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("LEVEL23-FIX")

SYMBOL = "SOL/USDT"
TIMEFRAME = "1m"

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ================= SAFE DATA =================
def load_data():
    try:
        log.info("📡 Fetching market data...")

        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=200)

        if not ohlcv:
            log.error("❌ EMPTY DATA FROM EXCHANGE")
            return None

        df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])

        log.info(f"📊 Data OK: {len(df)} rows")

        return df

    except Exception as e:
        log.error(f"❌ DATA ERROR: {e}")
        return None

# ================= SIMPLE SAFE MODEL =================
def simple_score(df):

    try:
        df["ret"] = df["c"].pct_change()
        df["ema9"] = df["c"].ewm(span=9).mean()
        df["ema21"] = df["c"].ewm(span=21).mean()

        last = df.iloc[-1]

        score = 50

        if last["ema9"] > last["ema21"]:
            score += 20
        else:
            score -= 20

        if df["ret"].std() < 0.01:
            score += 10
        else:
            score -= 10

        signal = "WAIT"
        if score > 65:
            signal = "LONG"
        elif score < 35:
            signal = "SHORT"

        return signal, score, float(last["c"])

    except Exception as e:
        log.error(f"❌ MODEL ERROR: {e}")
        log.error(traceback.format_exc())
        return "WAIT", 50, 0

# ================= RUN =================
def run():

    log.info("🚀 LEVEL 23 FIX STARTED")

    df = load_data()

    if df is None or len(df) < 50:
        log.warning("⚠️ Not enough data → SAFE EXIT")
        print("LEVEL 23: NO DATA BUT SYSTEM IS RUNNING 🟡")
        return

    signal, score, price = simple_score(df)

    print("\n======================")
    print("🚀 LEVEL 23 OUTPUT")
    print("======================")
    print(f"Symbol: {SYMBOL}")
    print(f"Signal: {signal}")
    print(f"Score: {score}")
    print(f"Price: {price}")
    print("======================\n")

    log.info("✅ LEVEL 23 DONE")

# ================= START =================
if __name__ == "__main__":
    run()
