import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# ─────────────────────────────
# 🛡️ 安全工具
# ─────────────────────────────

def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, float) and np.isnan(x):
            return default
        return float(x)
    except:
        return default


def safe_download(ticker, period="6mo"):
    try:
        df = yf.download(ticker, period=period, progress=False)
        if df is None or df.empty:
            return None
        return df
    except:
        return None


# ─────────────────────────────
# 📊 指標
# ─────────────────────────────

def calc_cci(high, low, close, period=20):
    tp = (high + low + close) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    return (tp - ma) / (0.015 * md + 1e-10)


def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1).mean()
    avg_loss = loss.ewm(com=period - 1).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def calc_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ─────────────────────────────
# 🧠 策略（穩定版）
# ─────────────────────────────

def format_stop(atr_stop, avg_px):
    try:
        if atr_stop is None or np.isnan(atr_stop):
            return f"{avg_px * 0.93:.2f}（均成本-7%）"
        return f"{atr_stop:.2f}"
    except:
        return "均成本-7%"


def pro_strategy(cur_price, avg_px, shares, atr):
    cur_price = safe_float(cur_price)
    avg_px = safe_float(avg_px)
    shares = int(safe_float(shares))
    atr = safe_float(atr, None)

    unreal_p = (cur_price - avg_px) * shares

    stop_text = format_stop(atr, avg_px)

    return {
        "pnl": unreal_p,
        "plan": (
            f"📋 持有股數：{shares:,}\n"
            f"現價：{cur_price:.2f} / 成本：{avg_px:.2f}\n"
            f"未實現損益：{unreal_p:.0f}\n"
            f"停損：{stop_text}"
        )
    }


# ─────────────────────────────
# 🚀 主程式
# ─────────────────────────────

def run_app():
    st.set_page_config(page_title="Sentinel v6", layout="wide")

    st.title("📊 Sentinel Pro v6（穩定版）")

    ticker = st.text_input("股票代號", "2330.TW")

    if st.button("開始分析"):
        df = safe_download(ticker)

        if df is None:
            st.error("抓不到資料（可能停牌或代號錯）")
            return

        if len(df) < 30:
            st.warning("資料不足")
            return

        df["CCI"] = calc_cci(df["High"], df["Low"], df["Close"]).fillna(0)
        df["RSI"] = calc_rsi(df["Close"]).fillna(50)
        df["ATR"] = calc_atr(df["High"], df["Low"], df["Close"]).fillna(0)

        latest = df.iloc[-1]

        cur_price = latest["Close"]
        atr = latest["ATR"]

        avg_px = st.number_input("你的成本", value=float(cur_price))
        shares = st.number_input("持股數", value=1000)

        result = pro_strategy(cur_price, avg_px, shares, atr)

        st.subheader("📈 分析結果")

        st.metric("未實現損益", f"{result['pnl']:.0f}")

        st.text(result["plan"])

        try:
            st.line_chart(df["Close"])
        except:
            st.warning("圖表顯示失敗")


def main():
    try:
        run_app()
    except Exception as e:
        st.error("系統發生錯誤（已防護）")
        st.exception(e)


if __name__ == "__main__":
    main()