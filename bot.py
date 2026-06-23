import ccxt
import numpy as np
import pandas as pd
import asyncio
import time
import logging

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

log = logging.getLogger()

# ================= EXCHANGE =================
exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

SYMBOL = "SOL/USDT"

# ================= DATA =================
def get_ohlcv(limit=200):
    data = exchange.fetch_ohlcv(SYMBOL, "1m", limit=limit)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v"])
    return df

# ================= FEATURES =================
def build_features(df):

    df = df.copy()

    df["ret"] = df["c"].pct_change()
    df["vol"] = df["ret"].rolling(10).std()
    df["mom"] = df["c"] - df["c"].shift(5)

    df = df.dropna()

    X = df[["ret","vol","mom"]].values
    y = (df["c"].shift(-1) > df["c"]).astype(int).values[:-1]

    return X[:-1], y[:-1]

# ================= TRAIN =================
def train(X, y):

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    model = LogisticRegression()
    model.fit(Xs, y)

    return model, scaler

# ================= LIVE FEATURES SAFE =================
def live_features(df):

    ret = df["c"].pct_change().iloc[-1]
    vol = df["c"].pct_change().rolling(10).std().iloc[-1]
    mom = df["c"].iloc[-1] - df["c"].iloc[-5]

    # 🧠 FIX NaN
    if np.isnan(ret): ret = 0
    if np.isnan(vol): vol = 0
    if np.isnan(mom): mom = 0

    return np.array([ret, vol, mom]).reshape(1, -1)

# ================= MAIN =================
async def run():

    log.info("🚀 LEVEL 12 FIXED STARTED")

    df = get_ohlcv()

    X, y = build_features(df)

    model, scaler = train(X, y)

    log.info(f"📊 TRAIN DONE | samples={len(X)}")

    last_signal = None

    while True:

        try:
            df = get_ohlcv(100)

            latest = live_features(df)

            pred = model.predict(scaler.transform(latest))[0]

            signal = "LONG" if pred == 1 else "SHORT"

            price = df["c"].iloc[-1]

            if signal != last_signal:
                log.info(f"📡 SIGNAL: {signal} | PRICE: {price:.2f}")
                last_signal = signal
            else:
                log.info(f"⏳ HOLD | PRICE: {price:.2f}")

        except Exception as e:
            log.error(f"ERROR: {e}")

        await asyncio.sleep(10)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
