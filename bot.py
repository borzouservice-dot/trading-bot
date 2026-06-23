import ccxt
import pandas as pd
import numpy as np
import logging
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

# ================= CONFIG =================
SYMBOL = "SOL/USDT"
TIMEFRAME = "1m"

exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("LEVEL23")

# ================= DATA =================
def load_data(limit=300):  # کاهش برای VPS
    log.info("📡 Fetching data...")
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
    log.info(f"📊 Data loaded: {len(df)} rows")
    return df

# ================= FEATURES =================
def create_features(df):

    df["ret"] = df["c"].pct_change()
    df["ema9"] = df["c"].ewm(span=9).mean()
    df["ema21"] = df["c"].ewm(span=21).mean()
    df["vol"] = df["ret"].rolling(10).std()

    df["target"] = np.where(df["c"].shift(-1) > df["c"], 1, 0)

    df = df.dropna()

    X = df[["ema9","ema21","vol"]]
    y = df["target"]

    log.info(f"🧠 Features ready: {len(df)} samples")

    return X, y, df

# ================= MODEL =================
def train_model(X, y):

    log.info("🧠 Training model...")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    model = LogisticRegression()
    model.fit(X_train, y_train)

    acc = model.score(X_test, y_test)

    log.info(f"✅ Model Accuracy: {acc:.2f}")

    return model, X_test, y_test

# ================= BACKTEST =================
def backtest(model, X_test, df):

    preds = model.predict(X_test)

    df_bt = df.iloc[-len(preds):].copy()
    df_bt["pred"] = preds

    df_bt["strategy_ret"] = df_bt["pred"] * df_bt["ret"].shift(-1)

    equity = (1 + df_bt["strategy_ret"].fillna(0)).cumprod()

    return df_bt, equity

# ================= METRICS =================
def metrics(df_bt):

    total_return = df_bt["strategy_ret"].sum()
    winrate = (df_bt["strategy_ret"] > 0).mean()

    log.info(f"📊 Return: {total_return:.3f}")
    log.info(f"📈 WinRate: {winrate:.2f}")

    return total_return, winrate

# ================= RUN =================
def run():

    log.info("🚀 LEVEL 23 STARTED")

    df = load_data()

    X, y, df_clean = create_features(df)

    model, X_test, y_test = train_model(X, y)

    df_bt, equity = backtest(model, X_test, df_clean)

    total_return, winrate = metrics(df_bt)

    log.info("📊 FINAL EQUITY END VALUE:")
    log.info(float(equity.iloc[-1]))

    log.info("✅ LEVEL 23 FINISHED SUCCESSFULLY")

# ================= START =================
if __name__ == "__main__":
    run()
