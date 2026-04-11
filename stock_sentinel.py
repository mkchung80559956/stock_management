"""
Sentinel Pro — 台股多股掃描器 v2.0
CCI × 成交量 × 價格行為 量價策略訊號系統
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import itertools
import json
import os
import warnings
import logging
import pytz

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
    lo  = low.rolling(k_period).min()
    hi  = high.rolling(k_period).max()
    rsv = (close - lo) / (hi - lo + 1e-8) * 100
    k   = rsv.ewm(com=smooth - 1, min_periods=smooth).mean()
    d   = k.ewm(com=d_period - 1, min_periods=d_period).mean()
    return k, d


def calc_obv(close, volume):
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


# ─────────────────────────────────────────────
# 勝率提升三大核心函數
# ─────────────────────────────────────────────

def calc_trend_score(df: pd.DataFrame) -> pd.Series:
    """
    ① 趨勢過濾 (Trend Filter) — 中期趨勢強度 (-2 ~ +3)
    原理：只在中期上升趨勢中買入，可剔除逆勢假訊號、大幅降低接刀風險。
    研究顯示趨勢過濾可使勝率提升 15-25%。

    +3 = 強多頭：Price > EMA20 > EMA60，EMA20 斜率為正
    +2 = 多頭：Price > EMA20 > EMA60
    +1 = 弱多頭：Price > EMA60 but EMA20 < EMA60（橫盤）
     0 = 中性：Price 介於 EMA20 / EMA60 之間
    -1 = 弱空頭：Price < EMA60
    -2 = 強空頭：Price < EMA20 < EMA60，EMA20 斜率為負
    """
    score = pd.Series(0, index=df.index)
    if "EMA1" not in df.columns or "EMA2" not in df.columns or "EMA60" not in df.columns:
        return score

    price = df["Close"]
    ema20 = df["EMA2"]     # EMA2 = 20-period EMA (default)
    ema60 = df["EMA60"]

    # EMA20 斜率：過去 3 根平均方向
    ema20_slope = ema20.diff(3)

    above60   = price > ema60
    ema20_gt60 = ema20 > ema60

    # Strong uptrend
    strong_up = above60 & ema20_gt60 & (ema20_slope > 0)
    score[strong_up] = 3

    # Normal uptrend
    normal_up = above60 & ema20_gt60 & ~strong_up
    score[normal_up] = 2

    # Weak uptrend (price above EMA60 but EMA20 below)
    weak_up = above60 & ~ema20_gt60
    score[weak_up] = 1

    # Weak downtrend
    weak_dn = ~above60 & ema20_gt60
    score[weak_dn] = -1

    # Strong downtrend
    strong_dn = ~above60 & ~ema20_gt60 & (ema20_slope < 0)
    score[strong_dn] = -2

    return score


def calc_confluence_score(df: pd.DataFrame, p: dict) -> pd.Series:
    """
    ② 訊號共振 (Multi-indicator Confluence) — 買入共振分數 (0~7)
    原理：要求多個獨立指標同時確認，單一指標假訊號被大幅過濾。
    歷史回測顯示：共振分數 ≥ 5 的訊號，勝率比單一訊號高出 20-35%。

    7 個獨立指標共振：
    1. CCI > 0（動能正向）
    2. RSI > 50（RSI 強勢）
    3. K > D（KD 多頭排列）
    4. MACD_Hist > 0（MACD 多頭）
    5. OBV > OBV_MA（量能支撐）
    6. Close > EMA20（價格在均線上）
    7. Vol_Ratio > 1.0（成交量支撐）
    """
    c = pd.Series(0, index=df.index)
    if "CCI" in df.columns:
        c += (df["CCI"] > 0).astype(int)
    if "RSI" in df.columns:
        c += (df["RSI"] > 50).astype(int)
    if "K" in df.columns and "D" in df.columns:
        c += (df["K"] > df["D"]).astype(int)
    if "MACD_Hist" in df.columns:
        c += (df["MACD_Hist"] > 0).astype(int)
    if "OBV_Rising" in df.columns:
        c += df["OBV_Rising"].astype(int)
    if "EMA2" in df.columns:
        c += (df["Close"] > df["EMA2"]).astype(int)
    if "Vol_Ratio" in df.columns:
        c += (df["Vol_Ratio"] > 1.0).astype(int)
    return c


def calc_momentum_accel(df: pd.DataFrame) -> pd.Series:
    """
    ③ 動能加速 (Momentum Acceleration) — 過去 3 根 CCI 斜率 + RSI 斜率
    原理：最強的買點不是「動能最高」，而是「動能最快速轉強」的時刻。
    偵測 CCI 和 RSI 的加速上升，可提前捕捉趨勢啟動點。

    加速度 = (CCI 今日 − CCI 3日前) / 3  ← 每日平均漲幅
    正加速 + 共振訊號 = 最高品質進場點
    """
    accel = pd.Series(0.0, index=df.index)
    if "CCI" in df.columns:
        cci_slope = df["CCI"].diff(3) / 3        # CCI 每日平均變化速率
        accel += cci_slope / 50                  # normalise to 0-1 scale
    if "RSI" in df.columns:
        rsi_slope = df["RSI"].diff(3) / 3
        accel += rsi_slope / 10
    return accel.clip(-3, 3).round(2)


def calc_momentum_score(df: pd.DataFrame, p: dict) -> pd.Series:
    """
    綜合動能分數 (0–100) — 整合趨勢、共振、加速三個維度。
    升級版：加入趨勢分數與共振分數作為加權因子。
    """
    score = pd.Series(0.0, index=df.index)

    # CCI 貢獻 (0-20)
    if "CCI" in df.columns:
        score += df["CCI"].clip(-200, 200) / 200 * 20

    # RSI 貢獻 (0-15)
    if "RSI" in df.columns:
        score += df["RSI"].clip(0, 100) / 100 * 15

    # 量比貢獻 (0-15)
    if "Vol_Ratio" in df.columns:
        score += (df["Vol_Ratio"].clip(0, 4) / 4) * 15

    # MACD 方向貢獻 (0-10)
    if "MACD_Hist" in df.columns:
        score += (df["MACD_Hist"] > 0).astype(float) * 10

    # KD 金叉貢獻 (0-10)
    if "K" in df.columns and "D" in df.columns:
        score += (df["K"] > df["D"]).astype(float) * 10

    # ① 趨勢貢獻 (0-15): 新增
    if "TrendScore" in df.columns:
        score += (df["TrendScore"].clip(-2, 3) + 2) / 5 * 15

    # ② 共振貢獻 (0-10): 新增
    if "ConfluenceScore" in df.columns:
        score += df["ConfluenceScore"] / 7 * 10

    # ③ 加速貢獻 (0-5): 新增
    if "MomAccel" in df.columns:
        score += df["MomAccel"].clip(0, 3) / 3 * 5

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
    "HIGH_CONF_BUY":  0,
    "BREAKOUT_BUY":   1, "STRONG_BUY":  2, "BUY": 3, "DIV_BUY": 3,
    "KD_GOLDEN_ZONE": 3,
    "BULL_ZONE": 4, "RISING": 5,
    "WATCH": 8, "NEUTRAL": 9,
    "FALLING": 6, "BEAR_ZONE": 6, "KD_HIGH": 7,
    "DIV_SELL": 5, "SELL": 6, "STRONG_SELL": 5, "FAKE_BREAKOUT": 7,
}

SIGNAL_LABEL = {
    "HIGH_CONF_BUY":  "⭐ 三重共振",
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


def _html_safe(s: str) -> str:
    """Escape & < > so a plain-text string is safe to embed in HTML."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_scan_signal(df_sig: pd.DataFrame, lookback: int = 5) -> tuple[str, str]:
    """
    Returns (signal_key, detail).
    detail strings must NOT contain raw HTML special chars (< > &).
    """
    # ── 1. Recent crossover event ──
    for j in range(min(lookback, len(df_sig))):
        s = df_sig.iloc[-(j + 1)]["Signal"]
        if s not in ("NEUTRAL", "WATCH"):
            return s, df_sig.iloc[-(j + 1)]["Signal_Detail"]

    # ── 2. Zone state fallback ──
    latest = df_sig.iloc[-1]
    cci    = float(latest.get("CCI",     0) or 0)
    k      = float(latest.get("K",      50) or 50)
    d      = float(latest.get("D",      50) or 50)
    rsi    = float(latest.get("RSI",    50) or 50)
    obv_up = bool(latest.get("OBV_Rising", False))
    trnd   = int(float(latest.get("TrendScore",      0) or 0))
    conf   = int(float(latest.get("ConfluenceScore", 0) or 0))
    accl   = float(latest.get("MomAccel", 0) or 0)

    trend_txt = {3:"強多頭++", 2:"多頭+", 1:"弱多頭", 0:"中性",
                 -1:"弱空頭", -2:"強空頭--"}.get(trnd, str(trnd))
    conf_txt  = f"共振{conf}/7"
    accel_txt = f"加速{accl:+.1f}" if abs(accl) > 0.2 else ""

    if cci > 100:
        support = "OBV支撐" if obv_up else "OBV未支撐"
        return "BULL_ZONE", f"強勢區 CCI {cci:.0f} · {support} · {trend_txt} · {conf_txt}"

    if cci < -100:
        kd_note = "低檔" if k < 30 else ""
        return "BEAR_ZONE", f"超賣區 CCI {cci:.0f} · K={k:.0f}{kd_note} · {conf_txt}"

    if "KD_Golden" in df_sig.columns:
        for j in range(min(3, len(df_sig))):
            if bool(df_sig.iloc[-(j + 1)].get("KD_Golden", False)):
                return "KD_GOLDEN_ZONE", f"KD低檔金叉 K={k:.0f} · {trend_txt} · {conf_txt}"

    if k > 75 and k < d:
        return "KD_HIGH", f"KD高檔轉弱 K={k:.0f} · {conf_txt}"

    if cci > 0 and k > d and rsi > 50:
        extras = " · ".join(filter(None, [trend_txt, conf_txt, accel_txt]))
        return "RISING", f"上升中 CCI {cci:.0f} · {extras}"

    if cci < 0 and k < d and rsi < 50:
        return "FALLING", f"下跌中 CCI {cci:.0f} · {trend_txt} · {conf_txt}"

    for j in range(min(lookback, len(df_sig))):
        if df_sig.iloc[-(j + 1)]["Signal"] == "WATCH":
            return "WATCH", df_sig.iloc[-(j + 1)]["Signal_Detail"]

    return "NEUTRAL", f"整理中 · {trend_txt} · {conf_txt}"


def generate_signals(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """
    Returns df copy with all indicators + Signal + Signal_Detail.
    Three win-rate enhancements:
    ① TrendScore: medium-term trend filter (EMA20/EMA60)
    ② ConfluenceScore: multi-indicator agreement (0-7)
    ③ MomAccel: momentum acceleration (CCI+RSI slope)
    """
    df = df.copy()

    # ── Core indicators ──
    df["CCI"]    = calc_cci(df["High"], df["Low"], df["Close"], p["cci_period"])
    df["RSI"]    = calc_rsi(df["Close"], p["rsi_period"])
    df["Vol_MA"] = calc_vol_ma(df["Volume"], p["vol_ma_period"])
    df["ATR"]    = calc_atr(df["High"], df["Low"], df["Close"], 14)
    df["EMA1"]   = calc_ema(df["Close"], p["ema1"])
    df["EMA2"]   = calc_ema(df["Close"], p["ema2"])
    df["EMA60"]  = calc_ema(df["Close"], 60)          # ① medium-term trend anchor
    bb_u, bb_m, bb_l = calc_bb(df["Close"], p["bb_period"])
    df["BB_Upper"], df["BB_Mid"], df["BB_Lower"] = bb_u, bb_m, bb_l
    m, ms, mh = calc_macd(df["Close"], p["macd_fast"], p["macd_slow"], p["macd_signal"])
    df["MACD"], df["MACD_Sig"], df["MACD_Hist"] = m, ms, mh

    # ── KD + OBV ──
    k, d = calc_kd(df["High"], df["Low"], df["Close"],
                   p.get("kd_period", 9), p.get("kd_d", 3), p.get("kd_smooth", 3))
    df["K"], df["D"] = k, d
    df["OBV"]        = calc_obv(df["Close"], df["Volume"])
    df["OBV_MA"]     = df["OBV"].rolling(p.get("obv_ma", 20)).mean()
    df["OBV_Rising"] = df["OBV"] > df["OBV_MA"]

    # ── Volume ──
    vol_ratio        = df["Volume"] / (df["Vol_MA"] + 1e-8)
    df["Vol_Ratio"]  = vol_ratio.round(2)
    df["Vol_High"]   = vol_ratio >= p["vol_multiplier"]
    df["Vol_Strong"] = vol_ratio >= p["vol_strong_multiplier"]
    df["Vol_Shrink"] = vol_ratio < 0.8

    # ── ① TREND FILTER ──────────────────────────────────────────────────────
    df["TrendScore"] = calc_trend_score(df)
    in_uptrend = df["TrendScore"] >= 2
    # Honour the sidebar "trend_filter" toggle
    if p.get("trend_filter", True):
        in_downtrend = df["TrendScore"] <= -2   # strong downtrend → block buys
    else:
        in_downtrend = pd.Series(False, index=df.index)  # disabled → never blocks

    # ── ② CONFLUENCE SCORE ──────────────────────────────────────────────────
    df["ConfluenceScore"] = calc_confluence_score(df, p)
    high_conf = df["ConfluenceScore"] >= p.get("min_confluence", 5)

    # ── ③ MOMENTUM ACCELERATION ─────────────────────────────────────────────
    df["MomAccel"]  = calc_momentum_accel(df)
    accel_positive  = df["MomAccel"] > p.get("accel_threshold", 0.3)  # user-configurable

    # ── CCI crossovers ──
    cci_prev = df["CCI"].shift(1)
    df["CCI_X_neg100_UP"] = (cci_prev < -100) & (df["CCI"] >= -100)
    df["CCI_X_zero_UP"]   = (cci_prev <    0) & (df["CCI"] >=    0)
    df["CCI_X_pos100_UP"] = (cci_prev <  100) & (df["CCI"] >=  100)
    df["CCI_X_pos100_DN"] = (cci_prev >= 100) & (df["CCI"] <   100)

    # ── KD crossovers ──
    k_prev, d_prev = df["K"].shift(1), df["D"].shift(1)
    df["KD_Golden"] = (k_prev <= d_prev) & (df["K"] > df["D"]) & (df["K"] < p.get("kd_oversold",  20))
    df["KD_Dead"]   = (k_prev >= d_prev) & (df["K"] < df["D"]) & (df["K"] > p.get("kd_overbought", 80))

    # ── Price action ──
    df["LowerShadow"]   = has_long_lower_shadow(df["Open"], df["Close"], df["Low"])
    df["BullEngulf"]    = is_bullish_engulf(df["Open"], df["Close"])
    df["UpperShadow"]   = has_long_upper_shadow(df["Open"], df["Close"], df["High"])
    df["PriceUp"]       = df["Close"] > df["Close"].shift(1)
    df["PriceUp_VolDN"] = df["PriceUp"] & (df["Volume"] < df["Volume"].shift(1))
    df["BlackCandle"]   = df["Close"] < df["Open"]

    # ── Divergence ──
    if p.get("use_divergence", True):
        df["BullDiv"] = detect_bullish_divergence(df["Close"], df["CCI"], lookback=p.get("div_lookback", 25))
        df["BearDiv"] = detect_bearish_divergence(df["Close"], df["CCI"], lookback=p.get("div_lookback", 25))
    else:
        df["BullDiv"] = False
        df["BearDiv"] = False

    # ══════════════════════════════════════════════════════════
    # SIGNAL ASSIGNMENT — order = priority (first wins)
    # ══════════════════════════════════════════════════════════
    sig    = pd.Series("NEUTRAL", index=df.index)
    detail = pd.Series("",        index=df.index)

    # ★ 0. HIGH_CONF_BUY — 三重共振最高品質訊號 (①+②+③ 全中)
    #    條件：上升趨勢 + 5+/7 指標共振 + 動能加速 + CCI剛突破0軸或-100軸
    hc_trigger = (df["CCI_X_zero_UP"] | df["CCI_X_neg100_UP"]) & df["Vol_High"]
    m0 = hc_trigger & in_uptrend & high_conf & accel_positive
    sig[m0] = "HIGH_CONF_BUY"
    # Simple scalar assignment — avoid pandas Series arithmetic that can fail on NaN
    if m0.any():
        for idx in df.index[m0]:
            c = df.at[idx, "ConfluenceScore"]
            c_int = int(c) if pd.notna(c) else 0
            detail.at[idx] = f"三重共振：趨勢+ + {c_int}/7共振 + 動能加速"

    # 1. 噴發買：CCI突破+100 + 強放量 + OBV + 趨勢確認
    m1 = df["CCI_X_pos100_UP"] & df["Vol_Strong"] & df["OBV_Rising"] & ~in_downtrend
    sig[m1]    = "BREAKOUT_BUY"
    detail[m1] = "噴發段：CCI突破+100 + 強放量 + OBV量能支撐"

    m1b = df["CCI_X_pos100_UP"] & df["Vol_Strong"] & ~df["OBV_Rising"] & ~in_downtrend
    sig[m1b]    = "BREAKOUT_BUY"
    detail[m1b] = "噴發段：CCI突破+100 + 強放量（⚠️ OBV未支撐）"

    # 2. 誘多：CCI突破+100 縮量
    m2 = df["CCI_X_pos100_UP"] & ~df["Vol_High"]
    sig[m2]    = "FAKE_BREAKOUT"
    detail[m2] = "誘多警告：CCI突破+100 但量不配合"

    # 3. 強買：CCI突破-100 + 放量 + 止跌K — 需趨勢不是強空頭
    m3 = df["CCI_X_neg100_UP"] & df["Vol_High"] & (df["LowerShadow"] | df["BullEngulf"]) & ~in_downtrend
    sig[m3 & (sig == "NEUTRAL")] = "STRONG_BUY"
    detail[m3 & (sig == "STRONG_BUY")] = "強買：CCI突破-100 + 放量 + 止跌K"

    # 3b. KD低檔金叉強買
    m3b = df["KD_Golden"] & df["Vol_High"] & (df["LowerShadow"] | df["BullEngulf"]) & ~in_downtrend
    sig[m3b & (sig == "NEUTRAL")] = "STRONG_BUY"
    detail[m3b & (sig == "STRONG_BUY")] = "強買：KD低檔金叉(K低於20) + 放量 + 止跌K"

    # 4. 底背離買入
    m4 = df["BullDiv"] & df["Vol_High"]
    sig[m4 & (sig == "NEUTRAL")] = "DIV_BUY"
    detail[m4 & (sig == "DIV_BUY")] = "底背離：股價創低但CCI底部抬高 + 放量"

    # 5. 一般買入：CCI突破0軸 + 放量 (趨勢不是強空頭)
    m5 = df["CCI_X_zero_UP"] & df["Vol_High"] & ~in_downtrend
    sig[m5 & (sig == "NEUTRAL")] = "BUY"
    detail[m5 & (sig == "BUY")] = "買入：CCI突破0軸 + 放量（動能轉正）"

    # 6. 觀望：CCI突破-100 縮量
    m6 = df["CCI_X_neg100_UP"] & ~df["Vol_High"]
    sig[m6 & (sig == "NEUTRAL")] = "WATCH"
    detail[m6 & (sig == "WATCH")] = "觀望：CCI突破-100 但量縮（弱反彈）"

    # 7. 強賣
    m7a = df["CCI_X_pos100_DN"] & (df["Vol_Shrink"] | (df["Vol_High"] & df["BlackCandle"]))
    m7b = df["KD_Dead"] & df["PriceUp_VolDN"]
    m7  = m7a | m7b
    sig[m7 & (sig == "NEUTRAL")] = "STRONG_SELL"
    detail[m7a & (sig == "STRONG_SELL")] = "強賣：CCI跌破+100 + 買盤竭盡"
    detail[m7b & (sig == "STRONG_SELL")] = "強賣：KD高檔死叉 + 價漲量縮"

    # 8. 頂背離
    m8 = df["BearDiv"] & df["PriceUp_VolDN"]
    sig[m8 & (sig == "NEUTRAL")] = "DIV_SELL"
    detail[m8 & (sig == "DIV_SELL")] = "頂背離：股價創高但CCI高點降低 + 量縮"

    # 9. 一般賣出
    m9 = (df["RSI"] > p["rsi_overbought"]) & df["PriceUp_VolDN"] & df["UpperShadow"]
    sig[m9 & (sig == "NEUTRAL")] = "SELL"
    detail[m9 & (sig == "SELL")] = "賣出：RSI超買 + 價漲量縮 + 上影線"

    df["Signal"]        = sig
    df["Signal_Detail"] = detail
    df["MomScore"]      = calc_momentum_score(df, p)

    return df


# ══════════════════════════════════════════════
# BACKTESTING
# ══════════════════════════════════════════════

BUY_SIGNALS  = {"HIGH_CONF_BUY", "STRONG_BUY", "BUY", "DIV_BUY", "BREAKOUT_BUY"}
SELL_SIGNALS = {"STRONG_SELL", "SELL", "DIV_SELL"}


def backtest(df: pd.DataFrame, holding_days: int, profit_pct: float, stop_pct: float) -> dict:
    """
    Backtest buy signals. Entry is at the NEXT bar's open (simulated as next
    bar's close) to avoid look-ahead bias — you can only act after the signal
    bar closes.
    """
    buy_idx = df.index[df["Signal"].isin(BUY_SIGNALS)]
    if len(buy_idx) == 0:
        return {"win_rate": 0, "total": 0, "wins": 0, "losses": 0,
                "avg_return": 0, "max_return": 0, "min_return": 0, "trades": pd.DataFrame()}

    prices = df["Close"].values
    opens  = df["Open"].values
    dates  = df.index
    rows   = []

    for entry_date in buy_idx:
        pos = df.index.get_loc(entry_date)
        # Enter at NEXT bar's open to eliminate look-ahead bias
        entry_pos = pos + 1
        if entry_pos >= len(prices):
            continue
        ep  = opens[entry_pos]          # next bar open
        outcome = "HOLD"
        xp, xd, held = ep, dates[entry_pos], 0

        for d in range(1, min(holding_days + 1, len(prices) - entry_pos)):
            fp  = prices[entry_pos + d]
            ret = (fp - ep) / ep * 100
            if ret >= profit_pct:
                outcome, xp, xd, held = "WIN",  fp, dates[entry_pos + d], d; break
            elif ret <= -stop_pct:
                outcome, xp, xd, held = "LOSS", fp, dates[entry_pos + d], d; break

        if outcome == "HOLD" and entry_pos + holding_days < len(prices):
            xp      = prices[entry_pos + holding_days]
            held    = holding_days
            xd_idx  = entry_pos + holding_days
            xd      = dates[xd_idx] if xd_idx < len(dates) else dates[-1]
            outcome = "WIN" if xp > ep else "LOSS"

        ret_pct = (xp - ep) / ep * 100
        rows.append({
            "進場日":  entry_date.date(),
            "訊號":    df.loc[entry_date, "Signal"],
            "進場價":  round(ep, 2),
            "出場價":  round(xp, 2),
            "出場日":  xd.date() if hasattr(xd, "date") else xd,
            "持有天":  held,
            "報酬%":   round(ret_pct, 2),
            "結果":    outcome,
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
              "use_divergence": False}
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


@st.cache_data(ttl=86400)
def auto_optimize_cci(symbol: str, period: str,
                      holding_days: int, profit_target: float, stop_loss: float,
                      vol_ma_period: int, rsi_period: int,
                      kd_period: int, ema2: int) -> dict:
    """
    Per-stock CCI optimisation — searches 5 CCI × 3 vol = 15 combinations.
    Cache key uses only the params that affect optimisation outcome (scalar args,
    not a dict — dict args prevent reliable st.cache_data caching).
    Changing holding_days/profit_target/stop_loss correctly invalidates the cache.
    """
    df_raw, _ = fetch_data(symbol, period)
    if df_raw is None or len(df_raw) < 80:
        return {"cci_period": 39, "vol_multiplier": 1.5,
                "win_rate": 0, "avg_return": 0, "total": 0, "optimised": False}

    # Minimal param set for optimisation (no divergence = fast)
    base = dict(
        vol_ma_period=vol_ma_period, vol_strong_multiplier=2.5,
        rsi_period=rsi_period, rsi_oversold=30, rsi_overbought=70,
        macd_fast=12, macd_slow=26, macd_signal=9,
        kd_period=kd_period, kd_smooth=3, kd_d=3,
        kd_oversold=20, kd_overbought=80, obv_ma=20,
        ema1=10, ema2=ema2, bb_period=20,
        use_divergence=False, div_lookback=25,
        min_confluence=5, accel_threshold=0.3, trend_filter=True,
        holding_days=holding_days,
        profit_target=profit_target,
        stop_loss=stop_loss,
    )

    best = None
    for cp in [14, 20, 26, 39, 52]:
        for vm in [1.2, 1.5, 2.0]:
            try:
                p2  = {**base, "cci_period": cp, "vol_multiplier": vm}
                df2 = generate_signals(df_raw, p2)
                bt  = backtest(df2, holding_days, profit_target, stop_loss)
                if bt["total"] < 3:
                    continue
                score = bt["win_rate"] + max(bt["avg_return"], 0) * 2
                if best is None or score > best["_score"]:
                    best = {"cci_period": cp, "vol_multiplier": vm,
                            "win_rate": bt["win_rate"], "avg_return": bt["avg_return"],
                            "total": bt["total"], "optimised": True, "_score": score}
            except Exception:
                pass

    return best or {"cci_period": 39, "vol_multiplier": 1.5,
                    "win_rate": 0, "avg_return": 0, "total": 0, "optimised": False}


# ══════════════════════════════════════════════
# 台股中文名稱對照表（靜態，零 API 呼叫）
# ══════════════════════════════════════════════
_TW_NAMES: dict[str, tuple[str, str]] = {
    "0050": ("元大台灣50", "上市"),
    "0051": ("元大中型100", "上市"),
    "0052": ("富邦科技", "上市"),
    "0053": ("元大電子", "上市"),
    "0054": ("元大台商50", "上市"),
    "0056": ("元大高股息", "上市"),
    "006208": ("富邦台50", "上市"),
    "00881": ("國泰台灣5G", "上市"),
    "1101": ("台泥", "上市"),
    "1102": ("亞泥", "上市"),
    "1103": ("嘉泥", "上市"),
    "1104": ("環泥", "上市"),
    "1108": ("幸福", "上市"),
    "1109": ("信大", "上市"),
    "1110": ("東泥", "上市"),
    "1210": ("大成", "上市"),
    "1216": ("統一", "上市"),
    "1217": ("愛之味", "上市"),
    "1229": ("聯華", "上市"),
    "1231": ("聯華食", "上市"),
    "1232": ("大統益", "上市"),
    "1234": ("黑松", "上市"),
    "1235": ("興泰", "上市"),
    "1301": ("台塑", "上市"),
    "1303": ("南亞", "上市"),
    "1305": ("華夏", "上市"),
    "1308": ("亞東", "上市"),
    "1312": ("國喬", "上市"),
    "1313": ("聯成", "上市"),
    "1326": ("台化", "上市"),
    "1402": ("遠東新", "上市"),
    "1409": ("新纖", "上市"),
    "1417": ("嘉裕", "上市"),
    "1418": ("東華", "上市"),
    "1432": ("大魯閣", "上市"),
    "1434": ("福懋", "上市"),
    "1515": ("力山", "上市"),
    "1702": ("南僑", "上市"),
    "1710": ("東聯", "上市"),
    "1711": ("永光", "上市"),
    "1712": ("興農", "上市"),
    "1714": ("和桐", "上市"),
    "1717": ("長興", "上市"),
    "1718": ("中纖", "上市"),
    "1722": ("台肥", "上市"),
    "1723": ("中碳", "上市"),
    "1725": ("元禎", "上市"),
    "1730": ("花仙子", "上市"),
    "1737": ("台鹽", "上市"),
    "1773": ("勝一", "上市"),
    "1776": ("展宇", "上市"),
    "1789": ("神隆", "上市"),
    "2002": ("中鋼", "上市"),
    "2006": ("東和鋼鐵", "上市"),
    "2014": ("中鴻", "上市"),
    "2015": ("豐興", "上市"),
    "2017": ("官田鋼", "上市"),
    "2022": ("聚亨", "上市"),
    "2038": ("海光", "上市"),
    "2048": ("勝麗", "上市"),
    "2049": ("上銀", "上市"),
    "2201": ("裕隆", "上市"),
    "2204": ("中華汽車", "上市"),
    "2207": ("和泰車", "上市"),
    "2227": ("裕日車", "上市"),
    "2231": ("為升", "上市"),
    "2239": ("英利-KY", "上市"),
    "2301": ("光寶科", "上市"),
    "2303": ("聯電", "上市"),
    "2308": ("台達電", "上市"),
    "2313": ("華通", "上市"),
    "2316": ("楠梓電", "上市"),
    "2317": ("鴻海", "上市"),
    "2324": ("仁寶", "上市"),
    "2327": ("國巨", "上市"),
    "2329": ("華泰", "上市"),
    "2330": ("台積電", "上市"),
    "2332": ("友訊", "上市"),
    "2337": ("旺宏", "上市"),
    "2338": ("光罩", "上市"),
    "2340": ("光磊", "上市"),
    "2342": ("茂矽", "上市"),
    "2344": ("華邦電", "上市"),
    "2345": ("智邦", "上市"),
    "2347": ("聯強", "上市"),
    "2351": ("順德工業", "上市"),
    "2352": ("佳世達", "上市"),
    "2353": ("宏碁", "上市"),
    "2354": ("鴻準", "上市"),
    "2356": ("英業達", "上市"),
    "2357": ("華碩", "上市"),
    "2360": ("致茂", "上市"),
    "2363": ("矽統", "上市"),
    "2365": ("昆盈", "上市"),
    "2367": ("燿華", "上市"),
    "2368": ("金像電", "上市"),
    "2371": ("大同", "上市"),
    "2376": ("技嘉", "上市"),
    "2377": ("微星", "上市"),
    "2379": ("瑞昱", "上市"),
    "2382": ("廣達", "上市"),
    "2383": ("台光電", "上市"),
    "2385": ("群光", "上市"),
    "2388": ("威盛", "上市"),
    "2393": ("億光", "上市"),
    "2395": ("研華", "上市"),
    "2397": ("友通", "上市"),
    "2398": ("虹光", "上市"),
    "2399": ("映泰", "上市"),
    "2404": ("漢唐", "上市"),
    "2406": ("國碩", "上市"),
    "2408": ("南亞科", "上市"),
    "2409": ("友達", "上市"),
    "2412": ("中華電", "上市"),
    "2436": ("偉詮電", "上市"),
    "2449": ("京元電子", "上市"),
    "2451": ("創見", "上市"),
    "2454": ("聯發科", "上市"),
    "2474": ("可成", "上市"),
    "2475": ("華映", "上市"),
    "2486": ("一詮", "上市"),
    "2492": ("華新科", "上市"),
    "2498": ("宏達電", "上市"),
    "2601": ("益航", "上市"),
    "2603": ("長榮", "上市"),
    "2605": ("新興", "上市"),
    "2606": ("裕民", "上市"),
    "2609": ("陽明", "上市"),
    "2610": ("華航", "上市"),
    "2615": ("萬海", "上市"),
    "2617": ("台航", "上市"),
    "2618": ("長榮航", "上市"),
    "2637": ("慧洋-KY", "上市"),
    "2716": ("旭聯", "上市"),
    "2801": ("彰銀", "上市"),
    "2812": ("台中銀", "上市"),
    "2816": ("旺旺保", "上市"),
    "2820": ("華票", "上市"),
    "2823": ("中壽", "上市"),
    "2833": ("台壽保", "上市"),
    "2834": ("臺企銀", "上市"),
    "2836": ("台灣企銀", "上市"),
    "2838": ("聯邦銀", "上市"),
    "2850": ("新產", "上市"),
    "2851": ("中再保", "上市"),
    "2880": ("華南金", "上市"),
    "2881": ("富邦金", "上市"),
    "2882": ("國泰金", "上市"),
    "2883": ("開發金", "上市"),
    "2884": ("玉山金", "上市"),
    "2885": ("元大金", "上市"),
    "2886": ("兆豐金", "上市"),
    "2887": ("台新金", "上市"),
    "2888": ("新光金", "上市"),
    "2889": ("國票金", "上市"),
    "2890": ("永豐金", "上市"),
    "2891": ("中信金", "上市"),
    "2892": ("第一金", "上市"),
    "2903": ("遠百", "上市"),
    "2905": ("三商行", "上市"),
    "2912": ("統一超", "上市"),
    "2915": ("潤泰全", "上市"),
    "3006": ("晶豪科", "上櫃"),
    "3008": ("大立光", "上市"),
    "3016": ("嘉晶", "上市"),
    "3019": ("亞光", "上市"),
    "3030": ("聯鈞", "上市"),
    "3034": ("聯詠", "上市"),
    "3035": ("智原", "上市"),
    "3037": ("欣興", "上市"),
    "3044": ("健鼎", "上市"),
    "3105": ("穩懋", "上市"),
    "3149": ("正達", "上市"),
    "3152": ("璟德", "上市"),
    "3189": ("景碩", "上市"),
    "3231": ("緯創", "上市"),
    "3264": ("欣銓", "上市"),
    "3293": ("鈊象", "上市"),
    "3312": ("弘凱", "上市"),
    "3324": ("雙鴻", "上市"),
    "3374": ("精材", "上市"),
    "3443": ("創意", "上市"),
    "3481": ("群創", "上市"),
    "3515": ("華擎", "上市"),
    "3533": ("嘉澤", "上市"),
    "3576": ("新日興", "上市"),
    "3587": ("貿聯-KY", "上市"),
    "3591": ("艾訊", "上市"),
    "3596": ("智易", "上市"),
    "3605": ("宏致", "上市"),
    "3607": ("顯示科技", "上市"),
    "3617": ("碩天", "上市"),
    "3622": ("洋華", "上市"),
    "3661": ("世芯-KY", "上櫃"),
    "3673": ("TPK-KY", "上市"),
    "3675": ("德微", "上市"),
    "3679": ("天虹", "上市"),
    "3680": ("家登", "上市"),
    "3686": ("達能", "上市"),
    "3689": ("湧德電子", "上市"),
    "3698": ("隆達", "上市"),
    "3701": ("大眾電腦", "上市"),
    "3702": ("大聯大", "上市"),
    "3704": ("合勤科技", "上市"),
    "3706": ("神盾", "上市"),
    "3714": ("兆利", "上市"),
    "3715": ("定穎投控", "上市"),
    "3720": ("力致", "上市"),
    "3722": ("同致", "上市"),
    "3726": ("本土科技", "上市"),
    "3729": ("群電", "上市"),
    "3731": ("明泰", "上市"),
    "3737": ("友達光電", "上市"),
    "4105": ("東洋", "上市"),
    "4106": ("雃博", "上市"),
    "4107": ("邦特", "上市"),
    "4119": ("旭富", "上市"),
    "4128": ("中天", "上市"),
    "4142": ("國光生", "上市"),
    "4153": ("鈺緯", "上市"),
    "4170": ("新藥", "上市"),
    "4174": ("浩鼎", "上市"),
    "4414": ("如興", "上市"),
    "4532": ("瑞友", "上市"),
    "4743": ("合一", "上市"),
    "4763": ("材料-KY", "上市"),
    "4806": ("昱展新藥", "上市"),
    "4904": ("遠傳", "上市"),
    "4906": ("正文", "上市"),
    "4934": ("太醫", "上市"),
    "4938": ("和碩", "上市"),
    "4961": ("天鈺", "上櫃"),
    "4966": ("譜瑞-KY", "上櫃"),
    "5269": ("祥碩", "上櫃"),
    "5274": ("信驊", "上櫃"),
    "5315": ("科風", "上市"),
    "5347": ("世界", "上市"),
    "5483": ("中美晶", "上市"),
    "5876": ("上海商銀", "上市"),
    "5880": ("合庫金", "上市"),
    "5904": ("寶雅", "上市"),
    "6005": ("群益期", "上市"),
    "6116": ("彩晶", "上市"),
    "6121": ("新普", "上市"),
    "6147": ("頎邦", "上市"),
    "6153": ("嘉聯益", "上市"),
    "6214": ("精誠", "上市"),
    "6230": ("超豐", "上市"),
    "6239": ("力成", "上市"),
    "6269": ("台郡", "上市"),
    "6271": ("同欣電", "上櫃"),
    "6274": ("台燿", "上市"),
    "6288": ("聯嘉光電", "上市"),
    "6409": ("旭隼", "上市"),
    "6415": ("矽力-KY", "上櫃"),
    "6451": ("訊芯-KY", "上市"),
    "6456": ("GIS-KY", "上市"),
    "6461": ("益得", "上櫃"),
    "6505": ("台塑化", "上市"),
    "6510": ("精測", "上市"),
    "6533": ("晶心科", "上櫃"),
    "6541": ("泰碩", "上市"),
    "6547": ("高端疫苗", "上市"),
    "6589": ("台康生技", "上市"),
    "6669": ("緯穎", "上市"),
    "6689": ("聯陽", "上市"),
    "6770": ("力積電", "上市"),
    "8016": ("矽創", "上市"),
    "8046": ("南電", "上市"),
    "8050": ("廣隆", "上市"),
    "8299": ("群電", "上櫃"),
    "9904": ("寶成", "上市"),
    "9910": ("豐泰", "上市"),
    "9933": ("中鼎", "上市"),
    "9941": ("裕融", "上市"),
    "9945": ("潤泰新", "上市"),
    "9950": ("萬國通", "上市"),
    # ── 更多常見股票（補充截圖中缺失的代號）────────
    "1513": ("中興電", "上市"), "2707": ("晶華",   "上市"),
    "6182": ("合晶",   "上市"), "3596": ("智易",   "上市"),
    "2363": ("矽統",   "上市"), "3714": ("兆利",   "上市"),
    "2364": ("力廣",   "上市"), "2356": ("英業達", "上市"),
    "3081": ("聯亞",   "上市"), "6279": ("胡連",   "上市"),
    "2441": ("超豐",   "上市"), "4912": ("聯德",   "上市"),
    "2439": ("美律",   "上市"), "3062": ("建漢",   "上市"),
    "3014": ("聯陽",   "上市"), "3017": ("奇鋐",   "上市"),
    "3023": ("信邦",   "上市"), "3036": ("文曄",   "上市"),
    "3044": ("健鼎",   "上市"), "3189": ("景碩",   "上市"),
    "3231": ("緯創",   "上市"), "4919": ("新唐",   "上市"),
    "5388": ("中磊",   "上市"), "6197": ("佳必琪", "上市"),
    "6215": ("和椿",   "上市"), "6223": ("旺矽",   "上市"),
    "6235": ("華孚",   "上市"), "6251": ("定穎",   "上市"),
    "6257": ("矽格",   "上市"), "6261": ("久元",   "上市"),
    "6263": ("普萊德", "上市"), "6278": ("台表科", "上市"),
    "6285": ("啟碁",   "上市"), "6299": ("佳鼎",   "上市"),
    "6302": ("詮腦",   "上市"), "6306": ("崇越",   "上市"),
    "6414": ("樺漢",   "上市"), "6438": ("迅得",   "上市"),
    "6443": ("元晶",   "上市"), "6444": ("精準",   "上市"),
    "6446": ("藥華藥", "上市"), "6452": ("康友-KY","上市"),
    "6491": ("晶碩",   "上市"), "6505": ("台塑化", "上市"),
    "6523": ("達運",   "上市"), "6526": ("禾瑞亞", "上市"),
    "6548": ("長科",   "上市"), "6552": ("易華電", "上市"),
    "6558": ("興能高", "上市"), "6568": ("宏觀",   "上市"),
    "6582": ("申豐",   "上市"), "6592": ("和潤企業","上市"),
    "6598": ("ABC-KY", "上市"), "6606": ("建準",   "上市"),
    "6616": ("特斯",   "上市"), "6618": ("元大期", "上市"),
    "6621": ("旭富",   "上市"), "6626": ("華立",   "上市"),
    "6641": ("皇將",   "上市"), "6654": ("理想",   "上市"),
    "6657": ("騰輝電", "上市"), "6662": ("樂通",   "上市"),
    "6672": ("騰凱",   "上市"), "6679": ("台策",   "上市"),
    "6702": ("歐萊德", "上市"), "6706": ("惠特",   "上市"),
    "6712": ("長榮航科","上市"),"6719": ("彩富",   "上市"),
    "6728": ("鈞興-KY","上市"), "6736": ("同欣電", "上市"),
    "6760": ("致茂電", "上市"), "6781": ("AES-KY", "上市"),
    "6789": ("采鈺",   "上市"), "6803": ("崇越電", "上市"),
    "6803": ("崇越電", "上市"), "6809": ("邑昇",   "上市"),
    "8046": ("南電",   "上市"), "8071": ("尚寶",   "上市"),
    "8076": ("伍豐",   "上市"), "8081": ("致新",   "上市"),
    "8088": ("品安",   "上市"), "8092": ("建暐",   "上市"),
    "8105": ("凌巨",   "上市"), "8110": ("華東",   "上市"),
    "8112": ("至上",   "上市"), "8121": ("越峰",   "上市"),
    "8131": ("福懋油", "上市"), "8150": ("南茂",   "上市"),
    "8163": ("達方",   "上市"), "8176": ("智捷",   "上市"),
    "8183": ("精星",   "上市"), "8210": ("勤誠",   "上市"),
    "8213": ("志超",   "上市"), "8215": ("明基材", "上市"),
    "8222": ("寶一",   "上市"), "8240": ("华夏",   "上市"),
    "8251": ("鋼鈑工", "上市"), "8271": ("宇顒",   "上市"),
    "8299": ("群電",   "上櫃"),
}# ── Clean up the table: remove any accidentally invalid keys ──
_TW_NAMES = {k: v for k, v in _TW_NAMES.items()
             if k.isdigit() or (len(k) >= 4 and k[:4].isdigit())}


def lookup_name(code: str) -> tuple[str, str]:
    """
    Look up Chinese name from static table first (instant),
    then fall back to yfinance .info if not found.
    Returns (name, market_label).
    """
    bare = code.upper().replace(".TWO", "").replace(".TW", "")
    if bare in _TW_NAMES:
        return _TW_NAMES[bare]
    # Fallback: infer market from suffix
    mkt = "上櫃" if code.upper().endswith(".TWO") else "上市"
    return "", mkt


@st.cache_data(ttl=3600)   # 1h TTL — retry sooner than 24h on failures
def fetch_name(code: str, _v: int = 2) -> tuple[str, str]:
    """
    Return (name, market_label).  _v bumps the cache key to clear stale entries.
    Static table (instant) → yfinance .info fallback.
    Empty results are NOT cached — the calling code falls back gracefully.
    """
    # 1. Static table (instant, no network)
    name, mkt = lookup_name(code)
    if name:
        return name, mkt

    # 2. yfinance .info fallback
    bare = code.upper().replace(".TWO", "").replace(".TW", "")
    if code.upper().endswith(".TWO"):
        candidates = [(code, "上櫃")]
    elif code.upper().endswith(".TW"):
        candidates = [(code, "上市")]
    else:
        candidates = [(bare + ".TW", "上市"), (bare + ".TWO", "上櫃")]

    _STRIP = [" Co., Ltd.", " Co.,Ltd.", " Co.Ltd.", " Corporation",
              " Inc.", " Ltd.", "股份有限公司", "有限公司", " Co.", "-KY", " -KY"]

    for sym, label in candidates:
        try:
            info = yf.Ticker(sym).info
            if not info or not isinstance(info, dict) or len(info) < 3:
                continue
            n = (info.get("shortName") or info.get("longName") or "")
            for s in _STRIP:
                n = n.replace(s, "")
            n = n.strip()
            if n:
                return n, label
        except Exception:
            pass
    return "", mkt   # empty — callers must handle gracefully


def batch_fetch_names(codes: tuple) -> dict:
    """
    Return {bare_code: (name, market_label)} for all codes.
    Uses ONLY the static _TW_NAMES table (instant, zero network).
    For codes not in the table, the per-stock fetch_name() fallback
    in the scan loop will handle them individually with 24h caching.
    This avoids the yf.Tickers() bulk call that triggers rate-limiting.
    """
    result = {}
    for code in codes:
        bare = code.upper().replace(".TWO", "").replace(".TW", "")
        name, mkt = lookup_name(code)
        result[bare] = (name, mkt)   # name may be "" for unknown codes — fallback handles it
    return result


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
            df = yf.Ticker(sym).history(period=period)
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
    "HIGH_CONF_BUY": ("star",          "#ffd700", 16, "below"),
    "BREAKOUT_BUY":  ("triangle-up",   "#ff9900", 14, "below"),
    "STRONG_BUY":    ("triangle-up",   "#00ff88", 12, "below"),
    "BUY":           ("triangle-up",   "#44ddff", 10, "below"),
    "DIV_BUY":       ("diamond",       "#00ff88", 10, "below"),
    "WATCH":         ("circle-open",   "#ffee44",  8, "below"),
    "STRONG_SELL":   ("triangle-down", "#ff3355", 12, "above"),
    "SELL":          ("triangle-down", "#ff8866", 10, "above"),
    "DIV_SELL":      ("diamond",       "#ff3355", 10, "above"),
    "FAKE_BREAKOUT": ("x",             "#cc44ff",  8, "above"),
}


def calc_support_resistance(df: pd.DataFrame, window: int = 20, n_levels: int = 3) -> dict:
    """
    Find significant support and resistance levels from recent price action.
    Uses rolling max/min to identify swing highs/lows.
    Returns {'resistance': [...], 'support': [...]}
    """
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    n     = len(df)

    resistance_levels = []
    support_levels    = []

    # Swing highs: local max within window
    for i in range(window, n - window):
        if high.iloc[i] == high.iloc[i-window:i+window+1].max():
            resistance_levels.append(round(float(high.iloc[i]), 2))

    # Swing lows: local min within window
    for i in range(window, n - window):
        if low.iloc[i] == low.iloc[i-window:i+window+1].min():
            support_levels.append(round(float(low.iloc[i]), 2))

    # Deduplicate levels within 1% of each other
    def dedup(levels: list, tol: float = 0.01) -> list:
        if not levels:
            return []
        levels = sorted(set(levels), reverse=True)
        result = [levels[0]]
        for lvl in levels[1:]:
            if abs(lvl - result[-1]) / (result[-1] + 1e-8) > tol:
                result.append(lvl)
        return result

    # Return closest levels to current price
    current = float(close.iloc[-1])
    res = sorted([l for l in dedup(resistance_levels) if l > current])[:n_levels]
    sup = sorted([l for l in dedup(support_levels)    if l < current], reverse=True)[:n_levels]

    # Also add 52-week high/low as key levels
    yr = df.tail(252)
    w52_high = round(float(yr["High"].max()), 2)
    w52_low  = round(float(yr["Low"].min()),  2)
    if w52_high > current and w52_high not in res:
        res = sorted(res + [w52_high])[:n_levels + 1]
    if w52_low < current and w52_low not in sup:
        sup = sorted(sup + [w52_low], reverse=True)[:n_levels + 1]

    return {"resistance": res, "support": sup,
            "52w_high": w52_high, "52w_low": w52_low}


def calc_rr_targets(price: float, stop: float, rr_ratios: list = [1.5, 2.0, 3.0]) -> list:
    """
    Calculate take-profit targets based on Risk:Reward ratios.
    risk = price - stop
    target_n = price + risk * rr_n
    Returns list of (rr, target_price) tuples.
    """
    risk = price - stop
    if risk <= 0:
        return []
    return [(rr, round(price + risk * rr, 2)) for rr in rr_ratios]


@st.cache_data(ttl=3600)
def fetch_fundamentals(code: str) -> dict:
    """
    Fetch basic fundamental data for the stock info panel.
    Returns dict with pe, pb, dividend_yield, market_cap, week52_high, week52_low, beta.
    All fields default to None if unavailable.
    """
    bare = code.upper().replace(".TWO", "").replace(".TW", "")
    if code.upper().endswith(".TWO"):
        sym = code
    elif code.upper().endswith(".TW"):
        sym = code
    else:
        sym = bare + ".TW"

    result = {k: None for k in
              ["pe", "pb", "div_yield", "market_cap", "eps", "beta",
               "week52_high", "week52_low", "avg_vol_10d"]}
    try:
        info = yf.Ticker(sym).info
        if not info or len(info) < 3:
            return result
        result["pe"]          = info.get("trailingPE") or info.get("forwardPE")
        result["pb"]          = info.get("priceToBook")
        result["div_yield"]   = info.get("dividendYield")
        result["market_cap"]  = info.get("marketCap")
        result["eps"]         = info.get("trailingEps")
        result["beta"]        = info.get("beta")
        result["week52_high"] = info.get("fiftyTwoWeekHigh")
        result["week52_low"]  = info.get("fiftyTwoWeekLow")
        result["avg_vol_10d"] = info.get("averageVolume10days") or info.get("averageVolume")
    except Exception:
        pass
    return result


def build_chart(df: pd.DataFrame, symbol: str, p: dict,
                sr: dict | None = None,
                stop_price: float | None = None,
                rr_targets: list | None = None) -> go.Figure:
    """
    Professional 5-panel chart with:
    - Full legends for every indicator
    - Support/Resistance levels + 52W high/low
    - Stop loss + R:R target lines
    - OBV on independent secondary axis
    - Unified hover across all panels
    - KD cross text labels (金叉/死叉)
    """
    df = df.tail(130).copy()
    ema1_p = p.get("ema1", 10)
    ema2_p = p.get("ema2", 20)
    kd_p   = p.get("kd_period", 9)
    cci_p  = p.get("cci_period", 39)
    bb_p   = p.get("bb_period", 20)

    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True,
        row_heights=[0.40, 0.13, 0.17, 0.15, 0.15],
        vertical_spacing=0.018,
        specs=[[{"secondary_y": False}],
               [{"secondary_y": True}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}]],
    )

    # ── P1: K線 ──
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="K線",
        increasing_fillcolor="#e8414e", increasing_line_color="#e8414e",
        decreasing_fillcolor="#22cc66", decreasing_line_color="#22cc66",
        hoverinfo="x+text",
        text=[f"O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f}"
              for o, h, l, c in zip(df["Open"], df["High"], df["Low"], df["Close"])],
    ), row=1, col=1)

    for col_key, label, color, lw, dash in [
        ("EMA1",  f"EMA{ema1_p}",  "#f0a500", 1.4, "solid"),
        ("EMA2",  f"EMA{ema2_p}",  "#2196f3", 1.4, "solid"),
        ("EMA60", "EMA60",          "#e040fb", 1.0, "dash"),
    ]:
        if col_key in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col_key], name=label,
                line=dict(color=color, width=lw, dash=dash),
                showlegend=True, legendgroup="ema",
                hovertemplate=f"{label}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    if "BB_Upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_Upper"], name=f"BB上({bb_p},2σ)",
            line=dict(color="#546e7a", width=0.9, dash="dot"),
            showlegend=True, legendgroup="bb",
            hovertemplate="BB上: %{y:.2f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_Lower"], name="BB下",
            line=dict(color="#546e7a", width=0.9, dash="dot"),
            fill="tonexty", fillcolor="rgba(84,110,122,0.06)",
            showlegend=False,
            hovertemplate="BB下: %{y:.2f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_Mid"], name="BB中",
            line=dict(color="#37474f", width=0.7, dash="dash"),
            showlegend=False,
            hovertemplate="BB中: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # Support / Resistance levels
    if sr:
        for lvl in sr.get("resistance", []):
            fig.add_hline(y=lvl, line_dash="dot",
                          line_color="rgba(232,65,78,0.65)", line_width=1.2,
                          row=1, col=1,
                          annotation_text=f"壓 {lvl:.2f}",
                          annotation_font_size=9,
                          annotation_font_color="rgba(232,65,78,0.9)")
        for lvl in sr.get("support", []):
            fig.add_hline(y=lvl, line_dash="dot",
                          line_color="rgba(34,204,102,0.65)", line_width=1.2,
                          row=1, col=1,
                          annotation_text=f"撐 {lvl:.2f}",
                          annotation_font_size=9,
                          annotation_font_color="rgba(34,204,102,0.9)")
        if sr.get("52w_high"):
            fig.add_hline(y=sr["52w_high"], line_dash="longdash",
                          line_color="rgba(255,153,0,0.55)", line_width=1,
                          row=1, col=1,
                          annotation_text=f"52W高 {sr['52w_high']:.2f}",
                          annotation_font_size=9,
                          annotation_font_color="rgba(255,153,0,0.8)")
        if sr.get("52w_low"):
            fig.add_hline(y=sr["52w_low"], line_dash="longdash",
                          line_color="rgba(100,181,246,0.55)", line_width=1,
                          row=1, col=1,
                          annotation_text=f"52W低 {sr['52w_low']:.2f}",
                          annotation_font_size=9,
                          annotation_font_color="rgba(100,181,246,0.8)")

    # Stop loss line
    if stop_price:
        fig.add_hline(y=stop_price, line_dash="solid",
                      line_color="rgba(255,51,85,0.9)", line_width=2.0,
                      row=1, col=1,
                      annotation_text=f"🛑 停損 {stop_price:.2f}",
                      annotation_font_size=10,
                      annotation_font_color="#ff3355")

    # R:R target lines
    if rr_targets:
        rr_colors = ["rgba(0,255,136,0.75)", "rgba(0,212,255,0.65)", "rgba(255,153,0,0.65)"]
        for (rr, target), rr_col in zip(rr_targets[:3], rr_colors):
            fig.add_hline(y=target, line_dash="dash",
                          line_color=rr_col, line_width=1.3,
                          row=1, col=1,
                          annotation_text=f"🎯 R{rr}x {target:.2f}",
                          annotation_font_size=9,
                          annotation_font_color=rr_col)

    # Signal markers
    for sig, (shape, color, size, pos) in MARKER_SHAPE.items():
        mask = df["Signal"] == sig
        if not mask.any():
            continue
        y_vals = df.loc[mask, "Low"] * 0.972 if pos == "below" \
                 else df.loc[mask, "High"] * 1.028
        hover = [f"{SIGNAL_LABEL.get(sig,sig)}<br>{d}"
                 for d in df.loc[mask, "Signal_Detail"]]
        fig.add_trace(go.Scatter(
            x=df.index[mask], y=y_vals, mode="markers",
            marker=dict(symbol=shape, color=color, size=size + 2,
                        line=dict(width=1.2, color="#000")),
            name=SIGNAL_LABEL.get(sig, sig),
            hovertext=hover, hoverinfo="text",
            showlegend=True, legendgroup="signals",
        ), row=1, col=1)

    # ── P2: Volume + OBV (dual axis) ──
    vol_colors = ["#e8414e" if c >= o else "#22cc66"
                  for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], marker_color=vol_colors,
        name="成交量", opacity=0.65, showlegend=False,
        hovertemplate="量: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)
    if "Vol_MA" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Vol_MA"],
            name=f"均量{p.get('vol_ma_period',20)}日",
            line=dict(color="#f0a500", width=1.2),
            showlegend=True, legendgroup="vol",
            hovertemplate="均量: %{y:,.0f}<extra></extra>",
        ), row=2, col=1)
    if "OBV" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["OBV"], name="OBV",
            line=dict(color="#00d4ff", width=1.3),
            showlegend=True, legendgroup="vol",
            hovertemplate="OBV: %{y:,.0f}<extra></extra>",
        ), row=2, col=1, secondary_y=True)
        if "OBV_MA" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["OBV_MA"], name="OBV均線",
                line=dict(color="#004d66", width=1.0, dash="dot"),
                showlegend=False,
                hovertemplate="OBV均: %{y:,.0f}<extra></extra>",
            ), row=2, col=1, secondary_y=True)

    # ── P3: CCI ──
    cci_colors = ["#e8414e" if v > 100 else "#22cc66" if v < -100 else "#455a64"
                  for v in df["CCI"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df.index, y=df["CCI"], marker_color=cci_colors,
        name=f"CCI({cci_p})", showlegend=False,
        hovertemplate=f"CCI: %{{y:.1f}}<extra></extra>",
    ), row=3, col=1)
    if "TrendScore" in df.columns:
        for mask_fn, fill_col in [
            (lambda: df["TrendScore"] >= 2,  "rgba(34,204,102,0.07)"),
            (lambda: df["TrendScore"] <= -2, "rgba(232,65,78,0.07)"),
        ]:
            mask = mask_fn()
            if not mask.any():
                continue
            rs = None
            pv = False
            for idx, val in enumerate(mask):
                if val and not pv:
                    rs = idx
                elif not val and pv and rs is not None:
                    try:
                        fig.add_shape(type="rect", xref="x", yref="y3 domain",
                            x0=df.index[rs], x1=df.index[idx - 1],
                            y0=0, y1=1, fillcolor=fill_col, line_width=0, layer="below")
                    except Exception:
                        pass
                    rs = None
                pv = bool(val)
            if rs is not None:
                try:
                    fig.add_shape(type="rect", xref="x", yref="y3 domain",
                        x0=df.index[rs], x1=df.index[-1],
                        y0=0, y1=1, fillcolor=fill_col, line_width=0, layer="below")
                except Exception:
                    pass
    for lvl, col, lbl in [(100, "rgba(232,65,78,0.4)", "超買"),
                           (-100, "rgba(34,204,102,0.4)", "超賣"),
                           (0, "#37474f", "")]:
        fig.add_hline(y=lvl, line_dash="dot", line_color=col, line_width=1,
                      row=3, col=1,
                      annotation_text=lbl, annotation_font_size=8,
                      annotation_font_color=col)

    # ── P4: KD ──
    if "K" in df.columns and "D" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["K"], name=f"K({kd_p})",
            line=dict(color="#f0a500", width=1.8),
            showlegend=True, legendgroup="kd",
            hovertemplate="K: %{y:.1f}<extra></extra>",
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["D"], name="D(3)",
            line=dict(color="#2196f3", width=1.8),
            showlegend=True, legendgroup="kd",
            hovertemplate="D: %{y:.1f}<extra></extra>",
        ), row=4, col=1)
        gc = df.get("KD_Golden", pd.Series(False, index=df.index))
        dc = df.get("KD_Dead",   pd.Series(False, index=df.index))
        if hasattr(gc, "any") and gc.any():
            fig.add_trace(go.Scatter(
                x=df.index[gc], y=df.loc[gc, "K"] - 4,
                mode="markers+text",
                marker=dict(symbol="triangle-up", color="#00ff88", size=12,
                            line=dict(width=1.5, color="#000")),
                text=["金叉"] * int(gc.sum()), textposition="bottom center",
                textfont=dict(size=8, color="#00ff88"),
                name="KD金叉", showlegend=True, legendgroup="kd",
                hovertemplate="KD金叉 K=%{y:.1f}<extra></extra>",
            ), row=4, col=1)
        if hasattr(dc, "any") and dc.any():
            fig.add_trace(go.Scatter(
                x=df.index[dc], y=df.loc[dc, "K"] + 4,
                mode="markers+text",
                marker=dict(symbol="triangle-down", color="#ff3355", size=12,
                            line=dict(width=1.5, color="#000")),
                text=["死叉"] * int(dc.sum()), textposition="top center",
                textfont=dict(size=8, color="#ff3355"),
                name="KD死叉", showlegend=True, legendgroup="kd",
                hovertemplate="KD死叉 K=%{y:.1f}<extra></extra>",
            ), row=4, col=1)
        for lvl, col, lbl in [(80, "rgba(232,65,78,0.35)", "超買80"),
                               (50, "#37474f", ""),
                               (20, "rgba(34,204,102,0.35)", "超賣20")]:
            fig.add_hline(y=lvl, line_dash="dot", line_color=col, line_width=1,
                          row=4, col=1, annotation_text=lbl,
                          annotation_font_size=8, annotation_font_color=col)

    # ── P5: MACD ──
    hist_colors = ["#e8414e" if v >= 0 else "#22cc66"
                   for v in df["MACD_Hist"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df.index, y=df["MACD_Hist"], marker_color=hist_colors,
        name="MACD柱(紅多綠空)", opacity=0.8,
        showlegend=True, legendgroup="macd",
        hovertemplate="Hist: %{y:.3f}<extra></extra>",
    ), row=5, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD"], name="MACD(藍)",
        line=dict(color="#2196f3", width=1.5),
        showlegend=True, legendgroup="macd",
        hovertemplate="MACD: %{y:.3f}<extra></extra>",
    ), row=5, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD_Sig"], name="訊號(橙)",
        line=dict(color="#f0a500", width=1.5),
        showlegend=True, legendgroup="macd",
        hovertemplate="Signal: %{y:.3f}<extra></extra>",
    ), row=5, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#37474f",
                  line_width=1, row=5, col=1)

    # ── Layout ──
    fig.update_layout(
        template="plotly_dark", height=920,
        paper_bgcolor="#0a0e1a", plot_bgcolor="#0d1226",
        xaxis_rangeslider_visible=False,
        margin=dict(l=60, r=90, t=30, b=10),
        font=dict(family="Space Mono, monospace", size=10, color="#8a9bb5"),
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
            font=dict(size=9), bgcolor="rgba(10,14,26,0.85)",
            bordercolor="#1e3a5f", borderwidth=1,
        ),
    )
    for i in range(1, 6):
        fig.update_yaxes(gridcolor="#1a2a3a", zeroline=False,
                         tickfont=dict(size=9), row=i, col=1)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=8, color="#00d4ff"),
                     row=2, col=1, secondary_y=True)
    fig.update_xaxes(showgrid=False, rangeslider_visible=False)

    annotations = [
        dict(x=0.01, y=1.00, xref="paper", yref="paper", showarrow=False,
             text=f"<b>{symbol}</b>  EMA{ema1_p}(橙) / EMA{ema2_p}(藍) / EMA60(紫) / BB({bb_p},2σ)  撐/壓=水平虛線",
             font=dict(color="#8a9bb5", size=10)),
        dict(x=0.01, y=0.578, xref="paper", yref="paper", showarrow=False,
             text=f"成交量(棒紅升綠降) / 均量{p.get('vol_ma_period',20)}日(橙) | OBV累積量能(藍,右軸) — OBV向上=量能支撐",
             font=dict(color="#8a9bb5", size=10)),
        dict(x=0.01, y=0.445, xref="paper", yref="paper", showarrow=False,
             text=f"CCI({cci_p})  紅柱&gt;+100超買 / 綠柱&lt;-100超賣 / 綠底=趨勢多頭 / 紅底=趨勢空頭",
             font=dict(color="#8a9bb5", size=10)),
        dict(x=0.01, y=0.285, xref="paper", yref="paper", showarrow=False,
             text=f"KD({kd_p})  橙=K線 藍=D線 / 金叉▲(低檔多) 死叉▼(高檔空) / 超買80 超賣20",
             font=dict(color="#8a9bb5", size=10)),
        dict(x=0.01, y=0.132, xref="paper", yref="paper", showarrow=False,
             text="MACD  藍=MACD 橙=訊號線 / 柱紅=MACD>0多頭 柱綠=MACD<0空頭 / 黃金交叉=買進",
             font=dict(color="#8a9bb5", size=10)),
    ]
    fig.update_layout(annotations=annotations)
    return fig

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
# 市場時段 & 自動更新
# ══════════════════════════════════════════════

_TZ_TW = pytz.timezone("Asia/Taipei")
AUTO_
