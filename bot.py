import ccxt
import numpy as np
import pandas as pd
import asyncio
import time
import random
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# ================= EXCHANGE =================
exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

SYMBOL = "SOL/USDT"

# ================= DATA =================
def get_ohlcv(limit=500):
    data = exchange.fetch_ohlcv(SYMBOL, timeframe="1m", limit=limit)
    df = pd.DataFrame(data, columns=["t","o","h","l","c","v"])
    return df

# ================= FEATURES =================
def create_features(df):

    df["return"] = df["c"].pct_change()
    df["volatility"] = df["return"].rolling(10).std()
    df["momentum"] = df["c"] - df["c"].shift(5)

    df["rsi"] = compute_rsi(df["c"], 14)

    df = df.dropna()

    X = df[["return","volatility","momentum","rsi"]].values
    y = (df["c"].shift(-1) > df["c"]).astype(int).values[:-1]

    return X[:-1], y[:-1]

# ================= RSI =================
def compute_rsi(series, period):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

# ================= TRAIN MODEL =================
def train_model(X, y):

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression()
    model.fit(X_scaled, y)

    return model, scaler

# ================= BACKTEST =================
def backtest(model, scaler, X, y):

    X_scaled = scaler.transform(X)

    preds = model.predict(X_scaled)

    returns = []

    for i in range(len(preds)):
        if preds[i] == y[i]:
            returns.append(1)
        else:
            returns.append(-1)

    returns = np.array(returns)

    winrate = (returns > 0).mean()
    sharpe = returns.mean() / (returns.std() + 1e-9)
    max_dd = min(returns.cumsum())

    return winrate, sharpe, max_dd

# ================= LIVE SIGNAL =================
def live_signal(model, scaler, latest):

    X = np.array([latest])
    X_scaled = scaler.transform(X)

    pred = model.predict(X_scaled)[0]

    return "LONG" if pred == 1 else "SHORT"

# ================= MAIN =================
async def run():

    print("🚀 LEVEL 12 STARTED — PRO QUANT SYSTEM")

    df = get_ohlcv()

    X, y = create_features(df)

    model, scaler = train_model(X, y)

    winrate, sharpe, dd = backtest(model, scaler, X, y)

    print("\n📊 BACKTEST RESULTS")
    print(f"WinRate: {winrate:.2f}")
    print(f"Sharpe: {sharpe:.2f}")
    print(f"MaxDrawdown: {dd:.2f}")

    while True:

        df = get_ohlcv(50)

        latest = df.iloc[-1]

        features = [
            df["c"].pct_change().iloc[-1],
            df["c"].pct_change().rolling(10).std().iloc[-1],
            df["c"].iloc[-1] - df["c"].iloc[-5],
            50  # placeholder RSI simplified
        ]

        signal = live_signal(model, scaler, features)

        price = df["c"].iloc[-1]

        print(f"📡 SIGNAL: {signal} | Price: {price:.2f}")

        await asyncio.sleep(10)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(run())
