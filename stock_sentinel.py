"""
Sentinel Pro — 台股多股掃描器 v2.0
CCI × 成交量 × 價格行為 量價策略訊號系統
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
import logging

# ── Silence noisy library output in Streamlit Cloud logs ──
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.base").setLevel(logging.CRITICAL)
logging.getLogger("yfinance.utils").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# Suppress the "$XXX: possibly delisted" stderr print that yfinance emits
# by monkey-patching the print function in yfinance's namespace at import time
import builtins as _builtins
_orig_print = _builtins.print

def _quiet_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    if "possibly delisted" in msg or "No data found" in msg or "period=" in msg:
        return
    _orig_print(*args, **kwargs)

_builtins.print = _quiet_print

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Sentinel Pro 🛡️",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",   # mobile-friendly: sidebar hidden by default
)

# ──────────────────────────────────────────────
# CUSTOM CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Noto+Sans+TC:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
.stApp { background-color: #0a0e1a; }

/* ── Header ── */
.sentinel-header {
    background: linear-gradient(135deg, #0d1226 0%, #141d3a 50%, #0d1226 100%);
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 14px;
    position: relative;
    overflow: hidden;
}
.sentinel-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #00d4ff, #0077ff, #00d4ff, transparent);
}
.sentinel-title {
    font-family: 'Space Mono', monospace;
    font-size: 1.3rem;
    font-weight: 700;
    color: #e8f4fd;
    margin: 0;
    letter-spacing: 0.03em;
    display: flex;
    align-items: center;
    gap: 8px;
}
.sentinel-sub {
    color: #5a8fb0;
    font-size: 0.75rem;
    margin-top: 3px;
    font-family: 'Space Mono', monospace;
}

/* ── Signal text colours ── */
.sig-strong-buy  { color: #00ff88; font-weight: 700; }
.sig-buy         { color: #44ddff; font-weight: 600; }
.sig-breakout    { color: #ff9900; font-weight: 700; }
.sig-fake        { color: #cc44ff; font-weight: 600; }
.sig-strong-sell { color: #ff3355; font-weight: 700; }
.sig-sell        { color: #ff8866; font-weight: 600; }
.sig-watch       { color: #ffee44; font-weight: 500; }
.sig-neutral     { color: #445566; }

/* ── Signal legend ── */
.signal-legend {
    background: #0d1a2d;
    border: 1px solid #1a3050;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.75rem;
    line-height: 1.9;
}

/* ── Optimisation card ── */
.opt-card {
    background: linear-gradient(135deg, #0d2040, #0a1628);
    border: 1px solid #0066cc;
    border-radius: 10px;
    padding: 14px 18px;
    margin-top: 10px;
}
.opt-card h4 { color: #00aaff; font-family: 'Space Mono', monospace; margin: 0 0 8px 0; }

/* ── Tabs ── */
div[data-testid="stTabs"] button {
    font-family: 'Space Mono', monospace;
    font-size: 0.8rem;
    color: #5a8fb0;
    padding: 6px 10px;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00d4ff;
    border-bottom-color: #00d4ff;
}

/* ── Dataframe ── */
.stDataFrame { border-radius: 8px; overflow: hidden; }
.stDataFrame td, .stDataFrame th { font-size: 0.78rem !important; }

/* ── Metrics ── */
div[data-testid="metric-container"] {
    background: #0d1a2d;
    border-radius: 8px;
    padding: 8px 10px;
    border: 1px solid #1a3050;
}
div[data-testid="metric-container"] label { font-size: 0.72rem !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }

/* ── Buttons — larger touch targets on mobile ── */
.stButton > button {
    min-height: 42px;
    font-size: 0.88rem;
}
.stDownloadButton > button { min-height: 38px; }

/* ── Sidebar compact ── */
section[data-testid="stSidebar"] { min-width: 240px !important; }
section[data-testid="stSidebar"] .stSlider { padding-top: 4px !important; }
section[data-testid="stSidebar"] label { font-size: 0.8rem !important; }

/* ── Mobile overrides ── */
@media (max-width: 768px) {
    .sentinel-title { font-size: 1.1rem; }
    .sentinel-sub   { font-size: 0.68rem; }
    .stDataFrame td, .stDataFrame th { font-size: 0.72rem !important; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 0.95rem !important; }
    .stButton > button { min-height: 46px; font-size: 0.92rem; }
}
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


def calc_kd(high, low, close, k_period=9, d_period=3, smooth=3):
    """
    KD Stochastic.  回傳 (K, D)。
    RSV = (close - lowest_low) / (highest_high - lowest_low) * 100
    K   = RSV 的 smooth-period EMA
    D   = K 的 d_period EMA
    """
    lo  = low.rolling(k_period).min()
    hi  = high.rolling(k_period).max()
    rsv = (close - lo) / (hi - lo + 1e-8) * 100
    k   = rsv.ewm(com=smooth - 1, min_periods=smooth).mean()
    d   = k.ewm(com=d_period - 1, min_periods=d_period).mean()
    return k, d


def calc_obv(close, volume):
    """On-Balance Volume — 累積量能趨勢。"""
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def calc_momentum_score(df: pd.DataFrame, p: dict) -> pd.Series:
    """
    綜合動能分數 (0–100)，用於「強勢排行」。
    分數越高代表短期動能越強。
    組成：CCI 正負 + RSI 位置 + 量比 + MACD 方向 + KD 金叉
    """
    score = pd.Series(0.0, index=df.index)
    # CCI 貢獻 (0-30)
    cci_norm = df["CCI"].clip(-200, 200) / 200 * 30
    score += cci_norm
    # RSI 貢獻 (0-25)
    score += df["RSI"].clip(0, 100) / 100 * 25
    # 量比貢獻 (0-20): capped at 4×
    score += (df["Vol_Ratio"].clip(0, 4) / 4) * 20
    # MACD 方向貢獻 (0-15)
    score += (df["MACD_Hist"] > 0).astype(float) * 15
    # KD 金叉貢獻 (0-10)
    if "K" in df.columns and "D" in df.columns:
        kd_cross = (df["K"] > df["D"]).astype(float)
        score += kd_cross * 10
    return score.clip(0, 100).round(1)


# ── Price-Action helpers ──────────────────────

def has_long_lower_shadow(open_, close, low, ratio=0.5):
    """下影線 ≥ 實體 × ratio → 止跌訊號"""
    body         = (close - open_).abs().clip(lower=1e-8)
    lower_shadow = np.minimum(open_, close) - low
    return (lower_shadow >= body * ratio).astype(bool)


def is_bullish_engulf(open_, close):
    """今陽K且實體吞噬昨陰K"""
    prev_open  = open_.shift(1)
    prev_close = close.shift(1)
    prev_body  = (prev_close - prev_open).clip(upper=0).abs()   # 昨陰K實體
    curr_body  = (close - open_).clip(lower=0)                  # 今陽K實體
    bearish_prev = prev_close < prev_open
    bullish_curr = close > open_
    engulf = (open_ <= prev_close) & (close >= prev_open)
    return (bearish_prev & bullish_curr & engulf & (curr_body > prev_body * 0.8)).astype(bool)


def has_long_upper_shadow(open_, close, high, ratio=0.5):
    """長上影線 → 賣壓訊號"""
    body         = (close - open_).abs().clip(lower=1e-8)
    upper_shadow = high - np.maximum(open_, close)
    return (upper_shadow >= body * ratio).astype(bool)


def detect_bullish_divergence(price, cci, lookback=30):
    """
    底背離: 向前 lookback 根 K 線中，price 創新低但 CCI 底部抬高。
    回傳布林 Series。
    """
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
        # price 創新低 但 CCI 高於前低對應值
        if curr_low < prev_low * 0.995 and arr_c[i] > window_c[prev_low_pos] * 1.05:
            result.iloc[i] = True
    return result


def detect_bearish_divergence(price, cci, lookback=30):
    """頂背離: price 創新高但 CCI 高點降低"""
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
# SIGNAL GENERATION  (CCI × Volume × Price)
# ══════════════════════════════════════════════

SIGNAL_ORDER = {
    "BREAKOUT_BUY": 0, "STRONG_BUY": 1, "BUY": 2, "DIV_BUY": 2,
    "KD_GOLDEN_ZONE": 2,
    "BULL_ZONE": 3, "RISING": 4,
    "WATCH": 7, "NEUTRAL": 8,
    "FALLING": 5, "BEAR_ZONE": 5, "KD_HIGH": 6,
    "DIV_SELL": 4, "SELL": 5, "STRONG_SELL": 4, "FAKE_BREAKOUT": 6,
}

SIGNAL_LABEL = {
    "BREAKOUT_BUY":   "🟠 噴發買",
    "STRONG_BUY":     "🟢 強買",
    "BUY":            "🔵 買入",
    "DIV_BUY":        "🟢 底背離",
    "KD_GOLDEN_ZONE": "🟢 KD金叉",
    "BULL_ZONE":      "🟡 強勢區",
    "RISING":         "🔼 上升中",
    "WATCH":          "⚪ 觀望",
    "NEUTRAL":        "─",
    "FALLING":        "🔽 下跌中",
    "BEAR_ZONE":      "🔵 超賣區",
    "KD_HIGH":        "🟡 KD高檔",
    "DIV_SELL":       "🔴 頂背離",
    "SELL":           "🟡 賣出",
    "STRONG_SELL":    "🔴 強賣",
    "FAKE_BREAKOUT":  "🟣 誘多",
}

# ── Map signal → concise zone for mobile display ──
SIGNAL_ZONE = {
    "BREAKOUT_BUY": "買", "STRONG_BUY": "買", "BUY": "買",
    "DIV_BUY": "買", "KD_GOLDEN_ZONE": "買",
    "BULL_ZONE": "持", "RISING": "漲",
    "WATCH": "觀", "NEUTRAL": "–",
    "FALLING": "跌", "BEAR_ZONE": "超賣",
    "KD_HIGH": "高", "DIV_SELL": "賣",
    "SELL": "賣", "STRONG_SELL": "賣", "FAKE_BREAKOUT": "誘",
}


def get_scan_signal(df_sig: pd.DataFrame, lookback: int = 5) -> tuple[str, str]:
    """
    Returns (signal_key, detail) for the scan table.
    Priority:
      1. Any non-neutral crossover event in the last `lookback` bars
      2. Current zone state (always produces a meaningful label)
    """
    # ── 1. Recent event signal ──
    for j in range(min(lookback, len(df_sig))):
        s = df_sig.iloc[-(j + 1)]["Signal"]
        if s not in ("NEUTRAL", "WATCH"):
            return s, df_sig.iloc[-(j + 1)]["Signal_Detail"]
        if s == "WATCH":   # return watch but keep scanning for stronger
            pass

    # ── 2. Zone state fallback ──
    latest = df_sig.iloc[-1]
    cci = float(latest.get("CCI", 0) or 0)
    k   = float(latest.get("K",  50) or 50)
    d   = float(latest.get("D",  50) or 50)
    rsi = float(latest.get("RSI", 50) or 50)
    obv_up = bool(latest.get("OBV_Rising", False))
    vol_r  = float(latest.get("Vol_Ratio", 1) or 1)

    # Strong bull zone
    if cci > 100:
        support = "OBV支撐" if obv_up else "OBV未支撐"
        return "BULL_ZONE", f"強勢區：CCI {cci:.0f}>+100，{support}"

    # Oversold zone
    if cci < -100:
        kd_txt = f"K={k:.0f}" + ("低檔" if k < 30 else "")
        return "BEAR_ZONE", f"超賣區：CCI {cci:.0f}<-100，{kd_txt}（關注底部）"

    # KD golden cross recently (look back 3 bars on KD_Golden column)
    if "KD_Golden" in df_sig.columns:
        for j in range(min(3, len(df_sig))):
            if bool(df_sig.iloc[-(j + 1)].get("KD_Golden", False)):
                return "KD_GOLDEN_ZONE", f"KD低檔金叉：K={k:.0f}，近{j+1}日發生"

    # KD high zone
    if k > 75 and k < d:
        return "KD_HIGH", f"KD高檔轉弱：K={k:.0f}，K下穿D"

    # Rising trend: CCI above 0, K above D
    if cci > 0 and k > d and rsi > 50:
        return "RISING", f"上升中：CCI {cci:.0f}，K>{d:.0f}，RSI={rsi:.0f}"

    # Falling trend
    if cci < 0 and k < d and rsi < 50:
        return "FALLING", f"下跌中：CCI {cci:.0f}，K<{d:.0f}，RSI={rsi:.0f}"

    # Watch: weak bounce (CCI crossed -100 but low volume earlier)
    for j in range(min(lookback, len(df_sig))):
        if df_sig.iloc[-(j + 1)]["Signal"] == "WATCH":
            return "WATCH", df_sig.iloc[-(j + 1)]["Signal_Detail"]

    return "NEUTRAL", "整理中"


def generate_signals(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """
    Returns df copy with Signal, Signal_Detail, CCI, RSI, KD, OBV,
    MACD*, Vol_MA, ATR, MomScore columns.
    """
    df = df.copy()

    # ── Compute indicators ──
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

    # ── KD Stochastic ──
    k, d = calc_kd(df["High"], df["Low"], df["Close"],
                   p.get("kd_period", 9), p.get("kd_d", 3), p.get("kd_smooth", 3))
    df["K"], df["D"] = k, d

    # ── OBV ──
    df["OBV"]        = calc_obv(df["Close"], df["Volume"])
    df["OBV_MA"]     = df["OBV"].rolling(p.get("obv_ma", 20)).mean()
    df["OBV_Rising"] = df["OBV"] > df["OBV_MA"]   # OBV 趨勢向上 → 量能支撐

    # ── Volume conditions ──
    vol_ratio            = df["Volume"] / (df["Vol_MA"] + 1e-8)
    df["Vol_Ratio"]      = vol_ratio.round(2)
    df["Vol_High"]       = vol_ratio >= p["vol_multiplier"]
    df["Vol_Strong"]     = vol_ratio >= p["vol_strong_multiplier"]
    df["Vol_Shrink"]     = vol_ratio < 0.8

    # ── CCI crossovers ──
    cci_prev = df["CCI"].shift(1)
    df["CCI_X_neg100_UP"]  = (cci_prev < -100) & (df["CCI"] >= -100)
    df["CCI_X_zero_UP"]    = (cci_prev <    0) & (df["CCI"] >=    0)
    df["CCI_X_pos100_UP"]  = (cci_prev <  100) & (df["CCI"] >=  100)
    df["CCI_X_pos100_DN"]  = (cci_prev >= 100) & (df["CCI"] <   100)

    # ── KD crossovers ──
    k_prev, d_prev = df["K"].shift(1), df["D"].shift(1)
    df["KD_Golden"]  = (k_prev <= d_prev) & (df["K"] > df["D"]) & (df["K"] < p.get("kd_oversold",  20))
    df["KD_Dead"]    = (k_prev >= d_prev) & (df["K"] < df["D"]) & (df["K"] > p.get("kd_overbought", 80))

    # ── Price action ──
    df["LowerShadow"]   = has_long_lower_shadow(df["Open"], df["Close"], df["Low"])
    df["BullEngulf"]    = is_bullish_engulf(df["Open"], df["Close"])
    df["UpperShadow"]   = has_long_upper_shadow(df["Open"], df["Close"], df["High"])
    df["PriceUp"]       = df["Close"] > df["Close"].shift(1)
    df["PriceUp_VolDN"] = df["PriceUp"] & (df["Volume"] < df["Volume"].shift(1))
    df["BlackCandle"]   = df["Close"] < df["Open"]

    # ── Divergence (only when flag on) ──
    if p.get("use_divergence", True):
        df["BullDiv"] = detect_bullish_divergence(df["Close"], df["CCI"], lookback=p.get("div_lookback", 25))
        df["BearDiv"] = detect_bearish_divergence(df["Close"], df["CCI"], lookback=p.get("div_lookback", 25))
    else:
        df["BullDiv"] = False
        df["BearDiv"] = False

    # ── Assign signals (priority: strongest first) ──
    sig    = pd.Series("NEUTRAL", index=df.index)
    detail = pd.Series("",        index=df.index)

    # 1. 強勢追漲：CCI突破+100 + 強放量 + OBV上升 → 噴發段
    m1 = df["CCI_X_pos100_UP"] & df["Vol_Strong"] & df["OBV_Rising"]
    sig[m1]    = "BREAKOUT_BUY"
    detail[m1] = "噴發段：CCI突破+100 + 強放量 + OBV量能支撐（倍量追強）"

    # 1b. 噴發但OBV不支撐 → 仍標 BREAKOUT 但附帶量能警示
    m1b = df["CCI_X_pos100_UP"] & df["Vol_Strong"] & ~df["OBV_Rising"]
    sig[m1b]    = "BREAKOUT_BUY"
    detail[m1b] = "噴發段：CCI突破+100 + 強放量（⚠️ OBV量能未支撐，注意假突破）"

    # 2. 假突破：CCI突破+100 but 縮量 → 誘多
    m2 = df["CCI_X_pos100_UP"] & ~df["Vol_High"]
    sig[m2]    = "FAKE_BREAKOUT"
    detail[m2] = "誘多警告：CCI突破+100 but 量不配合"

    # 3. 強買：CCI突破-100 + 放量 + 止跌K + OBV回升
    m3 = df["CCI_X_neg100_UP"] & df["Vol_High"] & (df["LowerShadow"] | df["BullEngulf"])
    sig[m3 & (sig == "NEUTRAL")] = "STRONG_BUY"
    detail[m3 & (sig == "STRONG_BUY")] = "強買：CCI突破-100 + 放量 + 止跌K（轉折確立）"

    # 3b. KD低檔金叉 + 放量 → 強買 (KD 補強)
    m3b = df["KD_Golden"] & df["Vol_High"] & (df["LowerShadow"] | df["BullEngulf"])
    sig[m3b & (sig == "NEUTRAL")] = "STRONG_BUY"
    detail[m3b & (sig == "STRONG_BUY")] = "強買：KD低檔金叉(<20) + 放量 + 止跌K（底部確認）"

    # 4. 底背離買入
    m4 = df["BullDiv"] & df["Vol_High"]
    sig[m4 & (sig == "NEUTRAL")] = "DIV_BUY"
    detail[m4 & (sig == "DIV_BUY")] = "底背離：股價創低但CCI底部抬高 + 放量確認"

    # 5. 一般買入：CCI突破0軸 + 放量 + OBV支撐
    m5 = df["CCI_X_zero_UP"] & df["Vol_High"]
    sig[m5 & (sig == "NEUTRAL")] = "BUY"
    detail[m5 & (sig == "BUY")] = "買入：CCI突破0軸 + 放量確認（動能轉正）"

    # 6. 觀望：CCI突破-100 但縮量（弱勢反彈）
    m6 = df["CCI_X_neg100_UP"] & ~df["Vol_High"]
    sig[m6 & (sig == "NEUTRAL")] = "WATCH"
    detail[m6 & (sig == "WATCH")] = "觀望：CCI突破-100 but 量縮（弱反彈，容易再跌）"

    # 7. 強賣：CCI跌破+100 + 量縮/爆量黑K 或 KD高檔死叉
    m7a = df["CCI_X_pos100_DN"] & (df["Vol_Shrink"] | (df["Vol_High"] & df["BlackCandle"]))
    m7b = df["KD_Dead"] & df["PriceUp_VolDN"]
    m7  = m7a | m7b
    sig[m7 & (sig == "NEUTRAL")] = "STRONG_SELL"
    detail[m7a & (sig == "STRONG_SELL")] = "強賣：CCI跌破+100 + 買盤竭盡（高檔撤退訊號）"
    detail[m7b & (sig == "STRONG_SELL")] = "強賣：KD高檔死叉(>80) + 價漲量縮（頭部訊號）"

    # 8. 頂背離賣出
    m8 = df["BearDiv"] & df["PriceUp_VolDN"]
    sig[m8 & (sig == "NEUTRAL")] = "DIV_SELL"
    detail[m8 & (sig == "DIV_SELL")] = "頂背離：股價創高但CCI高點降低 + 量縮（動能耗盡）"

    # 9. 一般賣出：RSI超買 + 價漲量縮 + 上影線
    m9 = (df["RSI"] > p["rsi_overbought"]) & df["PriceUp_VolDN"] & df["UpperShadow"]
    sig[m9 & (sig == "NEUTRAL")] = "SELL"
    detail[m9 & (sig == "SELL")] = "賣出：RSI超買 + 價漲量縮 + 上影線（追價意願薄弱）"

    df["Signal"]        = sig
    df["Signal_Detail"] = detail

    # ── Momentum score (computed after all signals) ──
    df["MomScore"] = calc_momentum_score(df, p)

    return df


# ══════════════════════════════════════════════
# BACKTESTING
# ══════════════════════════════════════════════

BUY_SIGNALS  = {"STRONG_BUY", "BUY", "DIV_BUY", "BREAKOUT_BUY"}
SELL_SIGNALS = {"STRONG_SELL", "SELL", "DIV_SELL"}


def backtest(df: pd.DataFrame, holding_days: int, profit_pct: float, stop_pct: float) -> dict:
    buy_idx = df.index[df["Signal"].isin(BUY_SIGNALS)]
    if len(buy_idx) == 0:
        return {"win_rate": 0, "total": 0, "wins": 0, "losses": 0,
                "avg_return": 0, "max_return": 0, "min_return": 0, "trades": pd.DataFrame()}

    prices = df["Close"].values
    dates  = df.index
    rows   = []

    for entry_date in buy_idx:
        pos = df.index.get_loc(entry_date)
        ep  = prices[pos]
        outcome = "HOLD"
        xp, xd, held = ep, entry_date, 0

        for d in range(1, min(holding_days + 1, len(prices) - pos)):
            fp  = prices[pos + d]
            ret = (fp - ep) / ep * 100
            if ret >= profit_pct:
                outcome, xp, xd, held = "WIN",  fp, dates[pos + d], d; break
            elif ret <= -stop_pct:
                outcome, xp, xd, held = "LOSS", fp, dates[pos + d], d; break

        if outcome == "HOLD" and pos + holding_days < len(prices):
            xp   = prices[pos + holding_days]
            held = holding_days
            xd   = dates[pos + holding_days] if pos + holding_days < len(dates) else entry_date
            outcome = "WIN" if xp > ep else "LOSS"

        ret_pct = (xp - ep) / ep * 100
        rows.append({
            "進場日":   entry_date.date(),
            "訊號":     df.loc[entry_date, "Signal"],
            "進場價":   round(ep, 2),
            "出場價":   round(xp, 2),
            "出場日":   xd.date() if hasattr(xd, "date") else xd,
            "持有天":   held,
            "報酬%":    round(ret_pct, 2),
            "結果":     outcome,
        })

    if not rows:
        return {"win_rate": 0, "total": 0, "wins": 0, "losses": 0,
                "avg_return": 0, "max_return": 0, "min_return": 0, "trades": pd.DataFrame()}

    tdf  = pd.DataFrame(rows)
    comp = tdf[tdf["結果"] != "HOLD"]
    wins = len(comp[comp["結果"] == "WIN"])
    tot  = len(comp)

    return {
        "win_rate":   round(wins / tot * 100, 1) if tot > 0 else 0,
        "total":      tot,
        "wins":       wins,
        "losses":     tot - wins,
        "avg_return": round(comp["報酬%"].mean(), 2) if tot > 0 else 0,
        "max_return": round(comp["報酬%"].max(),  2) if tot > 0 else 0,
        "min_return": round(comp["報酬%"].min(),  2) if tot > 0 else 0,
        "trades":     tdf,
    }


def optimize_params(df: pd.DataFrame, base_p: dict) -> pd.DataFrame:
    """Grid search: CCI period × vol_multiplier → win rate ranking."""
    cci_choices = [14, 20, 26, 39, 52]
    vol_choices = [1.2, 1.5, 2.0, 2.5, 3.0]
    rows = []

    for cp, vm in itertools.product(cci_choices, vol_choices):
        p2 = {**base_p, "cci_period": cp, "vol_multiplier": vm,
              "use_divergence": False}  # skip slow divergence in grid
        try:
            df2 = generate_signals(df, p2)
            bt  = backtest(df2, base_p["holding_days"],
                           base_p["profit_target"], base_p["stop_loss"])
            if bt["total"] >= 3:
                rows.append({
                    "CCI週期": cp, "放量門檻": vm,
                    "勝率%":   bt["win_rate"],
                    "總交易":  bt["total"],
                    "平均報酬%": bt["avg_return"],
                    "最大獲利%": bt["max_return"],
                    "最大虧損%": bt["min_return"],
                })
        except Exception:
            pass

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("勝率%", ascending=False).reset_index(drop=True)


# ══════════════════════════════════════════════
# DATA FETCHING
# ══════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_name(code: str) -> tuple[str, str]:
    """
    Return (display_name, market_label). Fast-path only — no slow .info call.
    Uses fast_info.display_name (yfinance 1.2+). Falls back to empty string
    rather than making a slow HTTP request during scan.
    market_label: '上市' | '上櫃' | ''
    """
    if code.upper().endswith(".TWO"):
        candidates = [(code, "上櫃")]
    elif code.upper().endswith(".TW"):
        candidates = [(code, "上市")]
    else:
        candidates = [(code + ".TW", "上市"), (code + ".TWO", "上櫃")]

    _STRIP = [" Co., Ltd.", " Co.,Ltd.", " Corporation", " Inc.", " Ltd.",
              "股份有限公司", "有限公司", " Co."]

    for sym, label in candidates:
        try:
            t    = yf.Ticker(sym)
            name = getattr(t.fast_info, "display_name", None) or ""
            if not name:
                # One additional attempt via .info but with a hard guard
                info = t.info
                if info and isinstance(info, dict) and len(info) > 5:
                    name = (info.get("shortName") or info.get("longName") or "")
            for s in _STRIP:
                name = name.replace(s, "")
            name = name.strip()
            if name:
                return name, label
        except Exception:
            pass
    return "", ""


@st.cache_data(ttl=300)
def fetch_data(symbol: str, period: str = "1y"):
    """Fetch OHLCV. Auto-tries .TW then .TWO for bare codes."""
    if symbol.upper().endswith((".TW", ".TWO")):
        candidates = [symbol]
    else:
        candidates = [symbol + ".TW", symbol + ".TWO"]

    last_err = "無資料"
    for sym in candidates:
        try:
            df = yf.Ticker(sym).history(period=period)  # stderr noise suppressed by monkey-patch
            if df.empty:
                last_err = f"{sym}: 無資料"
                continue
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if len(df) < 10:
                last_err = f"{sym}: 資料不足"
                continue
            return df, None
        except Exception as e:
            last_err = str(e)
    return None, last_err


@st.cache_data(ttl=60)
def fetch_quote(symbol: str) -> dict:
    """Fetch latest quote. Auto-tries .TW then .TWO."""
    if symbol.upper().endswith((".TW", ".TWO")):
        candidates = [symbol]
    else:
        candidates = [symbol + ".TW", symbol + ".TWO"]

    for sym in candidates:
        try:
            fi = yf.Ticker(sym).fast_info
            last = getattr(fi, "last_price",     None) or 0
            prev = getattr(fi, "previous_close", None) or 0
            if last == 0:
                continue
            chg   = last - prev
            chg_p = chg / prev * 100 if prev else 0
            return {"price": round(last, 2), "change": round(chg, 2),
                    "change_pct": round(chg_p, 2)}
        except Exception:
            pass
    return {}


# ══════════════════════════════════════════════
# CHART  (4-panel drill-down)
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

    # 5-panel: Candle+BB+EMA | Volume+OBV | CCI | KD | MACD
    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True,
        row_heights=[0.38, 0.12, 0.17, 0.17, 0.16],
        vertical_spacing=0.02,
    )

    # ── Panel 1: K線 + EMA + BB ──
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price",
        increasing_fillcolor="#e8414e", increasing_line_color="#e8414e",
        decreasing_fillcolor="#22cc66", decreasing_line_color="#22cc66",
    ), row=1, col=1)

    for col_name, color, lw, dash in [
        ("EMA1",     "#f0a500", 1.3, "solid"),
        ("EMA2",     "#2196f3", 1.3, "solid"),
        ("BB_Upper", "#607d8b", 0.8, "dot"),
        ("BB_Lower", "#607d8b", 0.8, "dot"),
        ("BB_Mid",   "#546e7a", 0.7, "dash"),
    ]:
        if col_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col_name], name=col_name,
                line=dict(color=color, width=lw, dash=dash),
                showlegend=False,
            ), row=1, col=1)

    if "BB_Upper" in df.columns and "BB_Lower" in df.columns:
        fig.add_trace(go.Scatter(
            x=pd.concat([pd.Series(df.index), pd.Series(df.index[::-1])]),
            y=pd.concat([df["BB_Upper"], df["BB_Lower"][::-1]]),
            fill="toself", fillcolor="rgba(100,140,180,0.05)",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ), row=1, col=1)

    # Signal markers
    for sig, (shape, color, size, pos) in MARKER_SHAPE.items():
        mask = df["Signal"] == sig
        if not mask.any():
            continue
        y_vals = (df.loc[mask, "Low"] * 0.975 if pos == "below"
                  else df.loc[mask, "High"] * 1.025)
        fig.add_trace(go.Scatter(
            x=df.index[mask], y=y_vals,
            mode="markers",
            marker=dict(symbol=shape, color=color, size=size,
                        line=dict(width=1, color="#000")),
            name=SIGNAL_LABEL.get(sig, sig),
            hovertext=df.loc[mask, "Signal_Detail"].tolist(),
            hoverinfo="text",
        ), row=1, col=1)

    # ── Panel 2: Volume bars + OBV line ──
    vol_colors = ["#e8414e" if c >= o else "#22cc66"
                  for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], marker_color=vol_colors,
        name="Volume", showlegend=False, opacity=0.7,
    ), row=2, col=1)
    if "OBV" in df.columns:
        # Normalise OBV to volume scale for overlay readability
        obv_range = df["OBV"].max() - df["OBV"].min() + 1e-8
        vol_range  = df["Volume"].max() + 1e-8
        obv_scaled = (df["OBV"] - df["OBV"].min()) / obv_range * vol_range * 0.8
        fig.add_trace(go.Scatter(
            x=df.index, y=obv_scaled, name="OBV(scaled)",
            line=dict(color="#00d4ff", width=1.2, dash="dot"),
            showlegend=False,
        ), row=2, col=1)
        # Vol_MA line
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Vol_MA"], name="Vol MA",
            line=dict(color="#f0a500", width=1.0),
            showlegend=False,
        ), row=2, col=1)

    # ── Panel 3: CCI ──
    cci_colors = ["#e8414e" if v > 100 else "#22cc66" if v < -100 else "#455a64"
                  for v in df["CCI"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df.index, y=df["CCI"], marker_color=cci_colors, name="CCI", showlegend=False,
    ), row=3, col=1)
    for level, col in [(100, "rgba(232,65,78,0.35)"), (-100, "rgba(34,204,102,0.35)"), (0, "#37474f")]:
        fig.add_hline(y=level, line_dash="dot", line_color=col, line_width=1, row=3, col=1)

    # ── Panel 4: KD ──
    if "K" in df.columns and "D" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["K"], name="K",
            line=dict(color="#f0a500", width=1.5), showlegend=False,
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["D"], name="D",
            line=dict(color="#2196f3", width=1.5), showlegend=False,
        ), row=4, col=1)
        # KD golden/dead cross markers
        gc = df["KD_Golden"] if "KD_Golden" in df.columns else pd.Series(False, index=df.index)
        dc = df["KD_Dead"]   if "KD_Dead"   in df.columns else pd.Series(False, index=df.index)
        if gc.any():
            fig.add_trace(go.Scatter(
                x=df.index[gc], y=df.loc[gc, "K"],
                mode="markers", marker=dict(symbol="triangle-up", color="#00ff88", size=9),
                name="KD金叉", showlegend=False,
            ), row=4, col=1)
        if dc.any():
            fig.add_trace(go.Scatter(
                x=df.index[dc], y=df.loc[dc, "K"],
                mode="markers", marker=dict(symbol="triangle-down", color="#ff3355", size=9),
                name="KD死叉", showlegend=False,
            ), row=4, col=1)
        for level, col in [(80, "rgba(232,65,78,0.35)"), (20, "rgba(34,204,102,0.35)"), (50, "#37474f")]:
            fig.add_hline(y=level, line_dash="dot", line_color=col, line_width=1, row=4, col=1)

    # ── Panel 5: MACD ──
    hist_colors = ["#e8414e" if v >= 0 else "#22cc66" for v in df["MACD_Hist"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df.index, y=df["MACD_Hist"], marker_color=hist_colors, name="Hist", showlegend=False,
    ), row=5, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD"], name="MACD",
        line=dict(color="#2196f3", width=1.3), showlegend=False,
    ), row=5, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD_Sig"], name="Signal",
        line=dict(color="#f0a500", width=1.3), showlegend=False,
    ), row=5, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=820,
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0d1226",
        xaxis_rangeslider_visible=False,
        margin=dict(l=55, r=20, t=20, b=10),
        font=dict(family="Space Mono, monospace", size=11, color="#8a9bb5"),
    )
    for i in range(1, 6):
        fig.update_yaxes(gridcolor="#1a2a3a", zeroline=False,
                         tickfont=dict(size=10), row=i, col=1)
    fig.update_xaxes(showgrid=False, rangeslider_visible=False)

    # Panel labels (y positions tuned to 5-panel layout)
    annotations = [
        dict(x=0.01, y=1.00, xref="paper", yref="paper",
             text=f"<b>{symbol}</b> · K線 / EMA / BB",
             showarrow=False, font=dict(color="#8a9bb5", size=11)),
        dict(x=0.01, y=0.59, xref="paper", yref="paper",
             text="Volume / OBV",
             showarrow=False, font=dict(color="#8a9bb5", size=11)),
        dict(x=0.01, y=0.46, xref="paper", yref="paper",
             text=f"CCI({p['cci_period']})",
             showarrow=False, font=dict(color="#8a9bb5", size=11)),
        dict(x=0.01, y=0.30, xref="paper", yref="paper",
             text=f"KD({p.get('kd_period',9)})",
             showarrow=False, font=dict(color="#8a9bb5", size=11)),
        dict(x=0.01, y=0.14, xref="paper", yref="paper",
             text="MACD",
             showarrow=False, font=dict(color="#8a9bb5", size=11)),
    ]
    fig.update_layout(annotations=annotations)
    return fig


# ══════════════════════════════════════════════
# EXCEL  IMPORT / EXPORT
# ══════════════════════════════════════════════

def to_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Sentinel_Scan", index=False)
        ws = w.sheets["Sentinel_Scan"]
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(
                (len(str(c.value or "")) for c in col), default=8
            ) + 3
    buf.seek(0)
    return buf.read()


def watchlist_from_excel(file) -> list[str]:
    try:
        df = pd.read_excel(file, header=0)
        for col in df.columns:
            if any(k in str(col).lower() for k in
                   ["stock", "symbol", "code", "代號", "股票", "ticker"]):
                return [str(v).strip() for v in df[col].dropna()
                        if str(v).strip() not in ("", "nan")]
        # fall back to first column
        return [str(v).strip() for v in df.iloc[:, 0].dropna()
                if str(v).strip() not in ("", "nan")]
    except Exception as e:
        st.error(f"Excel 匯入失敗：{e}")
        return []


# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

DEFAULT_WATCHLIST = [
    # 上市 (TSE .TW) ─────────────────────────────
    "2330",   # 台積電
"2317",   # 鴻海
"2454",   # 聯發科
"2881",   # 富邦金
"2308",   # 台達電
"2882",   # 國泰金
"2303",   # 聯電
"2886",   # 兆豐金
"2412",   # 中華電
"2382",   # 廣達
"2891",   # 中信金
"3008",   # 大立光
"2603",   # 長榮
"1301",   # 台塑
"1303",   # 南亞
"2892",   # 第一金
"2002",   # 中鋼
"2357",   # 華碩
"5880",   # 合庫金
"2327",   # 國巨
"2885",   # 元大金
"2609",   # 陽明
"2615",   # 萬海
"4938",   # 和碩
"2379",   # 瑞昱
"3034",   # 聯詠
"3711",   # 日月光投控
"2301",   # 光寶科
"2912",   # 統一超
"1216",   # 統一
"2395",   # 研華
"2880",   # 華南金
"2884",   # 玉山金
"2883",   # 開發金
"2887",   # 台新金
"2890",   # 永豐金
"6415",   # 矽力*-KY
"5871",   # 中租-KY
"5876",   # 上海商銀
"2408",   # 南亞科
"2313",   # 華通
"2376",   # 技嘉
"3231",   # 緯創
"6669",   # 緯穎
"2345",   # 智邦
"3037",   # 欣興
"8046",   # 南電
"2409",   # 友達
"3481",   # 群創
"2353",   # 宏碁
"1101",   # 台泥
"1102",   # 亞泥
"1402",   # 遠東新
"2105",   # 正新
"2207",   # 和泰車
"2610",   # 華航
"2618",   # 長榮航
"9904",   # 寶成
"9910",   # 豐泰
"9921",   # 巨大
"9945",   # 潤泰新
"2542",   # 興富發
"2352",   # 佳世達
"2347",   # 聯強
"6239",   # 力成
"2474",   # 可成
"4958",   # 臻鼎-KY
"2356",   # 英業達
"2324",   # 仁寶
"2439",   # 美律
"2492",   # 華新科
"1605",   # 華新
"1717",   # 長興
"1722",   # 台肥
"2104",   # 國際中橡
"6505",   # 台塑化
"1326",   # 台化
"2633",   # 台灣高鐵
"2707",   # 晶華
"3045",   # 台灣大
"4904",   # 遠傳
"8016",   # 矽創
"3532",   # 台勝科
"3443",   # 創意
"3661",   # 世芯-KY
"2368",   # 金像電
"6213",   # 聯茂
"6271",   # 同欣電
"2449",   # 京元電子
"3702",   # 大聯大
"3036",   # 文曄
"2360",   # 致茂
"2049",   # 上銀
"1504",   # 東元
"1503",   # 士電
"1513",   # 中興電
"1519",   # 華城
"6806",   # 連展投控
"5269",   # 祥碩
"6409",   # 旭隼
    
    # 上櫃 (OTC .TWO) ────────────────────────────
    "3661.TWO",   # 世芯-KY
    "6415.TWO",   # 矽力-KY
    "5269.TWO",   # 祥碩
    "4966.TWO",   # 譜瑞-KY
    "6271.TWO",   # 同欣電
]


def main():
    # ── Header ──────────────────────────────────
    st.markdown("""
    <div class="sentinel-header">
      <div class="sentinel-title">🛡️ Sentinel Pro <span style="color:#00d4ff;font-size:0.9em">v2.1</span></div>
      <div class="sentinel-sub">台股掃描器 · CCI × KD × OBV × 成交量</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Session state ────────────────────────────
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
    if "scan_rows" not in st.session_state:
        st.session_state.scan_rows = []

    # ══════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════
    with st.sidebar:
        st.markdown("### ⚙️ 策略參數")

        with st.expander("📊 CCI + 成交量", expanded=True):
            cci_period          = st.slider("CCI 週期",            10, 60,  39, 1)
            vol_ma_period       = st.slider("成交量均線週期",        5,  30,  20, 1)
            vol_multiplier      = st.slider("放量門檻（倍）",   1.0, 4.0, 1.5, 0.1)
            vol_strong_mul      = st.slider("強放量門檻（倍）", 1.5, 6.0, 2.5, 0.1)

        with st.expander("📈 RSI"):
            rsi_period     = st.slider("RSI 週期",   3, 21, 6,  1)
            rsi_oversold   = st.slider("超賣線",     20, 40, 30, 1)
            rsi_overbought = st.slider("超買線",     60, 85, 70, 1)

        with st.expander("📉 MACD"):
            macd_fast   = st.slider("快線 EMA",  5, 20, 12, 1)
            macd_slow   = st.slider("慢線 EMA", 15, 40, 26, 1)
            macd_sig    = st.slider("訊號線",    3, 15,  9, 1)

        with st.expander("📊 KD 隨機指標"):
            kd_period    = st.slider("KD 週期 (RSV)",    5, 20,  9, 1)
            kd_smooth    = st.slider("K 平滑",            1,  5,  3, 1)
            kd_d         = st.slider("D 平滑",            1,  5,  3, 1)
            kd_oversold  = st.slider("超賣線 (金叉門檻)", 10, 40, 20, 5)
            kd_overbought= st.slider("超買線 (死叉門檻)", 60, 95, 80, 5)

        with st.expander("📈 OBV 量能趨勢"):
            obv_ma = st.slider("OBV 均線週期", 5, 40, 20, 1)
            st.caption("OBV > OBV均線 = 量能支撐；用於確認突破真偽")

        with st.expander("🎯 均線 / 布林"):
            ema1      = st.slider("EMA 1",    5,  30, 10, 1)
            ema2      = st.slider("EMA 2",   10,  60, 20, 1)
            bb_period = st.slider("布林週期", 10,  30, 20, 1)

        with st.expander("🔀 背離偵測"):
            use_divergence = st.checkbox("啟用背離偵測", value=True)
            div_lookback   = st.slider("背離回看 K 數", 15, 50, 25, 1)

        with st.expander("🔬 回測設定"):
            holding_days  = st.slider("最長持有天數",   3,  30, 10, 1)
            profit_target = st.slider("獲利目標 (%)", 1.0, 15.0, 3.0, 0.5)
            stop_loss     = st.slider("停損 (%)",     1.0, 10.0, 5.0, 0.5)

        data_period = st.selectbox("資料區間", ["3mo", "6mo", "1y", "2y"], index=2)

        st.divider()
        st.markdown("### 📋 自選股清單")

        # Excel import
        uploaded = st.file_uploader("📥 從 Excel 匯入", type=["xlsx", "xls"])
        if uploaded:
            codes = watchlist_from_excel(uploaded)
            if codes:
                st.session_state.watchlist = codes
                st.success(f"已匯入 {len(codes)} 支股票")

        wl_text = st.text_area(
            "股票代號（每行一個；上市不需加後綴，上櫃請加 .TWO）",
            value="\n".join(st.session_state.watchlist),
            height=220,
        )
        if st.button("✅ 更新清單", width='stretch'):
            st.session_state.watchlist = [
                s.strip() for s in wl_text.strip().splitlines() if s.strip()
            ]
            st.session_state.scan_rows = []
            st.rerun()

        st.caption(f"共 **{len(st.session_state.watchlist)}** 支股票")

        # Export watchlist template
        wl_export = pd.DataFrame({"股票代號": st.session_state.watchlist})
        st.download_button(
            "📤 匯出清單範本 Excel",
            data=to_excel(wl_export),
            file_name="watchlist.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width='stretch',
        )

    # ── Pack params ─────────────────────────────
    params = dict(
        cci_period=cci_period, vol_ma_period=vol_ma_period,
        vol_multiplier=vol_multiplier, vol_strong_multiplier=vol_strong_mul,
        rsi_period=rsi_period, rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
        macd_fast=macd_fast, macd_slow=macd_slow, macd_signal=macd_sig,
        kd_period=kd_period, kd_smooth=kd_smooth, kd_d=kd_d,
        kd_oversold=kd_oversold, kd_overbought=kd_overbought,
        obv_ma=obv_ma,
        ema1=ema1, ema2=ema2, bb_period=bb_period,
        use_divergence=use_divergence, div_lookback=div_lookback,
        holding_days=holding_days, profit_target=profit_target, stop_loss=stop_loss,
    )

    # ══════════════════════════════════════════
    # TABS
    # ══════════════════════════════════════════
    tab_scan, tab_drill, tab_bt = st.tabs([
        "📡  訊號掃描", "🔬  個股分析", "📊  回測 & 優化",
    ])

    # ─────────────────────────────────────────
    # TAB 1  訊號掃描
    # ─────────────────────────────────────────
    with tab_scan:
        c_hd, c_btn = st.columns([4, 1])
        c_hd.markdown("#### 📡 即時掃描 — 量價訊號")
        run_scan = c_btn.button("🔄 掃描", type="primary", width='stretch')

        # Sort mode selector
        sort_mode = st.radio(
            "排序方式",
            ["📶 訊號強度", "🔥 動能分數", "📈 量比"],
            horizontal=True, label_visibility="collapsed",
        )

        if run_scan or not st.session_state.scan_rows:
            rows      = []
            failed    = []
            wl        = st.session_state.watchlist
            total_n   = max(len(wl), 1)
            prog      = st.progress(0, text="初始化...")

            for i, code in enumerate(wl):
                prog.progress((i + 1) / total_n, text=f"分析 {code} ({i+1}/{total_n})…")
                df_raw, err = fetch_data(code, data_period)
                if df_raw is None or len(df_raw) < 60:
                    failed.append(f"{code}: {err or '資料不足'}")
                    continue

                try:
                    df_sig = generate_signals(df_raw, params)
                except Exception as e:
                    failed.append(f"{code}: 訊號計算失敗 ({e})")
                    continue

                bt    = backtest(df_sig, holding_days, profit_target, stop_loss)
                quote = fetch_quote(code)
                cn_name, mkt_label = fetch_name(code)

                latest = df_sig.iloc[-1]
                prev   = df_sig.iloc[-2]
                price  = quote.get("price") or round(latest["Close"], 2)
                chg_p  = quote.get("change_pct") or (
                    (latest["Close"] - prev["Close"]) / (prev["Close"] + 1e-8) * 100
                )

                # ── Signal: event in last 5 bars OR current zone ──
                recent_sig, recent_detail = get_scan_signal(df_sig, lookback=5)

                # ATR-based stop
                atr_stop = round(price - latest["ATR"] * 1.5, 2) if pd.notna(latest.get("ATR")) else "-"
                mom = round(latest.get("MomScore", 0), 1) if pd.notna(latest.get("MomScore", 0)) else 0.0
                k_val = round(latest.get("K", np.nan), 1) if pd.notna(latest.get("K", np.nan)) else "-"
                d_val = round(latest.get("D", np.nan), 1) if pd.notna(latest.get("D", np.nan)) else "-"
                vol_r = round(latest["Vol_Ratio"], 2) if pd.notna(latest["Vol_Ratio"]) else 0.0

                bare = code.upper().replace(".TW", "").replace(".TWO", "")
                rows.append({
                    "代號":       bare,
                    "訊號":       SIGNAL_LABEL.get(recent_sig, recent_sig),
                    "動能":       mom,
                    "最新價":     price,
                    "漲跌%":      round(chg_p, 2),
                    "名稱":       cn_name,
                    "市場":       mkt_label,
                    f"CCI({cci_period})": round(latest["CCI"], 1) if pd.notna(latest["CCI"]) else "-",
                    f"RSI({rsi_period})": round(latest["RSI"], 1) if pd.notna(latest["RSI"]) else "-",
                    "K值":        k_val,
                    "D值":        d_val,
                    "量/均量":    vol_r,
                    "說明":       recent_detail,
                    "止損參考":   atr_stop,
                    "勝率%":      bt["win_rate"],
                    "平均報酬%":  bt["avg_return"],
                    "_sig_key":   recent_sig,
                    "_mom":       mom,
                    "_vol_r":     vol_r,
                })

            prog.empty()
            st.session_state.scan_rows      = rows
            st.session_state.scan_failed    = failed
            st.session_state.scan_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        rows      = st.session_state.scan_rows
        failed    = st.session_state.get("scan_failed", [])
        scan_time = st.session_state.get("scan_timestamp", "")

        if rows:
            # ── Sort ──
            if sort_mode == "🔥 動能分數":
                rows_sorted = sorted(rows, key=lambda r: -r["_mom"])
            elif sort_mode == "📈 量比":
                rows_sorted = sorted(rows, key=lambda r: -r["_vol_r"])
            else:
                rows_sorted = sorted(rows, key=lambda r: SIGNAL_ORDER.get(r["_sig_key"], 9))

            df_display = pd.DataFrame(rows_sorted)
            show_cols  = [c for c in df_display.columns if not c.startswith("_")]
            df_display = df_display[show_cols]

            if scan_time:
                st.caption(f"🕐 最後更新：{scan_time}　共 {len(rows)} 支")

            st.dataframe(
                df_display,
                width='stretch',
                height=530,
                column_config={
                    "漲跌%":  st.column_config.NumberColumn(format="%.2f%%"),
                    "動能":   st.column_config.ProgressColumn(
                        min_value=0, max_value=100, format="%.0f"),
                    "勝率%":  st.column_config.ProgressColumn(
                        min_value=0, max_value=100, format="%.1f%%"),
                    "平均報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                },
                hide_index=True,
            )

            # Signal legend
            st.markdown("""
            <div class="signal-legend">
            <b>買入訊號：</b>
            🟠 <b>噴發買</b> CCI突破+100強放量　
            🟢 <b>強買</b> CCI突破-100放量止跌K　
            🔵 <b>買入</b> CCI突破0軸放量　
            🟢 <b>底背離/KD金叉</b> 底部確認<br>
            <b>持倉/觀察：</b>
            🟡 <b>強勢區</b> CCI&gt;100持續強勢　
            🔼 <b>上升中</b> CCI&gt;0且K&gt;D　
            ⚪ <b>觀望</b> CCI突破-100量縮弱反彈<br>
            <b>賣出訊號：</b>
            🔴 <b>強賣</b> CCI跌破+100或KD高檔死叉　
            🟡 <b>賣出</b> RSI超買量縮上影線　
            🔴 <b>頂背離</b> 量縮動能耗盡　
            🟣 <b>誘多</b> CCI突破+100量不配合<br>
            <b>弱勢：</b>
            🔽 <b>下跌中</b> CCI&lt;0且K&lt;D　
            🔵 <b>超賣區</b> CCI&lt;-100（關注底部）
            </div>
            """, unsafe_allow_html=True)

            # Export
            st.markdown("")
            dl_bytes = to_excel(df_display)
            st.download_button(
                "📤 匯出掃描結果 Excel",
                data=dl_bytes,
                file_name=f"sentinel_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            if failed:
                with st.expander(f"⚠️ {len(failed)} 支股票載入失敗", expanded=False):
                    for msg in failed:
                        st.caption(f"• {msg}")
        else:
            st.markdown("""
            <div style="text-align:center;padding:40px 20px;color:#37474f">
              <div style="font-size:2.5rem">📡</div>
              <div style="font-size:1rem;margin-top:8px;color:#5a8fb0">
                點擊右上角「🔄 掃描」按鈕開始分析自選股
              </div>
              <div style="font-size:0.78rem;margin-top:6px;color:#37474f">
                側欄可調整策略參數 · 支援 Excel 匯入自選股清單
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # TAB 2  個股分析
    # ─────────────────────────────────────────
    with tab_drill:
        st.markdown("#### 🔬 個股深度分析")
        c1, c2, c3 = st.columns([3, 2, 1])
        sel_from_wl = c1.selectbox(
            "從自選股選擇", st.session_state.watchlist,
            format_func=lambda x: x if x.upper().endswith((".TW", ".TWO"))
                                     else f"{x}.TW",
        )
        custom_code = c2.text_input("或直接輸入代號", placeholder="e.g. 0050 / 3661.TWO")
        load_btn    = c3.button("📊 載入", type="primary", width='stretch')

        target = custom_code.strip() or sel_from_wl

        if load_btn:
            with st.spinner(f"載入 {target} …"):
                df_raw, err = fetch_data(target, data_period)
            if df_raw is None:
                st.error(f"無法取得資料：{err}")
            else:
                df_sig  = generate_signals(df_raw, params)
                latest  = df_sig.iloc[-1]
                prev    = df_sig.iloc[-2]
                quote   = fetch_quote(target)
                cn_name, mkt_label = fetch_name(target)

                price   = quote.get("price")    or round(latest["Close"], 2)
                chg     = quote.get("change")   or float(latest["Close"] - prev["Close"])
                chg_pct = quote.get("change_pct") or float(chg / (prev["Close"] + 1e-8) * 100)

                # ── Name banner ──
                bare_t    = target.upper().replace(".TW", "").replace(".TWO", "")
                mkt_color = "#22cc66" if mkt_label == "上櫃" else "#00aaff"
                chg_color = "#e8414e" if chg >= 0 else "#22cc66"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">'
                    f'<span style="font-size:1.3rem;font-weight:700;color:#e8f4fd;font-family:Space Mono,monospace">{bare_t}</span>'
                    f'<span style="background:{mkt_color};color:#000;padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:700">{mkt_label}</span>'
                    f'<span style="color:#8a9bb5;font-size:0.9rem">{cn_name}</span>'
                    f'<span style="color:{chg_color};font-size:1.1rem;font-weight:700;margin-left:auto">'
                    f'{price:.2f}　<span style="font-size:0.85rem">{chg:+.2f} ({chg_pct:+.2f}%)</span></span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Scan signal for this stock ──
                scan_sig, scan_detail = get_scan_signal(df_sig, lookback=5)

                # ── Metrics — 2 rows of 4 (mobile-friendly) ──
                r1c1, r1c2, r1c3, r1c4 = st.columns(4)
                r2c1, r2c2, r2c3, r2c4 = st.columns(4)

                cci_val = latest.get("CCI", np.nan)
                rsi_val = latest.get("RSI", np.nan)
                k_now   = latest.get("K",   np.nan)
                d_now   = latest.get("D",   np.nan)
                atr_val = latest.get("ATR", np.nan)
                vol_r   = latest.get("Vol_Ratio", np.nan)
                mom_now = float(latest.get("MomScore", 0) or 0)
                atr_stop= round(price - atr_val * 1.5, 2) if pd.notna(atr_val) else None

                r1c1.metric("訊號",       SIGNAL_LABEL.get(scan_sig, "─"))
                r1c2.metric(f"CCI({cci_period})", f"{cci_val:.1f}" if pd.notna(cci_val) else "-")
                r1c3.metric(f"RSI({rsi_period})", f"{rsi_val:.1f}" if pd.notna(rsi_val) else "-")
                r1c4.metric("量/均量",    f"{vol_r:.2f}x"   if pd.notna(vol_r)  else "-")

                r2c1.metric("動能分數",   f"{mom_now:.0f}/100")
                r2c2.metric("K值",        f"{k_now:.1f}"    if pd.notna(k_now)  else "-")
                r2c3.metric("D值",        f"{d_now:.1f}"    if pd.notna(d_now)  else "-")
                r2c4.metric("ATR停損",    f"{atr_stop:.2f}" if atr_stop         else "-")

                # ── Momentum bar ──
                mom_color = "#00ff88" if mom_now >= 60 else "#f0a500" if mom_now >= 40 else "#ff3355"
                st.markdown(
                    f'<div style="margin:4px 0 10px 0;display:flex;align-items:center;gap:10px">'
                    f'<span style="color:#5a8fb0;font-size:0.75rem;white-space:nowrap">動能 {mom_now:.0f}/100</span>'
                    f'<div style="flex:1;background:#1a2a3a;border-radius:4px;height:5px">'
                    f'<div style="background:{mom_color};width:{min(mom_now,100):.0f}%;height:5px;border-radius:4px"></div>'
                    f'</div>'
                    f'<span style="color:#5a8fb0;font-size:0.72rem;white-space:nowrap">{scan_detail[:40] + "…" if len(scan_detail) > 40 else scan_detail}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Chart ──
                fig = build_chart(df_sig, target, params)
                st.plotly_chart(fig, width='stretch')

                # ── Recent signal log (only crossover events) ──
                sig_cols  = ["Close", "Volume", "CCI", "RSI", "K", "D",
                             "Vol_Ratio", "MomScore", "Signal", "Signal_Detail"]
                available = [c for c in sig_cols if c in df_sig.columns]
                sig_hist  = df_sig[
                    df_sig["Signal"].isin(
                        list(BUY_SIGNALS) + list(SELL_SIGNALS) + ["WATCH", "FAKE_BREAKOUT"]
                    )
                ][available].tail(20)
                if not sig_hist.empty:
                    st.markdown("##### 📋 近期訊號記錄（最新 20 筆）")
                    sig_hist = sig_hist.copy()
                    sig_hist["Signal"] = sig_hist["Signal"].map(
                        lambda x: SIGNAL_LABEL.get(x, x))
                    sig_hist.index = sig_hist.index.date
                    st.dataframe(sig_hist, width='stretch')

    # ─────────────────────────────────────────
    # TAB 3  回測 & 優化
    # ─────────────────────────────────────────
    with tab_bt:
        st.markdown("#### 📊 回測分析 & 參數優化建議")

        c1, c2, c3 = st.columns([3, 2, 1])
        bt_sym  = c1.selectbox("選擇回測標的", st.session_state.watchlist,
                                format_func=lambda x: x if x.upper().endswith((".TW", ".TWO"))
                                                         else f"{x}.TW",
                                key="bt_sym")
        bt_cust = c2.text_input("或直接輸入代號", placeholder="e.g. 0050 / 3661.TWO", key="bt_custom")
        run_bt  = c3.button("🔬 執行", type="primary", width='stretch')

        bt_target = bt_cust.strip() or bt_sym

        if run_bt:
            with st.spinner(f"載入 {bt_target} 資料（2 年）…"):
                df_raw, err = fetch_data(bt_target, "2y")

            if df_raw is None:
                st.error(f"無法取得資料：{err}")
            else:
                df_sig = generate_signals(df_raw, params)
                bt     = backtest(df_sig, holding_days, profit_target, stop_loss)

                # ── Current params result ──
                st.markdown("##### 📌 當前參數回測結果")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric("勝率",      f"{bt['win_rate']:.1f}%")
                c2.metric("總交易",    bt["total"])
                c3.metric("獲利",      bt["wins"])
                c4.metric("虧損",      bt["losses"])
                c5.metric("平均報酬",  f"{bt['avg_return']:+.2f}%")
                c6.metric("最大獲利",  f"{bt['max_return']:+.2f}%")

                # Signal distribution
                if not bt["trades"].empty:
                    sig_cnt = bt["trades"].groupby("訊號")["結果"].value_counts().unstack(fill_value=0)
                    st.markdown("##### 各訊號勝率分布")
                    st.dataframe(sig_cnt, width='stretch')

                    with st.expander("📋 完整交易明細"):
                        st.dataframe(bt["trades"], width='stretch', height=350)
                        dl = to_excel(bt["trades"])
                        st.download_button(
                            "📤 匯出交易明細 Excel", data=dl,
                            file_name=f"backtest_{bt_target}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )

                # ── Grid-search optimisation ──
                st.divider()
                st.markdown("##### 🔧 參數優化建議（CCI週期 × 放量門檻 網格搜尋）")
                st.caption("自動測試 5 × 5 = 25 種組合，找出歷史勝率最高的參數配置")

                with st.spinner("網格搜尋中… 約需 20–40 秒"):
                    opt_df = optimize_params(df_raw, params)

                if opt_df.empty:
                    st.warning("訊號次數不足（至少需要 3 筆交易），請延長資料區間或放寬參數。")
                else:
                    st.dataframe(
                        opt_df.head(10),
                        width='stretch',
                        column_config={
                            "勝率%": st.column_config.ProgressColumn(
                                min_value=0, max_value=100, format="%.1f%%"
                            ),
                        },
                        hide_index=True,
                    )

                    best = opt_df.iloc[0]
                    delta_wr = best["勝率%"] - bt["win_rate"]
                    color = "#00ff88" if delta_wr > 0 else "#aaaaaa"

                    st.markdown(f"""
                    <div class="opt-card">
                      <h4>💡 最佳參數建議</h4>
                      <p style="color:#e8f4fd; font-size:1.05rem; margin:0">
                        CCI 週期 = <b style="color:#00d4ff">{int(best['CCI週期'])}</b> ，
                        放量門檻 = <b style="color:#00d4ff">{best['放量門檻']:.1f}x</b>
                      </p>
                      <p style="color:#8a9bb5; margin:6px 0 0 0; font-size:0.9rem">
                        預測勝率 <b style="color:{color}">{best['勝率%']:.1f}%</b>
                        （共 {int(best['總交易'])} 次交易，平均報酬 {best['平均報酬%']:+.2f}%）
                        — 比當前設定
                        <b style="color:{color}">{delta_wr:+.1f}%</b>
                      </p>
                      <p style="color:#5a7a90; font-size:0.8rem; margin-top:8px">
                        ※ 請在側欄調整「CCI週期」與「放量門檻」後重新掃描以套用建議參數。
                      </p>
                    </div>
                    """, unsafe_allow_html=True)

                    dl_opt = to_excel(opt_df)
                    st.download_button(
                        "📤 匯出優化結果 Excel", data=dl_opt,
                        file_name=f"optimize_{bt_target}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )


if __name__ == "__main__":
    main()
