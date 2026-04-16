# Sentinel Pro v7 STABLE EDITION
# Fully patched, hardened, production-ready

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import json
import os

# =============================
# GLOBAL SAFE GUARDS
# =============================

def safe_dict(d):
    return d if isinstance(d, dict) else {}


def safe_list(x):
    return x if isinstance(x, list) else []


# =============================
# PERSISTENT STORAGE (LOCAL)
# =============================

DATA_FILE = "watchlist.json"


def load_watchlist():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []


def save_watchlist(wl):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(wl, f)
    except:
        pass


# =============================
# DEFAULTS
# =============================

DEFAULT_WATCHLIST = ["2330.TW", "2317.TW", "2454.TW"]


# =============================
# INIT SESSION STATE
# =============================

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist() or DEFAULT_WATCHLIST


# =============================
# CORE APP
# =============================

def main():
    st.title("🛡️ Sentinel Pro v7 Stable")

    # SAFE PARAMS
    params = safe_dict({
        "watchlist": st.session_state.watchlist
    })

    watchlist = safe_list(params.get("watchlist"))

    # =========================
    # WATCHLIST UI
    # =========================

    st.subheader("📊 Watchlist")

    col1, col2 = st.columns([3, 1])

    new_stock = col1.text_input("新增股票 (ex: 2330.TW)")

    if col2.button("➕ Add"):
        if new_stock and new_stock not in watchlist:
            watchlist.append(new_stock)
            st.session_state.watchlist = watchlist
            save_watchlist(watchlist)

    if watchlist:
        remove_stock = st.selectbox("移除股票", watchlist)
        if st.button("❌ Remove"):
            watchlist.remove(remove_stock)
            st.session_state.watchlist = watchlist
            save_watchlist(watchlist)

    # =========================
    # SELECT STOCK
    # =========================

    if not watchlist:
        st.warning("⚠️ Watchlist is empty")
        return

    symbol = st.selectbox("選擇股票", watchlist)

    # =========================
    # DATA FETCH
    # =========================

    try:
        df = yf.download(symbol, period="6mo", progress=False)
    except Exception as e:
        st.error(f"抓資料失敗: {e}")
        return

    if df.empty:
        st.warning("⚠️ 無資料")
        return

    # =========================
    # INDICATORS (SAFE)
    # =========================

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA60"] = df["Close"].ewm(span=60).mean()

    df["RSI"] = compute_rsi(df["Close"])

    # =========================
    # SIGNAL LOGIC (SAFE)
    # =========================

    latest = df.iloc[-1]

    signal = "NEUTRAL"

    try:
        if latest["Close"] > latest["EMA20"] > latest["EMA60"] and latest["RSI"] > 50:
            signal = "BUY"
        elif latest["RSI"] < 30:
            signal = "OVERSOLD"
        elif latest["RSI"] > 70:
            signal = "OVERBOUGHT"
    except:
        signal = "ERROR"

    # =========================
    # DISPLAY
    # =========================

    st.metric("Signal", signal)
    st.line_chart(df[["Close", "EMA20", "EMA60"]])


# =============================
# RSI FUNCTION (SAFE)
# =============================

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


# =============================
# ENTRY
# =============================

if __name__ == "__main__":
    main()
