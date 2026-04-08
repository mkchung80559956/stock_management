"""
Sentinel Pro — 台股多股掃描器 v2.1 (Hotfix)
修正 Plotly 不支援 8 位數 Hex 色碼導致的效能與崩潰問題
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import itertools
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Sentinel Pro 🛡️",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CUSTOM CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Noto+Sans+TC:wght@400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans TC', sans-serif;
}
.stApp { background-color: #0a0e1a; }

.sentinel-header {
    background: linear-gradient(135deg, #0d1226 0%, #141d3a 50%, #0d1226 100%);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 20px 28px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.sentinel-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #00d4ff, #0077ff, #00d4ff, transparent);
}
.sentinel-title {
    font-family: 'Space Mono', monospace;
    font-size: 1.9rem;
    font-weight: 700;
    color: #e8f4fd;
    margin: 0;
    letter-spacing: 0.05em;
}
.sentinel-sub {
    color: #5a8fb0;
    font-size: 0.85rem;
    margin-top: 4px;
    font-family: 'Space Mono', monospace;
}

.sig-strong-buy   { color: #00ff88; font-weight: 700; font-size: 0.95rem; }
.sig-buy          { color: #44ddff; font-weight: 600; }
.sig-breakout     { color: #ff9900; font-weight: 700; font-size: 0.95rem; }
.sig-fake         { color: #cc44ff; font-weight: 600; }
.sig-strong-sell  { color: #ff3355; font-weight: 700; font-size: 0.95rem; }
.sig-sell         { color: #ff8866; font-weight: 600; }
.sig-watch        { color: #ffee44; font-weight: 500; }
.sig-neutral      { color: #445566; }

.metric-box {
    background: #0d1a2d;
    border: 1px solid #1a3050;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: center;
}
.metric-label { color: #5a8fb0; font-size: 0.75rem; font-family: 'Space Mono', monospace; }
.metric-value { color: #e8f4fd; font-size: 1.4rem; font-weight: 600; font-family: 'Space Mono', monospace; margin-top: 2px; }
.metric-delta { font-size: 0.8rem; margin-top: 2px; }
.metric-delta.pos { color: #ff4455; }
.metric-delta.neg { color: #00cc66; }

.signal-legend {
    background: #0d1a2d;
    border: 1px solid #1a3050;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.8rem;
    line-height: 2;
}

.opt-card {
    background: linear-gradient(135deg, #0d2040, #0a1628);
    border: 1px solid #0066cc;
    border-radius: 10px;
    padding: 16px 20px;
    margin-top: 12px;
}
.opt-card h4 { color: #00aaff; font-family: 'Space Mono', monospace; margin: 0 0 8px 0; }

div[data-testid="stTabs"] button {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: #5a8fb0;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00d4ff;
    border-bottom-color: #00d4ff;
}

.stDataFrame { border-radius: 8px; overflow: hidden; }
div[data-testid="metric-container"] { background: #0d1a2d; border-radius: 8px; padding: 12px; border: 1px solid #1a3050; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# INDICATOR FUNCTIONS
# ══════════════════════════════════════════════

def calc_cci(high, low, close, period=39):
    tp = (high + low + close) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    return (tp - ma) / (0.015 * md + 1e-10)


def calc_rsi(close, period=6):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def calc_macd(close, fast=12, slow=26, signal=9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    macd = ema_f - ema_s
    sig  = macd.ewm(span=signal, adjust=False).mean()
    return macd, sig, macd - sig


def calc_bb(close, period=20, num_std=2.0):
    ma  = close.rolling(period).mean()
    std = close.rolling(period).std()
    return ma + num_std * std, ma, ma - num_std * std


def calc_ema(close, period):
    return close.ewm(span=period, adjust=False).mean()


def calc_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_vol_ma(volume, period=20):
    return volume.rolling(period).mean()


# ── Price-Action helpers ──────────────────────

def has_long_lower_shadow(open_, close, low, ratio=0.5):
    body         = (close - open_).abs().clip(lower=1e-8)
    lower_shadow = np.minimum(open_, close) - low
    return (lower_shadow >= body * ratio).astype(bool)


def is_bullish_engulf(open_, close):
    prev_open  = open_.shift(1)
    prev_close = close.shift(1)
    prev_body  = (prev_close - prev_open).clip(upper=0).abs()
    curr_body  = (close - open_).clip(lower=0)
    bearish_prev = prev_close < prev_open
    bullish_curr = close > open_
    engulf = (open_ <= prev_close) & (close >= prev_open)
    return (bearish_prev & bullish_curr & engulf & (curr_body > prev_body * 0.8)).astype(bool)


def has_long_upper_shadow(open_, close, high, ratio=0.5):
    body         = (close - open_).abs().clip(lower=1e-8)
    upper_shadow = high - np.maximum(open_, close)
    return (upper_shadow >= body * ratio).astype(bool)


def detect_bullish_divergence(price, cci, lookback=30):
    result = pd.Series(False, index=price.index)
    arr_p  = price.values
    arr_c  = cci.values
    n = len(arr_p)
    half = lookback // 2

    for i in range(lookback, n):
        window_p = arr_p[i - lookback : i]
        window_c = arr_c[i - lookback : i]
        prev_low_pos = int(np.argmin(window_p[:half]))
        curr_low = arr_p[i]
        prev_low = window_p[prev_low_pos]

        if np.isnan(arr_c[i]) or np.isnan(window_c[prev_low_pos]):
            continue
        if curr_low < prev_low * 0.995 and arr_c[i] > window_c[prev_low_pos] * 1.05:
            result.iloc[i] = True
    return result


def detect_bearish_divergence(price, cci, lookback=30):
    result = pd.Series(False, index=price.index)
    arr_p  = price.values
    arr_c  = cci.values
    n = len(arr_p)
    half = lookback // 2

    for i in range(lookback, n):
        window_p = arr_p[i - lookback : i]
        window_c = arr_c[i - lookback : i]
        prev_hi_pos = int(np.argmax(window_p[:half]))
        curr_hi = arr_p[i]
        prev_hi = window_p[prev_hi_pos]

        if np.isnan(arr_c[i]) or np.isnan(window_c[prev_hi_pos]):
            continue
        if curr_hi > prev_hi * 1.005 and arr_c[i] < window_c[prev_hi_pos] * 0.95:
            result.iloc[i] = True
    return result


# ══════════════════════════════════════════════
# SIGNAL GENERATION
# ══════════════════════════════════════════════

SIGNAL_ORDER = {
    "BREAKOUT_BUY": 0, "STRONG_BUY": 1, "BUY": 2, "DIV_BUY": 2,
    "WATCH": 5, "NEUTRAL": 6,
    "DIV_SELL": 3, "SELL": 3, "STRONG_SELL": 4, "FAKE_BREAKOUT": 5,
}

SIGNAL_LABEL = {
    "BREAKOUT_BUY":  "🟠 噴發買",
    "STRONG_BUY":    "🟢 強買",
    "BUY":           "🔵 買入",
    "DIV_BUY":       "🟢 底背離",
    "WATCH":         "⚪ 觀望",
    "NEUTRAL":       "─",
    "DIV_SELL":      "🔴 頂背離",
    "SELL":          "🟡 賣出",
    "STRONG_SELL":   "🔴 強賣",
    "FAKE_BREAKOUT": "🟣 誘多",
}


def generate_signals(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    df = df.copy()
    df["CCI"]       = calc_cci(df["High"], df["Low"], df["Close"], p["cci_period"])
    df["RSI"]       = calc_rsi(df["Close"], p["rsi_period"])
    df["Vol_MA"]    = calc_vol_ma(df["Volume"], p["vol_ma_period"])
    df["ATR"]       = calc_atr(df["High"], df["Low"], df["Close"], 14)
    df["EMA1"]      = calc_ema(df["Close"], p["ema1"])
    df["EMA2"]      = calc_ema(df["Close"], p["ema2"])
    bb_u, bb_m, bb_l = calc_bb(df["Close"], p["bb_period"])
    df["BB_Upper"], df["BB_Mid"], df["BB_Lower"] = bb_u, bb_m, bb_l
    m, ms, mh       = calc_macd(df["Close"], p["macd_fast"], p["macd_slow"], p["macd_signal"])
    df["MACD"], df["MACD_Sig"], df["MACD_Hist"] = m, ms, mh

    vol_ratio            = df["Volume"] / (df["Vol_MA"] + 1e-8)
    df["Vol_High"]       = vol_ratio >= p["vol_multiplier"]
    df["Vol_Strong"]     = vol_ratio >= p["vol_strong_multiplier"]
    df["Vol_Shrink"]     = vol_ratio < 0.8

    cci_prev = df["CCI"].shift(1)
    df["CCI_X_neg100_UP"]  = (cci_prev < -100) & (df["CCI"] >= -100)
    df["CCI_X_zero_UP"]    = (cci_prev <    0) & (df["CCI"] >=    0)
    df["CCI_X_pos100_UP"]  = (cci_prev <  100) & (df["CCI"] >=  100)
    df["CCI_X_pos100_DN"]  = (cci_prev >= 100) & (df["CCI"] <   100)

    df["LowerShadow"]  = has_long_lower_shadow(df["Open"], df["Close"], df["Low"])
    df["BullEngulf"]   = is_bullish_engulf(df["Open"], df["Close"])
    df["UpperShadow"]  = has_long_upper_shadow(df["Open"], df["Close"], df["High"])
    df["PriceUp"]      = df["Close"] > df["Close"].shift(1)
    df["PriceUp_VolDN"]= df["PriceUp"] & (df["Volume"] < df["Volume"].shift(1))
    df["BlackCandle"]  = df["Close"] < df["Open"]

    if p.get("use_divergence", True):
        df["BullDiv"] = detect_bullish_divergence(df["Close"], df["CCI"], lookback=p.get("div_lookback", 25))
        df["BearDiv"] = detect_bearish_divergence(df["Close"], df["CCI"], lookback=p.get("div_lookback", 25))
    else:
        df["BullDiv"] = False
        df["BearDiv"] = False

    sig    = pd.Series("NEUTRAL", index=df.index)
    detail = pd.Series("",        index=df.index)

    m1 = df["CCI_X_pos100_UP"] & df["Vol_Strong"]
    sig[m1]    = "BREAKOUT_BUY"
    detail[m1] = "噴發段：CCI突破+100 + 強放量"

    m2 = df["CCI_X_pos100_UP"] & ~df["Vol_High"]
    sig[m2]    = "FAKE_BREAKOUT"
    detail[m2] = "誘多警告：CCI突破+100 but 量不配合"

    m3 = df["CCI_X_neg100_UP"] & df["Vol_High"] & (df["LowerShadow"] | df["BullEngulf"])
    sig[m3 & (sig == "NEUTRAL")] = "STRONG_BUY"
    detail[m3 & (sig == "STRONG_BUY")] = "強買：CCI突破-100 + 放量 + 止跌K"

    m4 = df["BullDiv"] & df["Vol_High"]
    sig[m4 & (sig == "NEUTRAL")] = "DIV_BUY"
    detail[m4 & (sig == "DIV_BUY")] = "底背離：CCI底部抬高 + 放量確認"

    m5 = df["CCI_X_zero_UP"] & df["Vol_High"]
    sig[m5 & (sig == "NEUTRAL")] = "BUY"
    detail[m5 & (sig == "BUY")] = "買入：CCI突破0軸 + 放量"

    m6 = df["CCI_X_neg100_UP"] & ~df["Vol_High"]
    sig[m6 & (sig == "NEUTRAL")] = "WATCH"
    detail[m6 & (sig == "WATCH")] = "觀望：CCI突破-100 but 量縮"

    m7 = df["CCI_X_pos100_DN"] & (df["Vol_Shrink"] | (df["Vol_High"] & df["BlackCandle"]))
    sig[m7 & (sig == "NEUTRAL")] = "STRONG_SELL"
    detail[m7 & (sig == "STRONG_SELL")] = "強賣：CCI跌破+100 + 買盤竭盡"

    m8 = df["BearDiv"] & df["PriceUp_VolDN"]
    sig[m8 & (sig == "NEUTRAL")] = "DIV_SELL"
    detail[m8 & (sig == "DIV_SELL")] = "頂背離：CCI高點降低 + 量縮"

    m9 = (df["RSI"] > p["rsi_overbought"]) & df["PriceUp_VolDN"] & df["UpperShadow"]
    sig[m9 & (sig == "NEUTRAL")] = "SELL"
    detail[m9 & (sig == "SELL")] = "賣出：RSI超買 + 價漲量縮"

    df["Signal"]        = sig
    df["Signal_Detail"] = detail
    df["Vol_Ratio"]     = vol_ratio.round(2)
    return df

# ══════════════════════════════════════════════
# DATA FETCHING (上市/上櫃 自動相容版)
# ══════════════════════════════════════════════

@st.cache_data(ttl=300)
def fetch_data(symbol: str, period: str = "1y"):
    if symbol.endswith((".TW", ".TWO", ".tw", ".two")):
        sym_list = [symbol.upper()]
    else:
        sym_list = [f"{symbol}.TW", f"{symbol}.TWO"]
    for sym in sym_list:
        try:
            df = yf.Ticker(sym).history(period=period)
            if not df.empty and len(df) > 0:
                df.index = pd.to_datetime(df.index).tz_localize(None)
                df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
                return df, None
        except Exception:
            continue
    return None, f"{symbol}: 無資料 (上市/上櫃皆查無資料)"

@st.cache_data(ttl=60)
def fetch_quote(symbol: str) -> dict:
    if symbol.endswith((".TW", ".TWO", ".tw", ".two")):
        sym_list = [symbol.upper()]
    else:
        sym_list = [f"{symbol}.TW", f"{symbol}.TWO"]
    for sym in sym_list:
        try:
            fi = yf.Ticker(sym).fast_info
            last = getattr(fi, "last_price", None)
            if last is not None and not np.isnan(last):
                prev  = getattr(fi, "previous_close",  None) or 0
                chg   = last - prev
                chg_p = chg / prev * 100 if prev else 0
                return {"price": round(last, 2), "change": round(chg, 2), "change_pct": round(chg_p, 2)}
        except Exception:
            continue
    return {}

# ══════════════════════════════════════════════
# CHART (已修正 Hex 色碼問題)
# ══════════════════════════════════════════════

MARKER_SHAPE = {
    "BREAKOUT_BUY":  ("triangle-up",    "#ff9900", 14, "below"),
    "STRONG_BUY":    ("triangle-up",    "#00ff88", 12, "below"),
    "BUY":           ("triangle-up",    "#44ddff", 10, "below"),
    "DIV_BUY":       ("diamond",        "#00ff88", 10, "below"),
    "WATCH":         ("circle-open",    "#ffee44",  8, "below"),
    "STRONG_SELL":   ("triangle-down",  "#ff3355", 12, "above"),
    "SELL":          ("triangle-down",  "#ff8866", 10, "above"),
    "DIV_SELL":      ("diamond",        "#ff3355", 10, "above"),
    "FAKE_BREAKOUT": ("x",              "#cc44ff",  8, "above"),
}

def build_chart(df: pd.DataFrame, symbol: str, p: dict) -> go.Figure:
    df = df.tail(130).copy()
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.44, 0.20, 0.18, 0.18],
        vertical_spacing=0.025,
    )

    # K線
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price",
        increasing_fillcolor="#e8414e", increasing_line_color="#e8414e",
        decreasing_fillcolor="#22cc66", decreasing_line_color="#22cc66",
    ), row=1, col=1)

    # 指標線
    for col_name, color, width, dash in [
        ("EMA1", "#f0a500", 1.3, "solid"), ("EMA2", "#2196f3", 1.3, "solid"),
        ("BB_Upper", "#607d8b", 0.8, "dot"), ("BB_Lower", "#607d8b", 0.8, "dot"),
        ("BB_Mid", "#546e7a", 0.7, "dash"),
    ]:
        if col_name in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col_name], name=col_name,
                line=dict(color=color, width=width, dash=dash), showlegend=False), row=1, col=1)

    # 訊號 Markers
    for sig, (shape, color, size, pos) in MARKER_SHAPE.items():
        mask = df["Signal"] == sig
        if not mask.any(): continue
        y_vals = (df.loc[mask, "Low"] * 0.975 if pos == "below" else df.loc[mask, "High"] * 1.025)
        fig.add_trace(go.Scatter(x=df.index[mask], y=y_vals, mode="markers",
            marker=dict(symbol=shape, color=color, size=size, line=dict(width=1, color="#000")),
            name=SIGNAL_LABEL.get(sig, sig), hovertext=df.loc[mask, "Signal_Detail"].tolist(), hoverinfo="text"), row=1, col=1)

    # CCI (修正透明色碼)
    cci_colors = ["#e8414e" if v > 100 else "#22cc66" if v < -100 else "#455a64" for v in df["CCI"].fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=df["CCI"], marker_color=cci_colors, name="CCI", showlegend=False), row=2, col=1)
    # 修正重點：使用 rgba 代替 8 位數 Hex
    fig.add_hline(y=100,  line_dash="dot", line_color="rgba(232, 65, 78, 0.33)", line_width=1, row=2, col=1)
    fig.add_hline(y=-100, line_dash="dot", line_color="rgba(34, 204, 102, 0.33)", line_width=1, row=2, col=1)
    fig.add_hline(y=0,    line_dash="dot", line_color="#37474f", line_width=1, row=2, col=1)

    # RSI (修正透明色碼)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#e040fb", width=1.5), showlegend=False), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="rgba(232, 65, 78, 0.33)", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="rgba(34, 204, 102, 0.33)", line_width=1, row=3, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#37474f", line_width=1, row=3, col=1)

    # MACD
    hist_colors = ["#e8414e" if v >= 0 else "#22cc66" for v in df["MACD_Hist"].fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], marker_color=hist_colors, showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], line=dict(color="#2196f3", width=1.3), showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Sig"], line=dict(color="#f0a500", width=1.3), showlegend=False), row=4, col=1)

    fig.update_layout(template="plotly_dark", height=820, paper_bgcolor="#0a0e1a", plot_bgcolor="#0d1226", margin=dict(l=55, r=20, t=20, b=10))
    fig.update_xaxes(showgrid=False, rangeslider_visible=False)
    return fig

# ══════════════════════════════════════════════
# BACKTEST & OTHERS (邏輯與前版相同，僅做整合)
# ══════════════════════════════════════════════

def backtest(df: pd.DataFrame, holding_days: int, profit_pct: float, stop_pct: float) -> dict:
    buy_idx = df.index[df["Signal"].isin({"STRONG_BUY", "BUY", "DIV_BUY", "BREAKOUT_BUY"})]
    if len(buy_idx) == 0: return {"win_rate": 0, "total": 0, "avg_return": 0, "trades": pd.DataFrame()}
    prices, dates, rows = df["Close"].values, df.index, []
    for entry_date in buy_idx:
        pos = df.index.get_loc(entry_date)
        ep = prices[pos]
        outcome, xp, xd, held = "HOLD", ep, entry_date, 0
        for d in range(1, min(holding_days + 1, len(prices) - pos)):
            fp = prices[pos + d]
            ret = (fp - ep) / ep * 100
            if ret >= profit_pct: outcome, xp, xd, held = "WIN", fp, dates[pos+d], d; break
            elif ret <= -stop_pct: outcome, xp, xd, held = "LOSS", fp, dates[pos+d], d; break
        if outcome == "HOLD" and pos + holding_days < len(prices):
            xp, held = prices[pos+holding_days], holding_days
            xd = dates[pos+holding_days]
            outcome = "WIN" if xp > ep else "LOSS"
        rows.append({"進場日": entry_date.date(), "訊號": df.loc[entry_date, "Signal"], "進場價": round(ep, 2), "出場價": round(xp, 2), "出場日": xd.date(), "持有天": held, "報酬%": round((xp-ep)/ep*100, 2), "結果": outcome})
    tdf = pd.DataFrame(rows)
    comp = tdf[tdf["結果"] != "HOLD"]
    wins = len(comp[comp["結果"] == "WIN"])
    tot = len(comp)
    return {"win_rate": round(wins/tot*100, 1) if tot > 0 else 0, "total": tot, "wins": wins, "losses": tot-wins, "avg_return": round(comp["報酬%"].mean(), 2) if tot > 0 else 0, "max_return": round(comp["報酬%"].max(), 2) if tot > 0 else 0, "min_return": round(comp["報酬%"].min(), 2) if tot > 0 else 0, "trades": tdf}

def to_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w: df.to_excel(w, index=False)
    buf.seek(0)
    return buf.read()

# ══════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════

DEFAULT_WATCHLIST = ["2330", "2317", "2454", "2382", "3711", "8069", "3293", "3105", "5347", "1565"]

def main():
    st.markdown("""<div class="sentinel-header"><div class="sentinel-title">🛡️ Sentinel Pro v2.1</div><div class="sentinel-sub">已修正繪圖引擎色碼相容性問題</div></div>""", unsafe_allow_html=True)
    if "watchlist" not in st.session_state: st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
    if "scan_rows" not in st.session_state: st.session_state.scan_rows = []

    with st.sidebar:
        st.markdown("### ⚙️ 策略參數")
        cci_period = st.slider("CCI 週期", 10, 60, 39)
        vol_multiplier = st.slider("放量門檻", 1.0, 4.0, 1.5, 0.1)
        st.divider()
        wl_text = st.text_area("股票清單 (上市/上櫃)", value="\n".join(st.session_state.watchlist), height=250)
        if st.button("✅ 更新清單"):
            st.session_state.watchlist = [s.strip() for s in wl_text.strip().splitlines() if s.strip()]
            st.session_state.scan_rows = []
            st.rerun()

    params = dict(cci_period=cci_period, vol_ma_period=20, vol_multiplier=vol_multiplier, vol_strong_multiplier=2.5, rsi_period=6, rsi_overbought=70, macd_fast=12, macd_slow=26, macd_signal=9, ema1=10, ema2=20, bb_period=20, use_divergence=True, div_lookback=25, holding_days=10, profit_target=3.0, stop_loss=5.0)

    tab_scan, tab_drill = st.tabs(["📡 訊號掃描", "🔬 個股分析"])

    with tab_scan:
        if st.button("🔄 開始掃描") or not st.session_state.scan_rows:
            rows, prog = [], st.progress(0)
            for i, code in enumerate(st.session_state.watchlist):
                prog.progress((i+1)/len(st.session_state.watchlist))
                df_raw, _ = fetch_data(code)
                if df_raw is None or len(df_raw) < 60: continue
                df_sig = generate_signals(df_raw, params)
                quote, bt = fetch_quote(code), backtest(df_sig, 10, 3.0, 5.0)
                latest = df_sig.iloc[-1]
                rows.append({"代號": code, "最新價": quote.get("price", latest["Close"]), "漲跌%": quote.get("change_pct", 0), "訊號": SIGNAL_LABEL.get(latest["Signal"], "─"), "說明": latest["Signal_Detail"], "勝率%": bt["win_rate"]})
            st.session_state.scan_rows = rows
        st.dataframe(pd.DataFrame(st.session_state.scan_rows), use_container_width=True, hide_index=True)

    with tab_drill:
        target = st.selectbox("選擇分析標的", st.session_state.watchlist)
        if st.button("分析個股"):
            df_raw, _ = fetch_data(target)
            if df_raw is not None:
                df_sig = generate_signals(df_raw, params)
                st.plotly_chart(build_chart(df_sig, target, params), use_container_width=True)

if __name__ == "__main__":
    main()
