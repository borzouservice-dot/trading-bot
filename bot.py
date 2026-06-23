import ccxt
import pandas as pd
import numpy as np
import logging
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt

# ================= CONFIG =================
SYMBOL = "SOL/USDT"
TIMEFRAME = "1m"

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LEVEL23")

# ================= LOAD DATA =================
def load_data(limit=1000):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    return df

# ================= FEATURES =================
def create_features(df):

    df["ret"] = df["c"].pct_change()
    df["ema9"] = df["c"].ewm(span=9).mean()
    df["ema21"] = df["c"].ewm(span=21).mean()
    df["vol"] = df["ret"].rolling(10).std()

    df["target"] = np.where(df["c"].shift(-1) > df["c"], 1, 0)

    df = df.dropna()

    features = df[["ema9","ema21","vol"]]
    labels = df["target"]

    return features, labels, df

# ================= TRAIN MODEL =================
def train_model(X, y):

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = LogisticRegression()
    model.fit(X_train, y_train)

    acc = model.score(X_test, y_test)

    log.info(f"MODEL ACCURACY: {acc:.2f}")

    return model, X_test, y_test

# ================= BACKTEST =================
def backtest(model, X_test, df_test):

    preds = model.predict(X_test)

    df_test = df_test.iloc[-len(preds):].copy()
    df_test["pred"] = preds

    df_test["strategy_ret"] = df_test["pred"] * df_test["ret"].shift(-1)

    equity = (1 + df_test["strategy_ret"].fillna(0)).cumprod()

    return df_test, equity

# ================= METRICS =================
def metrics(df_test):

    total_return = df_test["strategy_ret"].sum()

    winrate = (df_test["strategy_ret"] > 0).mean()

    max_dd = (df_test["strategy_ret"].cumsum() - df_test["strategy_ret"].cumsum().cummax()).min()

    return total_return, winrate, max_dd

# ================= RUN =================
def run():

    df = load_data()

    X, y, df_clean = create_features(df)

    model, X_test, y_test = train_model(X, y)

    df_test, equity = backtest(model, X_test, df_clean)

    total_return, winrate, max_dd = metrics(df_test)

    print("\n🚀 LEVEL 23 BACKTEST RESULTS")
    print(f"Return: {total_return:.2f}")
    print(f"WinRate: {winrate:.2f}")
    print(f"Max Drawdown: {max_dd:.2f}")

    # equity curve
    plt.plot(equity.values)
    plt.title("Equity Curve - LEVEL 23")
    plt.show()

# ================= START =================
if __name__ == "__main__":
    run()
