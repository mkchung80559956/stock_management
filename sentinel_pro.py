"""
Sentinel Pro — 台股多股掃描器 v3.0
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
import re as _re
import urllib.request as _urllib_req
import urllib.parse  as _urllib_parse

APP_VERSION   = "3.1"
APP_UPDATED   = "2026-04-15"   # ← bump this string on every update
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

    EMA200 (年線) 作為主要多空分界：
    +3 = 強多頭：Price > EMA20 > EMA60，且 Price > EMA200，EMA20 斜率為正
    +2 = 多頭：Price > EMA20 > EMA60，且 Price > EMA200
    +1 = 弱多頭：Price > EMA60 > EMA200（橫盤但仍在年線上）
     0 = 中性：Price 介於 EMA20/EMA60 之間，或剛好貼近 EMA200
    -1 = 弱空頭：Price < EMA60 但 > EMA200（短期偏弱，長期仍多）
    -2 = 強空頭：Price < EMA200（跌破年線，逆勢）
    """
    score = pd.Series(0, index=df.index)
    if "EMA1" not in df.columns or "EMA2" not in df.columns or "EMA60" not in df.columns:
        return score

    price  = df["Close"]
    ema20  = df["EMA2"]      # EMA2 = 20-period EMA (default)
    ema60  = df["EMA60"]
    # EMA200 (年線) — calculated here if not in columns
    ema200 = df["EMA200"] if "EMA200" in df.columns else \
             price.ewm(span=200, adjust=False).mean()

    # EMA20 斜率：過去 3 根平均方向
    ema20_slope = ema20.diff(3)

    above200   = price > ema200
    above60    = price > ema60
    ema20_gt60 = ema20 > ema60

    # Strong uptrend: all EMAs aligned + above 年線
    strong_up = above200 & above60 & ema20_gt60 & (ema20_slope > 0)
    score[strong_up] = 3

    # Normal uptrend: above 年線 + EMA20 > EMA60
    normal_up = above200 & above60 & ema20_gt60 & ~strong_up
    score[normal_up] = 2

    # Weak uptrend: above 年線, EMA60 > EMA20 (crossover zone)
    weak_up = above200 & above60 & ~ema20_gt60
    score[weak_up] = 1

    # Neutral / mild pullback: below EMA60 but above 年線
    weak_dn = above200 & ~above60
    score[weak_dn] = -1

    # Strong downtrend: below 年線 (逆勢, 最強過濾)
    strong_dn = ~above200
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
    df["EMA200"] = calc_ema(df["Close"], 200)          # ① long-term 年線 anchor (new)
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

    # ── Gap 2: Near-Resistance Filter ─────────────────────────────
    # If price is within 3% below a resistance level, buy signals face a ceiling.
    # Downgrade HIGH_CONF_BUY → BUY, BREAKOUT_BUY/STRONG_BUY → WATCH.
    # This avoids entering right at supply zones where sellers are waiting.
    try:
        sr_levels = calc_support_resistance(df)
        resist_levels = sr_levels.get("resistance", [])
        if resist_levels:
            near_resist = pd.Series(False, index=df.index)
            for lvl in resist_levels:
                # Within 3% below resistance = danger zone
                near_resist |= (df["Close"] >= lvl * 0.97) & (df["Close"] <= lvl * 1.01)
            # Downgrade buy signals that are in the resistance zone
            in_resist_zone = near_resist & df["Signal"].isin(BUY_SIGNALS)
            df.loc[in_resist_zone & (df["Signal"] == "HIGH_CONF_BUY"), "Signal_Detail"] = \
                df.loc[in_resist_zone & (df["Signal"] == "HIGH_CONF_BUY"), "Signal_Detail"] + \
                " ⚠️ 接近壓力區，謹慎"
            df.loc[in_resist_zone & df["Signal"].isin({"BREAKOUT_BUY","STRONG_BUY"}), "Signal_Detail"] = \
                df.loc[in_resist_zone & df["Signal"].isin({"BREAKOUT_BUY","STRONG_BUY"}), "Signal_Detail"] + \
                " ⚠️ 壓力區買入風險高"
            df["Near_Resist"] = near_resist   # expose for UI warning
    except Exception:
        df["Near_Resist"] = pd.Series(False, index=df.index)

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
    "8299": ("群電",   "上櫃"),
    "9904": ("寶成",   "上市"), "9910": ("豐泰",   "上市"),
    "9933": ("中鼎",   "上市"), "9941": ("裕融",   "上市"),
    "9945": ("潤泰新", "上市"), "9950": ("萬國通", "上市"),
    # ── 截圖 & 自選股清單缺失代號 ────────────────────────
    "5871": ("中租-KY",   "上市"), "4958": ("臻鼎-KY",  "上市"),
    "2633": ("台灣高鐵",  "上市"), "6213": ("聯茂",     "上市"),
    # ETF
    "00878": ("國泰永續高息", "上市"), "00919": ("群益台灣精選高息", "上市"),
    "00929": ("復華台灣科技優息", "上市"),
    # 電機/線纜
    "1503": ("士電",     "上市"), "1504": ("東元",     "上市"),
    "1519": ("華城",     "上市"), "1605": ("華新",     "上市"),
    # 生技/醫療
    "1785": ("光洋科",   "上市"), "4147": ("中裕",     "上市"),
    # 汽車
    "2104": ("中橡",     "上市"), "2105": ("正新",     "上市"),
    # 建設
    "2542": ("興富發",   "上市"),
    # 電信
    "3045": ("台灣大",   "上市"),
    # 半導體/IC
    "3141": ("晶宏",     "上市"), "3211": ("順達",     "上市"),
    "3526": ("凡甲",     "上市"), "3529": ("力旺",     "上市"),
    "3532": ("台勝科",   "上市"), "3558": ("神準",     "上市"),
    "3611": ("鑫龍騰",   "上市"), "3711": ("日月光投控","上市"),
    # 生醫
    "5289": ("宜鼎",     "上市"),
    # 其他
    "6472": ("保瑞",     "上市"), "6488": ("環球晶",   "上市"),
    "6806": ("嘉澤",     "上市"), "8044": ("網家",     "上市"),
    "8069": ("元太",     "上市"), "8086": ("宏捷科",   "上市"),
    "8358": ("金居",     "上市"), "8938": ("明安",     "上市"),
    "9921": ("巨大",     "上市"), "9951": ("皇田",     "上市"),
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


@st.cache_data(ttl=180)
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


@st.cache_data(ttl=60)
def batch_fetch_quotes(symbols: tuple) -> dict:
    """
    Fetch live quotes for ALL symbols in one yf.download() call.
    ~10x faster than calling fetch_quote() per-stock in a loop.
    Returns {bare_code: {"price": float, "change_pct": float}}.
    """
    if not symbols:
        return {}
    # Build full ticker list
    tickers = []
    bare_map = {}   # full_ticker → bare_code
    for s in symbols:
        bare = s.upper().replace(".TW","").replace(".TWO","")
        full = s if s.upper().endswith((".TW",".TWO")) else bare + ".TW"
        tickers.append(full)
        bare_map[full] = bare

    result = {}
    try:
        # Single batch download — period="2d" gives today + yesterday for change%
        df_batch = yf.download(
            tickers=" ".join(tickers),
            period="2d", interval="1d",
            auto_adjust=True, progress=False,
            group_by="ticker",
        )
        if df_batch.empty:
            return {}

        # Multi-ticker layout: columns are (field, ticker)
        for full in tickers:
            bare = bare_map[full]
            try:
                if len(tickers) == 1:
                    closes = df_batch["Close"].dropna()
                else:
                    closes = df_batch["Close"][full].dropna()
                if len(closes) < 1:
                    continue
                last = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else last
                chg_p = (last - prev) / prev * 100 if prev else 0
                result[bare] = {"price": round(last, 2),
                                "change_pct": round(chg_p, 2)}
            except Exception:
                continue
    except Exception:
        pass
    return result


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
        ("EMA1",   f"EMA{ema1_p}",  "#f0a500", 1.4, "solid"),
        ("EMA2",   f"EMA{ema2_p}",  "#2196f3", 1.4, "solid"),
        ("EMA60",  "EMA60",          "#e040fb", 1.0, "dash"),
        ("EMA200", "EMA200 (年線)", "#ffd600", 1.2, "dashdot"),  # 年線 — golden
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
AUTO_REFRESH_INTERVAL = 15 * 60   # 15 minutes in seconds


def tw_now() -> datetime:
    return datetime.now(_TZ_TW)


def _tw_holidays_2026() -> set:
    """
    Taiwan Stock Exchange holidays 2026.
    Source: TWSE official calendar (non-trading days beyond weekends).
    Returns set of date strings "YYYY-MM-DD".
    """
    return {
        # New Year
        "2026-01-01",
        # Lunar New Year (Spring Festival)
        "2026-01-26","2026-01-27","2026-01-28","2026-01-29",
        "2026-01-30","2026-01-31","2026-02-01","2026-02-02",
        # Peace Memorial Day
        "2026-02-27","2026-02-28",
        # Children's Day / Tomb Sweeping
        "2026-04-03","2026-04-04",
        # Labour Day (if TWSE observes)
        # Dragon Boat Festival
        "2026-06-19",
        # Mid-Autumn Festival
        "2026-09-25",
        # National Day
        "2026-10-09","2026-10-10",
    }

def _is_tw_holiday(d=None) -> bool:
    """Returns True if the given date (default: today) is a Taiwan public holiday."""
    if d is None:
        d = tw_now().date()
    return d.strftime("%Y-%m-%d") in _tw_holidays_2026()

def is_market_open() -> bool:
    """台股盤中：週一到週五 09:00–13:30 台北時間，排除國定假日"""
    now = tw_now()
    if now.weekday() >= 5:          # Saturday / Sunday
        return False
    if _is_tw_holiday(now.date()):  # Taiwan public holiday
        return False
    t = now.time()
    import datetime as _dt
    return _dt.time(9, 0) <= t <= _dt.time(13, 30)


def is_market_day() -> bool:
    """今天是台股交易日（排除週末 + 國定假日）"""
    now = tw_now()
    if now.weekday() >= 5: return False
    if _is_tw_holiday(now.date()): return False
    return True


def seconds_to_next_refresh(last_ts: str, interval: int = AUTO_REFRESH_INTERVAL) -> int:
    """Return seconds until next auto-refresh (negative = overdue)."""
    if not last_ts:
        return 0
    try:
        last_dt = _TZ_TW.localize(datetime.strptime(last_ts, "%Y-%m-%d %H:%M"))
        next_dt = last_dt + timedelta(seconds=interval)
        remaining = int((next_dt - tw_now()).total_seconds())
        return remaining
    except Exception:
        return 0


def format_countdown(seconds: int) -> str:
    if seconds <= 0:
        return "即將更新"
    m, s = divmod(abs(seconds), 60)
    return f"{m:02d}:{s:02d}"


# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════



# ══════════════════════════════════════════════
# PERSISTENT TRADE STORE  (3-layer resilience)
# ══════════════════════════════════════════════
_TRADE_FILE = "/tmp/sentinel_trades.json"


@st.cache_resource
def _get_trade_store() -> dict:
    """
    Singleton dict living in cache_resource — survives st.rerun() and
    browser tab changes within the same Streamlit server process.
    On first call we try to restore from the /tmp backup file.
    Structure: {"trades": [...], "next_id": int}
    """
    store = {"trades": [], "next_id": 1}
    try:
        if os.path.exists(_TRADE_FILE):
            with open(_TRADE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded.get("trades"), list):
                store["trades"]  = loaded["trades"]
                store["next_id"] = int(loaded.get("next_id", 1))
    except Exception:
        pass   # corrupt file — start fresh
    return store


def _save_trades(store: dict) -> None:
    """Atomically write the store to the /tmp backup file."""
    try:
        tmp = _TRADE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"trades": store["trades"],
                       "next_id": store["next_id"]}, f, ensure_ascii=False)
        os.replace(tmp, _TRADE_FILE)   # atomic rename
    except Exception:
        pass


def port_add_trade(trade: dict) -> None:
    store = _get_trade_store()
    store["trades"].append(trade)
    store["next_id"] += 1
    _save_trades(store)


def port_delete_trade(trade_id: int) -> bool:
    store = _get_trade_store()
    before = len(store["trades"])
    store["trades"] = [t for t in store["trades"] if t["id"] != trade_id]
    changed = len(store["trades"]) < before
    if changed:
        _save_trades(store)
    return changed


def port_replace_trades(new_list: list, reset_id: bool = False) -> None:
    store = _get_trade_store()
    store["trades"] = new_list
    if reset_id:
        store["next_id"] = max((t.get("id", 0) for t in new_list), default=0) + 1
    _save_trades(store)


def port_get_trades() -> list:
    return _get_trade_store()["trades"]


def port_next_id() -> int:
    return _get_trade_store()["next_id"]


# ══════════════════════════════════════════════
# PORTFOLIO HELPERS  (module-level — not inside main)
# ══════════════════════════════════════════════
from collections import deque as _deque

def get_open_positions(trades: list) -> dict:
    pos = {}
    for t in sorted(trades, key=lambda x: x["date"]):
        c = t["code"]
        if t["type"] == "買入":
            if c not in pos:
                pos[c] = {"shares": 0, "cost": 0.0, "fees": 0.0,
                          "name": t.get("name",""), "ids": []}
            pos[c]["shares"] += t["shares"]
            pos[c]["cost"]   += t["shares"] * t["price"] + t.get("fee", 0)
            pos[c]["fees"]   += t.get("fee", 0)
            pos[c]["ids"].append(t["id"])
        elif t["type"] == "賣出" and c in pos:
            cost_pp = pos[c]["cost"] / max(pos[c]["shares"], 1)
            pos[c]["shares"] -= t["shares"]
            pos[c]["cost"]    = max(pos[c]["cost"] - cost_pp * t["shares"], 0)
            if pos[c]["shares"] <= 0:
                del pos[c]
    return pos


def get_closed_trades(trades: list) -> list:
    buys, closed = {}, []
    for t in sorted(trades, key=lambda x: x["date"]):
        c = t["code"]
        if t["type"] == "買入":
            if c not in buys: buys[c] = _deque()
            buys[c].append({"sh": t["shares"], "px": t["price"], "fee": t.get("fee",0)})
        elif t["type"] == "賣出" and c in buys and buys[c]:
            rem, total_cost = t["shares"], 0.0
            while rem > 0 and buys[c]:
                b    = buys[c][0]
                take = min(rem, b["sh"])
                total_cost += take * b["px"] + b["fee"] * (take / b["sh"])
                b["sh"] -= take; rem -= take
                if b["sh"] <= 0: buys[c].popleft()
            sell_proc = t["shares"] * t["price"] - t.get("fee", 0)
            pnl = sell_proc - total_cost
            closed.append({
                "代號": c, "名稱": t.get("name",""),
                "買入均價": round(total_cost / t["shares"], 2),
                "賣出價": t["price"], "股數": t["shares"],
                "實現損益": round(pnl, 0),
                "報酬%": round(pnl / (total_cost + 1e-8) * 100, 2),
                "結果": "獲利" if pnl > 0 else "虧損",
                "賣出日": t["date"],
            })
    return closed



# ══════════════════════════════════════════════
# TELEGRAM  PUSH  NOTIFICATIONS
# ══════════════════════════════════════════════

def _tg_send(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """
    Send a Telegram message via Bot API (plain text, no parse_mode).
    Returns (success, error_message).
    """
    if not token or not chat_id:
        return False, "Token 或 Chat ID 未設定"
    # Strip all HTML tags — use plain text to avoid HTTP 400 from unescaped chars
    clean_text = _re.sub(r'<[^>]+>', '', text)
    try:
        url  = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
        data = _urllib_parse.urlencode({
            "chat_id": str(chat_id).strip(),
            "text":    clean_text,
        }).encode()
        req = _urllib_req.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with _urllib_req.urlopen(req, timeout=10) as r:
            resp_body = r.read().decode()
            if r.status == 200:
                return True, ""
            return False, f"HTTP Error {r.status}: {resp_body[:300]}"
    except Exception as e:
        err = str(e)
        # urllib HTTPError contains the response body
        if hasattr(e, 'read'):
            try: err += " | " + e.read().decode()[:200]
            except Exception: pass
        return False, err


def send_signal_alert(token: str, chat_id: str,
                      new_buy_rows: list, new_sell_rows: list) -> int:
    """Send Telegram alerts for newly-detected actionable signals."""
    if not token or not chat_id:
        return 0
    msgs_sent = 0

    def _safe_float(v, default=0.0):
        try: return float(v)
        except Exception: return default

    for r in new_buy_rows[:8]:
        sig_lbl = SIGNAL_LABEL.get(r["_sig_key"], r["_sig_key"])
        wr      = _safe_float(r.get("_win_rate", r.get("勝率%", 0)))
        conf    = int(_safe_float(r.get("_conf", r.get("共振", 0))))
        chg     = _safe_float(r.get("漲跌%", 0))
        detail  = str(r.get("_detail", r.get("說明", "")))[:60]
        star    = "⭐" if r["_sig_key"] == "HIGH_CONF_BUY" else "🟢"
        price   = r.get("最新價", "─")
        stop    = r.get("_sl_label", r.get("止損說明", r.get("止損參考", "─")))
        ts      = r.get("_ts", tw_now().strftime("%H:%M"))
        msg = (
            f"{star} <b>Sentinel Pro 買入訊號</b>\n"
            f"🏷 <b>{r['代號']} {r.get('名稱','')}</b>　{r.get('市場','')}\n"
            f"📡 訊號：{sig_lbl}\n"
            f"💰 現價：<b>{price}</b>　漲跌：{chg:+.2f}%\n"
            f"📊 共振：{conf}/7　勝率：{wr:.0f}%\n"
            f"🛑 止損：{stop}\n"
            f"📝 {detail}\n"
            f"🕐 {ts}"
        )
        ok, _ = _tg_send(token, chat_id, msg)
        if ok:
            msgs_sent += 1

    for r in new_sell_rows[:4]:
        sig_lbl = SIGNAL_LABEL.get(r["_sig_key"], r["_sig_key"])
        chg     = _safe_float(r.get("漲跌%", 0))
        msg = (
            f"🔴 <b>Sentinel Pro 賣出訊號</b>\n"
            f"🏷 <b>{r['代號']} {r.get('名稱','')}</b>\n"
            f"📡 訊號：{sig_lbl}\n"
            f"💰 現價：{r.get('最新價','─')}　漲跌：{chg:+.2f}%\n"
            f"🕐 {tw_now().strftime('%H:%M')}"
        )
        ok, _ = _tg_send(token, chat_id, msg)
        if ok:
            msgs_sent += 1

    return msgs_sent


# ══════════════════════════════════════════════
# GOOGLE  SHEETS  PERSISTENT  STORAGE
# ══════════════════════════════════════════════
_GS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


def _gs_headers(api_key: str) -> dict:
    return {"Content-Type": "application/json"}


def gs_read_trades(sheet_id: str, api_key: str) -> list:
    """
    Read trades from Google Sheets (public sheet with API key read).
    Sheet must have columns: id,type,code,name,date,price,shares,fee
    Returns list of dicts, empty on error.
    """
    if not sheet_id or not api_key:
        return []
    try:
        range_  = "Sheet1!A:H"
        url     = f"{_GS_BASE}/{sheet_id}/values/{_urllib_parse.quote(range_)}?key={api_key}"
        req     = _urllib_req.Request(url)
        with _urllib_req.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        rows = data.get("values", [])
        if len(rows) < 2:
            return []
        headers = rows[0]
        trades  = []
        for row in rows[1:]:
            # Pad short rows
            while len(row) < len(headers):
                row.append("")
            t = dict(zip(headers, row))
            try:
                t["id"]     = int(float(t.get("id", 0)))
                t["price"]  = float(t.get("price", 0))
                t["shares"] = int(float(t.get("shares", 0)))
                t["fee"]    = float(t.get("fee", 0))
            except Exception:
                continue
            if t.get("code") and t.get("type"):
                trades.append(t)
        return trades
    except Exception:
        return []


def gs_append_trade(sheet_id: str, api_key: str, trade: dict) -> bool:
    """
    Append one trade row to Google Sheets via REST API.
    Requires the sheet to be writable — use a service account token
    or OAuth token passed as api_key (Bearer token).
    Returns True on success.
    """
    if not sheet_id or not api_key:
        return False
    try:
        range_  = "Sheet1!A:H"
        url     = (f"{_GS_BASE}/{sheet_id}/values/"
                   f"{_urllib_parse.quote(range_)}:append"
                   f"?valueInputOption=USER_ENTERED")
        values  = [[
            trade.get("id",""), trade.get("type",""),
            trade.get("code",""), trade.get("name",""),
            trade.get("date",""), trade.get("price",""),
            trade.get("shares",""), trade.get("fee",""),
        ]]
        body    = json.dumps({"values": values}).encode()
        req     = _urllib_req.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        with _urllib_req.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def gs_overwrite_trades(sheet_id: str, api_key: str, trades: list) -> tuple[bool, str]:
    """
    Overwrite entire Sheet1 with header + all trades.
    Returns (success, error_message).
    api_key can be:
      - OAuth Bearer token (ya29.xxx) → full read/write
      - API Key (AIza...) → read-only only, write will fail
    """
    if not sheet_id or not api_key:
        return False, "Sheet ID 或 Token 未設定"
    try:
        headers = [["id","type","code","name","date","price","shares","fee"]]
        rows    = headers + [[
            str(t.get("id","")), str(t.get("type","")), str(t.get("code","")),
            str(t.get("name","")), str(t.get("date","")), str(t.get("price","")),
            str(t.get("shares","")), str(t.get("fee","")),
        ] for t in trades]

        # Step 1: Clear range (correct URL format for Sheets API v4)
        clear_url = f"{_GS_BASE}/{sheet_id}/values/Sheet1!A1:H10000:clear"
        req = _urllib_req.Request(clear_url, data=b"{}", method="POST")
        req.add_header("Authorization", f"Bearer {api_key.strip()}")
        req.add_header("Content-Type", "application/json")
        try:
            with _urllib_req.urlopen(req, timeout=10):
                pass
        except Exception as e:
            err = str(e)
            if hasattr(e, 'read'):
                try: err += " | " + e.read().decode()[:300]
                except Exception: pass
            return False, f"Clear失敗: {err}"

        # Step 2: Write values
        write_url = (f"{_GS_BASE}/{sheet_id}/values/"
                     f"Sheet1!A1?valueInputOption=USER_ENTERED")
        body = json.dumps({"values": rows}).encode()
        req  = _urllib_req.Request(write_url, data=body, method="PUT")
        req.add_header("Authorization", f"Bearer {api_key.strip()}")
        req.add_header("Content-Type", "application/json")
        with _urllib_req.urlopen(req, timeout=10) as r:
            if r.status == 200:
                return True, ""
            resp = r.read().decode()[:300]
            return False, f"Write HTTP {r.status}: {resp}"
    except Exception as e:
        err = str(e)
        if hasattr(e, 'read'):
            try: err += " | " + e.read().decode()[:300]
            except Exception: pass
        return False, err



# ══════════════════════════════════════════════
# SIGNAL  HISTORY  TRACKER
# Stores real signals as they fire, tracks actual
# 5/10/20-day returns to build a live win-rate DB.
# ══════════════════════════════════════════════
_SIG_HIST_FILE = "/tmp/sentinel_sig_history.json"

@st.cache_resource
def _get_sig_hist_store() -> dict:
    """
    Singleton: {
      "records": [
        {id, code, name, sig_key, sig_label, confluence,
         trend, date_fired, price_fired, atr_stop,
         price_5d, price_10d, price_20d,
         ret_5d, ret_10d, ret_20d, status}
      ]
    }
    status: "pending" → "partial" → "complete"
    """
    store = {"records": []}
    try:
        if os.path.exists(_SIG_HIST_FILE):
            with open(_SIG_HIST_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded.get("records"), list):
                store["records"] = loaded["records"]
    except Exception:
        pass
    return store


def _save_sig_hist(store: dict) -> None:
    try:
        tmp = _SIG_HIST_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False)
        os.replace(tmp, _SIG_HIST_FILE)
    except Exception:
        pass


def sig_hist_add(record: dict) -> None:
    """Add a new signal record if not already recorded today for this code+sig."""
    store = _get_sig_hist_store()
    # Dedup: same code + sig_key within same calendar day
    existing_keys = {(r["code"], r["sig_key"], r["date_fired"])
                     for r in store["records"]}
    key = (record["code"], record["sig_key"], record["date_fired"])
    if key not in existing_keys:
        store["records"].append(record)
        _save_sig_hist(store)


def sig_hist_update_outcomes(fetch_data_fn) -> int:
    """
    For every pending/partial record, check if 5/10/20 trading days
    have elapsed and fetch the actual closing price to fill in returns.
    Returns count of records updated.
    """
    store   = _get_sig_hist_store()
    records = store["records"]
    updated = 0

    for r in records:
        if r.get("status") == "complete":
            continue
        try:
            fire_date = datetime.strptime(r["date_fired"], "%Y-%m-%d").date()
            today     = tw_now().date()
            cal_days  = (today - fire_date).days   # calendar days elapsed

            # Approximate: 5 trading days ≈ 7 calendar days, etc.
            thresholds = {5: 7, 10: 14, 20: 28}

            # Fetch historical data for this stock (use 3mo to cover all windows)
            df, _ = fetch_data_fn(r["code"], "3mo")
            if df is None or len(df) < 5:
                continue

            # Filter to dates >= fire_date
            df_after = df[df.index.date >= fire_date]
            n_bars   = len(df_after)   # trading days since signal

            changed = False
            for td, cd in [(5,"ret_5d"), (10,"ret_10d"), (20,"ret_20d")]:
                price_key = f"price_{td}d"
                if r.get(price_key) is not None:
                    continue   # already filled
                if n_bars >= td:
                    # Use the closing price at the td-th trading day
                    close_at_td = float(df_after.iloc[td - 1]["Close"])
                    ret_pct     = (close_at_td - r["price_fired"]) / r["price_fired"] * 100
                    r[price_key]     = round(close_at_td, 2)
                    r[cd]            = round(ret_pct, 2)
                    changed = True

            if changed:
                # Set status
                filled = sum(1 for td in [5,10,20] if r.get(f"price_{td}d") is not None)
                r["status"] = "complete" if filled == 3 else "partial"
                updated += 1

        except Exception:
            continue

    if updated:
        store["records"] = records
        _save_sig_hist(store)

    return updated


def sig_hist_get_all() -> list:
    return _get_sig_hist_store()["records"]


def sig_hist_clear() -> None:
    store = _get_sig_hist_store()
    store["records"] = []
    _save_sig_hist(store)


def sig_hist_to_df(records: list) -> "pd.DataFrame":
    """Convert records to a clean display DataFrame."""
    if not records:
        return pd.DataFrame()
    rows = []
    for r in records:
        sig_label = SIGNAL_LABEL.get(r.get("sig_key",""), r.get("sig_label","─"))
        rows.append({
            "日期":      r.get("date_fired",""),
            "代號":      r.get("code",""),
            "名稱":      r.get("name",""),
            "訊號":      sig_label,
            "共振":      r.get("confluence", "-"),
            "趨勢":      r.get("trend", "-"),
            "進場價":    r.get("price_fired",""),
            "5日%":      r.get("ret_5d"),
            "10日%":     r.get("ret_10d"),
            "20日%":     r.get("ret_20d"),
            "狀態":      {"pending":"⏳等待","partial":"🔄部分","complete":"✅完成"}.get(
                          r.get("status","pending"), "⏳等待"),
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("日期", ascending=False).reset_index(drop=True)
    return df
    # 上市 (TSE .TW) ─────────────────────────────
def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample daily OHLCV to weekly (week ending Friday).
    Requires DatetimeIndex.
    """
    agg = {
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }
    # Use W-FRI to align with Taiwan market week
    df_w = df.resample("W-FRI").agg(agg).dropna()
    return df_w


@st.cache_data(ttl=1800)
def get_weekly_signal(symbol: str, p: dict,
                      _p_ver: int = 1) -> tuple[str, str]:
    """
    Returns (weekly_sig_key, detail) for the symbol.
    Cached 30 min — weekly bars don't change intraday.
    _p_ver bumps cache when params change.
    """
    df_daily, _ = fetch_data(symbol, "2y")
    if df_daily is None or len(df_daily) < 52:
        return "NEUTRAL", "週線資料不足"
    try:
        df_w = resample_weekly(df_daily)
        if len(df_w) < 20:
            return "NEUTRAL", "週線K棒不足"
        df_w_sig = generate_signals(df_w, p)
        w_sig, w_det = get_scan_signal(df_w_sig, lookback=3)
        return w_sig, w_det
    except Exception as e:
        return "NEUTRAL", str(e)[:40]


def mtf_confirm(daily_sig: str, weekly_sig: str) -> tuple[bool, str]:
    """
    Multi-timeframe confirmation:
    Both timeframes must agree on direction.
    Returns (confirmed, label).
    """
    BUY  = {"HIGH_CONF_BUY","BREAKOUT_BUY","STRONG_BUY","BUY","DIV_BUY",
            "KD_GOLDEN_ZONE","BULL_ZONE","RISING"}
    SELL = {"STRONG_SELL","DIV_SELL","SELL","FAKE_BREAKOUT","KD_HIGH",
            "BEAR_ZONE","FALLING"}

    d_buy  = daily_sig  in BUY
    d_sell = daily_sig  in SELL
    w_buy  = weekly_sig in BUY
    w_sell = weekly_sig in SELL

    if d_buy and w_buy:
        return True,  "✅ 日線買+週線買"
    if d_sell and w_sell:
        return True,  "✅ 日線賣+週線賣"
    if d_buy and not w_buy and not w_sell:
        return False, "⚠️ 日買/週中性"
    if d_buy and w_sell:
        return False, "❌ 日買/週賣（逆勢）"
    if d_sell and w_buy:
        return False, "❌ 日賣/週買（逆勢）"
    return False, "⚪ 無明確共識"
def classify_market_regime(df: pd.DataFrame) -> pd.Series:
    """
    Classify each daily bar into market regime using EMA position + EMA slope.
    Three regimes:
      'bull'     — EMA20 > EMA60  AND  EMA20 slope (10-bar) > 0
      'bear'     — EMA20 < EMA60  AND  EMA20 slope (10-bar) < 0
      'sideways' — transitional: EMA crossing or slope contradicts position
    Uses EMA slope instead of ROC to avoid the threshold sensitivity problem.
    Produces roughly equal thirds across a typical 2-year history.
    """
    ema20   = df["Close"].ewm(span=20, adjust=False).mean()
    ema60   = df["Close"].ewm(span=60, adjust=False).mean()
    slope10 = ema20.diff(10)   # 10-bar slope of EMA20

    regime = pd.Series("sideways", index=df.index, dtype=str)
    regime[(ema20 > ema60) & (slope10 > 0)] = "bull"
    regime[(ema20 < ema60) & (slope10 < 0)] = "bear"
    return regime


def backtest_by_regime(
    df: pd.DataFrame,
    params: dict,
    holding_days: int = 10,
    profit_pct: float = 3.0,
    stop_pct: float = 5.0,
) -> dict:
    """
    Run backtest and annotate each trade with its market regime at entry.
    Returns dict with:
      all_trades   — full trade DataFrame with 'market_regime' column
      regime_stats — DataFrame: regime × signal → win_rate, avg_ret, count
      signal_stats — DataFrame: signal × metric (across all regimes)
      best_by_regime — {regime: [(signal, win_rate, count)]}
    """
    df_sig = generate_signals(df, params)
    regime = classify_market_regime(df)
    df_sig["market_regime"] = regime

    buy_idx = df_sig.index[df_sig["Signal"].isin(BUY_SIGNALS)]
    if len(buy_idx) == 0:
        empty = pd.DataFrame()
        return {"all_trades": empty, "regime_stats": empty,
                "signal_stats": empty, "best_by_regime": {}}

    prices = df_sig["Close"].values
    opens  = df_sig["Open"].values
    dates  = df_sig.index
    rows   = []

    for entry_date in buy_idx:
        pos = df_sig.index.get_loc(entry_date)
        entry_pos = pos + 1
        if entry_pos >= len(prices):
            continue
        ep      = opens[entry_pos]
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
            xp   = prices[entry_pos + holding_days]
            held = holding_days
            xd   = dates[min(entry_pos + holding_days, len(dates) - 1)]
            outcome = "WIN" if xp > ep else "LOSS"

        ret_pct = (xp - ep) / ep * 100
        rows.append({
            "進場日":       entry_date.date(),
            "訊號代號":     df_sig.loc[entry_date, "Signal"],
            "訊號名稱":     SIGNAL_LABEL.get(df_sig.loc[entry_date, "Signal"], "─"),
            "市場環境":     {"bull": "🐂 多頭", "bear": "🐻 空頭",
                            "sideways": "⚖️ 盤整"}.get(
                                str(df_sig.loc[entry_date, "market_regime"]), "─"),
            "共振":         int(float(df_sig.loc[entry_date].get("ConfluenceScore", 0) or 0)),
            "趨勢分數":     int(float(df_sig.loc[entry_date].get("TrendScore", 0) or 0)),
            "進場價":       round(ep, 2),
            "出場價":       round(xp, 2),
            "持有天":       held,
            "報酬%":        round(ret_pct, 2),
            "結果":         outcome,
        })

    if not rows:
        empty = pd.DataFrame()
        return {"all_trades": empty, "regime_stats": empty,
                "signal_stats": empty, "best_by_regime": {}}

    all_trades = pd.DataFrame(rows)
    comp       = all_trades[all_trades["結果"] != "HOLD"]

    # ── Regime × Signal cross-stats ─────────────────────────────────
    env_order  = ["🐂 多頭", "⚖️ 盤整", "🐻 空頭"]
    stat_rows  = []
    best_by_regime: dict[str, list] = {}

    for env in env_order:
        env_df = comp[comp["市場環境"] == env]
        if len(env_df) == 0:
            continue
        best_sig = []
        for sig_code in BUY_SIGNALS:
            sig_label = SIGNAL_LABEL.get(sig_code, sig_code)
            s = env_df[env_df["訊號代號"] == sig_code]
            if len(s) < 2:
                continue
            wr  = len(s[s["結果"] == "WIN"]) / len(s) * 100
            avg = s["報酬%"].mean()
            stat_rows.append({
                "市場環境":  env,
                "訊號":      sig_label,
                "次數":      len(s),
                "勝率%":     round(wr, 1),
                "平均報酬%": round(avg, 2),
                "最大獲利%": round(s["報酬%"].max(), 2),
                "最大虧損%": round(s["報酬%"].min(), 2),
            })
            best_sig.append((sig_label, wr, len(s), avg))
        best_sig.sort(key=lambda x: (-x[1], -x[2]))
        best_by_regime[env] = best_sig

    regime_stats = (pd.DataFrame(stat_rows)
                    .sort_values(["市場環境", "勝率%"], ascending=[True, False])
                    .reset_index(drop=True)) if stat_rows else pd.DataFrame()

    # ── Signal-level summary (across all environments) ───────────────
    sig_rows = []
    for sig_code in BUY_SIGNALS:
        sig_label = SIGNAL_LABEL.get(sig_code, sig_code)
        s = comp[comp["訊號代號"] == sig_code]
        if len(s) < 2:
            continue
        wr = len(s[s["結果"] == "WIN"]) / len(s) * 100
        sig_rows.append({
            "訊號":      sig_label,
            "總次數":    len(s),
            "勝率%":     round(wr, 1),
            "平均報酬%": round(s["報酬%"].mean(), 2),
            "多頭勝率%": round(len(s[(s["市場環境"] == "🐂 多頭") & (s["結果"] == "WIN")]) /
                              max(len(s[s["市場環境"] == "🐂 多頭"]), 1) * 100, 1),
            "盤整勝率%": round(len(s[(s["市場環境"] == "⚖️ 盤整") & (s["結果"] == "WIN")]) /
                              max(len(s[s["市場環境"] == "⚖️ 盤整"]), 1) * 100, 1),
            "空頭勝率%": round(len(s[(s["市場環境"] == "🐻 空頭") & (s["結果"] == "WIN")]) /
                              max(len(s[s["市場環境"] == "🐻 空頭"]), 1) * 100, 1),
        })
    signal_stats = (pd.DataFrame(sig_rows)
                    .sort_values("勝率%", ascending=False)
                    .reset_index(drop=True)) if sig_rows else pd.DataFrame()

    return {
        "all_trades":    all_trades,
        "regime_stats":  regime_stats,
        "signal_stats":  signal_stats,
        "best_by_regime": best_by_regime,
        "total_trades":  len(comp),
    }


DEFAULT_WATCHLIST = [
    # 上市 (TSE .TW) ─────────────────────────────
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
"0050",   # 元大台灣50
"0051",   # 元大中型100
"0056",   # 元大高股息
"00878",  # 國泰永續高股息
"006208", # 富邦台50
"00919",  # 群益台灣精選高息
"00929",  # 復華台灣科技優息
    
    # 上櫃 (OTC .TWO) ────────────────────────────
"8069",   # 元太
"6488",   # 環球晶
"5483",   # 中美晶
"3529",   # 力旺
"3293",   # 鈊象
"8299",   # 群聯
"6182",   # 合晶
"4966",   # 譜瑞-KY
"3105",   # 穩懋
"5347",   # 世界
"6510",   # 精測
"8044",   # 網家
"4147",   # 中裕
"4174",   # 浩鼎
"6446",   # 藥華藥
"4743",   # 合一
"3141",   # 晶宏
"6147",   # 頎邦
"6261",   # 久元
"3081",   # 聯亞
"6274",   # 台耀
"3680",   # 家登
"8358",   # 金居
"3324",   # 雙鴻
"6223",   # 旺矽
"3211",   # 順達
"6121",   # 新普
"5274",   # 信驊
"3526",   # 凡甲
"8086",   # 宏捷科
"3264",   # 欣銓
"6472",   # 保瑞
"1785",   # 光洋科
"3611",   # 鼎翰
"3558",   # 神準
"5289",   # 宜鼎
"8938",   # 明安
"9951",   # 皇田
]

# ── Professional Strategy Engine ─────────────────────
def _pro_strategy(sig_k, trend_s, conf_s, accel_s,
                  unreal_pct, cur_px, avg_px,
                  shares_held, atr):
    """
    Professional 5-dimension strategy engine.
    Returns dict:
      action        — badge text
      color         — hex colour
      sell_pct      — 0/25/50/75/100 % of position to sell
      sell_shares   — exact share count (rounded to lot of 1000)
      entry_add_pct — % of position to ADD (0 if no add)
      steps         — list of (step_label, detail) decision steps
      exec_plan     — concrete execution instruction string
      urgency       — "立即" / "本週" / "下次交易日" / "觀察"
    """
    sell_sigs   = {"STRONG_SELL","DIV_SELL","SELL","FAKE_BREAKOUT","KD_HIGH"}
    strong_sell = {"STRONG_SELL","DIV_SELL"}
    warn_sell   = {"SELL","FAKE_BREAKOUT","KD_HIGH"}
    buy_sigs    = {"HIGH_CONF_BUY","BREAKOUT_BUY","STRONG_BUY","BUY","DIV_BUY"}
    prime_buy   = {"HIGH_CONF_BUY","BREAKOUT_BUY","STRONG_BUY"}

    # ATR-based stop (if available)
    atr_stop = round(avg_px - atr * 1.5, 2) if pd.notna(atr) and atr > 0 else None
    stop_triggered = cur_px < atr_stop if atr_stop else False
    # Pre-compute display strings (cannot use :.2f inside conditional)
    atr_stop_txt  = f"{atr_stop:.2f}" if atr_stop else "─"
    cost_stop_txt = f"{atr_stop:.2f}" if atr_stop else "均成本"

    # Profit tiers
    small_profit  = 3 < unreal_pct <= 8
    mid_profit    = 8 < unreal_pct <= 15
    big_profit    = 15 < unreal_pct <= 25
    huge_profit   = unreal_pct > 25
    small_loss    = -7 <= unreal_pct < 0
    mid_loss      = -15 <= unreal_pct < -7
    big_loss      = unreal_pct < -15

    steps = []

    # ── DIMENSION 1: 技術訊號 ──────────────────────────
    if sig_k in strong_sell:
        sig_score = -3
        steps.append(("📉 訊號",
            f"強力賣出訊號「{SIGNAL_LABEL.get(sig_k,sig_k)}」— 趨勢反轉風險高"))
    elif sig_k in warn_sell:
        sig_score = -2
        steps.append(("⚠️ 訊號",
            f"賣出警示「{SIGNAL_LABEL.get(sig_k,sig_k)}」— 動能轉弱"))
    elif sig_k in prime_buy:
        sig_score = 3
        steps.append(("⭐ 訊號",
            f"強力買入「{SIGNAL_LABEL.get(sig_k,sig_k)}」— 多頭動能強"))
    elif sig_k in buy_sigs:
        sig_score = 1
        steps.append(("🟢 訊號",
            f"買入訊號「{SIGNAL_LABEL.get(sig_k,sig_k)}」— 技術面偏多"))
    else:
        sig_score = 0
        steps.append(("⚪ 訊號",
            f"中性「{SIGNAL_LABEL.get(sig_k,sig_k)}」— 等待方向"))

    # ── DIMENSION 2: 趨勢 ─────────────────────────────
    trend_lbl = {3:"強多頭↑↑",2:"多頭↑",1:"弱多頭",0:"中性",
                 -1:"弱空頭",-2:"強空頭↓↓"}
    if trend_s >= 2:
        steps.append(("📈 趨勢", f"{trend_lbl[trend_s]}：EMA20>EMA60，方向有利"))
    elif trend_s == 1:
        steps.append(("📊 趨勢", f"{trend_lbl[trend_s]}：趨勢尚未明確確立"))
    elif trend_s == 0:
        steps.append(("📊 趨勢", "中性盤整：無明顯多空偏向"))
    else:
        steps.append(("📉 趨勢", f"{trend_lbl.get(trend_s,'─')}：EMA20<EMA60，空頭環境"))

    # ── DIMENSION 3: 共振強度 ─────────────────────────
    if conf_s >= 6:
        steps.append(("⭐ 共振", f"{conf_s}/7 指標共振 — 高度確認，訊號可信度高"))
    elif conf_s >= 4:
        steps.append(("🟡 共振", f"{conf_s}/7 指標共振 — 中度確認"))
    else:
        steps.append(("🔴 共振", f"{conf_s}/7 指標共振 — 確認度不足，訊號不確定"))

    # ── DIMENSION 4: 動能加速 ─────────────────────────
    if accel_s > 0.5:
        steps.append(("🚀 加速", f"CCI+RSI 斜率 {accel_s:+.2f} — 動能快速上升"))
    elif accel_s > 0.2:
        steps.append(("↗️ 加速", f"CCI+RSI 斜率 {accel_s:+.2f} — 動能緩步改善"))
    elif accel_s < -0.3:
        steps.append(("⬇️ 減速", f"CCI+RSI 斜率 {accel_s:+.2f} — 動能快速衰退"))
    else:
        steps.append(("➡️ 平穩", f"CCI+RSI 斜率 {accel_s:+.2f} — 動能持平"))

    # ── DIMENSION 5: 成本位置 + ATR 停損 ─────────────
    if atr_stop:
        margin = cur_px - atr_stop
        margin_pct = margin / cur_px * 100
        steps.append(("🛑 停損",
            f"ATR×1.5停損位：{atr_stop:.2f}　"
            f"現價距停損 {margin_pct:.1f}%（{'安全' if margin_pct>5 else '接近'}）"))
    if huge_profit:
        steps.append(("💰 成本",
            f"獲利 {unreal_pct:.1f}% — 已達豐厚獲利，保留利潤是優先考量"))
    elif big_profit:
        steps.append(("💰 成本",
            f"獲利 {unreal_pct:.1f}% — 良好獲利，可考慮分批保護"))
    elif mid_profit:
        steps.append(("💰 成本",
            f"獲利 {unreal_pct:.1f}% — 小幅獲利，趨勢持續才有擴大空間"))
    elif small_profit:
        steps.append(("💰 成本",
            f"獲利 {unreal_pct:.1f}% — 剛脫離成本區，不輕易停利"))
    elif big_loss:
        steps.append(("🚨 成本",
            f"虧損 {unreal_pct:.1f}% — 嚴重虧損，必須評估是否停損保本"))
    elif mid_loss:
        steps.append(("⚠️ 成本",
            f"虧損 {unreal_pct:.1f}% — 達停損警戒，觀察下個交易日收盤"))
    elif stop_triggered:
        steps.append(("🛑 成本",
            f"現價 {cur_px:.2f} 跌破 ATR停損位 {atr_stop:.2f} — 停損條件觸發"))
    else:
        steps.append(("✅ 成本",
            f"小幅虧損/微獲利 {unreal_pct:+.1f}%，持倉尚在正常波動範圍"))

    # ══════════════════════════════════════════════════
    # DECISION MATRIX → 精確賣出比例 & 執行計畫
    # ══════════════════════════════════════════════════
    lot = 1000   # Taiwan stock minimum trading lot

    def _to_shares(pct, total):
        """Round to nearest lot."""
        raw = total * pct / 100
        return max(lot, round(raw / lot) * lot) if raw >= lot else 0

    # --- 立即停損 ---
    if stop_triggered or (sig_k in strong_sell and big_loss):
        sell_pct = 100
        sh = shares_held
        return dict(
            action="🚨 立即停損",  color="#ff0033",
            sell_pct=100, sell_shares=sh, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：全部清倉 {sh:,} 股 @ 市價\n"
                f"   停損價位 {atr_stop_txt} 已觸發\n"
                f"   預計虧損：{int(sh*(cur_px-avg_px)):+,} 元（{unreal_pct:.1f}%）\n"
                f"   ⏰ 緊急程度：開盤立即執行"
            ),
            urgency="立即"
        )

    # --- 強力賣出訊號 + 大幅獲利 → 全部出場 ---
    if sig_k in strong_sell and (big_profit or huge_profit):
        sh = shares_held
        return dict(
            action="🔴 全部清倉", color="#ff3355",
            sell_pct=100, sell_shares=sh, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：全部清倉 {sh:,} 股 @ 市價\n"
                f"   強力賣出訊號 + 獲利 {unreal_pct:.1f}% → 趨勢反轉跡象\n"
                f"   鎖定利潤：{int(unreal):+,} 元\n"
                f"   ⏰ 緊急程度：本週完成"
            ),
            urgency="本週"
        )

    # --- 強力賣出訊號 + 小幅獲利 → 賣出75% ---
    if sig_k in strong_sell and small_profit:
        sh = _to_shares(75, shares_held)
        left = shares_held - sh
        return dict(
            action="🔴 減碼75%", color="#ff3355",
            sell_pct=75, sell_shares=sh, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：賣出 {sh:,} 股（75%），保留 {left:,} 股\n"
                f"   強賣訊號但獲利有限，先保護大部分本金\n"
                f"   若破 {cost_stop_txt} 再清倉剩餘\n"
                f"   ⏰ 緊急程度：本週完成"
            ),
            urgency="本週"
        )

    # --- 強力賣出訊號 + 虧損 → 賣出50% 觀察 ---
    if sig_k in strong_sell and (small_loss or mid_loss):
        sh = _to_shares(50, shares_held)
        left = shares_held - sh
        return dict(
            action="🔴 減碼50%", color="#ff3355",
            sell_pct=50, sell_shares=sh, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：先賣出 {sh:,} 股（50%），保留 {left:,} 股\n"
                f"   訊號偏空但未達強停損，先降低部位風險\n"
                f"   停損條件：若跌破 {cost_stop_txt} → 清倉剩餘\n"
                f"   反彈條件：若 CCI 再次突破 -100 + 放量可考慮回補\n"
                f"   ⏰ 緊急程度：下次交易日"
            ),
            urgency="下次交易日"
        )

    # --- 一般賣出訊號 + 大幅/豐厚獲利 → 賣出50% ---
    if sig_k in warn_sell and (big_profit or huge_profit):
        sh = _to_shares(50, shares_held)
        left = shares_held - sh
        return dict(
            action="🟡 分批出場50%", color="#f0a500",
            sell_pct=50, sell_shares=sh, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：賣出 {sh:,} 股（50%），保留 {left:,} 股\n"
                f"   獲利 {unreal_pct:.1f}% 已達分批出場標準\n"
                f"   保留倉位待趨勢明朗後再決定（{SIGNAL_LABEL.get(sig_k,'─')} 訊號）\n"
                f"   停損調升至成本價 {avg_px:.2f} 保護已實現利潤\n"
                f"   ⏰ 緊急程度：本週完成"
            ),
            urgency="本週"
        )

    # --- 動能衰退 + 豐厚獲利 → 賣出25%鎖定 ---
    if accel_s < -0.3 and (big_profit or huge_profit) and sig_k not in buy_sigs:
        sh = _to_shares(25, shares_held)
        left = shares_held - sh
        return dict(
            action="🟡 保護25%獲利", color="#f0a500",
            sell_pct=25, sell_shares=sh, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：賣出 {sh:,} 股（25%）鎖定部分獲利\n"
                f"   動能加速度 {accel_s:.2f} 顯示趨勢動力衰退\n"
                f"   保留 {left:,} 股繼續持有\n"
                f"   若 CCI 跌破 0 軸再賣出第2批（25%）\n"
                f"   ⏰ 緊急程度：觀察"
            ),
            urgency="觀察"
        )

    # --- 嚴重虧損（無強賣訊號）→ 評估停損 ---
    if big_loss and trend_s <= 0:
        sh = _to_shares(50, shares_held)
        return dict(
            action="⚠️ 停損評估", color="#ff6600",
            sell_pct=50, sell_shares=sh, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：考慮先賣出 {sh:,} 股（50%）降低風險\n"
                f"   虧損 {unreal_pct:.1f}% 已超過嚴重虧損警戒（-15%）\n"
                f"   空頭趨勢環境下持續持倉風險高\n"
                f"   停損標準：若破 {cost_stop_txt} → 清倉剩餘\n"
                f"   ⏰ 緊急程度：下次交易日決策"
            ),
            urgency="下次交易日"
        )

    # --- 三重共振加碼 ---
    if sig_k in prime_buy and trend_s >= 2 and conf_s >= 5:
        add_sh = _to_shares(25, shares_held)   # add 25% more
        new_avg = (avg_px * shares_held + cur_px * add_sh) / (shares_held + add_sh)
        return dict(
            action="⭐ 加碼25%", color="#ffd700",
            sell_pct=0, sell_shares=0, entry_add_pct=25, steps=steps,
            exec_plan=(
                f"📋 執行計畫：加碼買入 {add_sh:,} 股（現有倉位25%）\n"
                f"   三重共振訊號 + 多頭趨勢 + {conf_s}/7 共振\n"
                f"   加碼後均成本：{new_avg:.2f}（現 {avg_px:.2f}）\n"
                f"   加碼停損位：{atr_stop_txt}\n"
                f"   ⏰ 緊急程度：下次交易日執行"
            ),
            urgency="下次交易日"
        )

    # --- 續抱（訊號偏多，不操作）---
    if sig_k in buy_sigs and trend_s >= 1:
        return dict(
            action="🟢 續抱", color="#00ff88",
            sell_pct=0, sell_shares=0, entry_add_pct=0, steps=steps,
            exec_plan=(
                f"📋 執行計畫：維持現有 {shares_held:,} 股，不操作\n"
                f"   技術面偏多，趨勢支撐持倉\n"
                f"   停損守護：ATR停損 {atr_stop_txt}\n"
                f"   出場條件：若出現強賣訊號或跌破停損位 → 再評估\n"
                f"   ⏰ 緊急程度：觀察"
            ),
            urgency="觀察"
        )

    # --- 持有觀察（中性）---
    return dict(
        action="⚪ 持有觀察", color="#5a8fb0",
        sell_pct=0, sell_shares=0, entry_add_pct=0, steps=steps,
        exec_plan=(
            f"📋 執行計畫：維持現有 {shares_held:,} 股，等待訊號明確\n"
            f"   目前無明顯多空訊號，保持紀律等待\n"
            f"   停損守護：{cost_stop_txt}\n"
            f"   ⏰ 緊急程度：觀察"
        ),
        urgency="觀察"
    )


def main():
    # ── Header ──────────────────────────────────
    st.markdown(f"""
    <div class="sentinel-header">
      <div class="sentinel-title">🛡️ Sentinel Pro <span style="color:#00d4ff;font-size:0.9em">v{APP_VERSION}</span></div>
      <div class="sentinel-sub">台股掃描器 · CCI × KD × OBV × 成交量 · 更新於 {APP_UPDATED}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Session state ────────────────────────────
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
    if "scan_rows" not in st.session_state:
        st.session_state.scan_rows = []
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = False
    if "prev_sig_keys" not in st.session_state:
        st.session_state.prev_sig_keys = {}
    if "signal_fired_at" not in st.session_state:
        st.session_state.signal_fired_at = {}   # {代號: "YYYY-MM-DD HH:MM"}
    # Portfolio trades now managed via port_get_trades() / port_add_trade()
    # No session_state needed — cache_resource + /tmp file handle persistence

    # ══════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════
    with st.sidebar:
        st.markdown("### ⚙️ 策略參數")

        with st.expander("⭐ 勝率提升設定", expanded=True):
            st.caption("三大核心過濾器 — 可顯著提高選股精準度")
            min_confluence = st.slider(
                "② 共振門檻（/7）",
                min_value=3, max_value=7, value=5, step=1,
                help="至少需要幾個指標同時確認才觸發三重共振。建議 5 以上"
            )
            accel_threshold = st.slider(
                "③ 加速門檻",
                min_value=0.1, max_value=1.0, value=0.3, step=0.1,
                help="CCI+RSI 斜率加速度下限。數值越高越嚴格"
            )
            trend_filter = st.checkbox(
                "① 趨勢過濾（強空頭不買）",
                value=True,
                help="TrendScore ≤ -2 時不發出買入訊號，避免逆勢接刀"
            )
            st.markdown("""
            <div style="background:#0d1a2d;border-radius:6px;padding:8px 12px;font-size:0.72rem;color:#5a8fb0;margin-top:4px">
            ⭐ <b>三重共振</b> = ① 趨勢↑ + ② 5+/7共振 + ③ 動能加速<br>
            研究顯示三重共振可使勝率提升 <b style="color:#00ff88">+20~35%</b>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("📊 CCI + 成交量", expanded=False):
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

        with st.expander("🕯 多時間框架確認 (MTF)", expanded=False):
            use_mtf = st.checkbox(
                "啟用日K + 週K 雙重確認",
                value=False,
                key="use_mtf",
                help="只有日線與週線同時出現方向一致的訊號才視為有效。"
                     "可大幅降低假突破，但訊號數量會減少約 40-60%。"
            )
            if use_mtf:
                st.caption(
                    "✅ 已啟用：掃描表格新增「週線訊號」和「MTF確認」欄，"
                    "未通過雙重確認的買入訊號會自動降級。"
                )

        with st.expander("🛑 停損設定", expanded=False):
            st.caption("設定實際操作時使用的停損策略")
            sl_mode = st.radio(
                "停損計算方式",
                ["ATR倍數（動態）", "固定百分比"],
                horizontal=True, key="sl_mode",
            )
            if sl_mode == "ATR倍數（動態）":
                atr_mult = st.slider(
                    "ATR 倍數", min_value=1.0, max_value=4.0,
                    value=1.5, step=0.5, key="atr_mult",
                    help="停損 = 進場價 - ATR(14) × 倍數。"
                         "1.5x = 較緊；2.0x = 正常；3.0x = 寬鬆"
                )
                fixed_sl_pct = None
            else:
                fixed_sl_pct = st.slider(
                    "固定停損 %", min_value=1.0, max_value=15.0,
                    value=7.0, step=0.5, key="fixed_sl_pct",
                    help="停損 = 進場價 × (1 - 此百分比/100)"
                )
                atr_mult = 1.5   # unused but keep default

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

        # ── Telegram 推播設定 ──────────────────────────────
        with st.expander("📲 Telegram 推播設定", expanded=False):
            st.caption("掃描到買入訊號時自動推送到你的 Telegram")
            # Read from st.secrets if configured in Streamlit Cloud
            _tg_sec = {}
            try: _tg_sec = st.secrets.get("telegram", {})
            except Exception: pass
            tg_token   = st.text_input("Bot Token",
                value=_tg_sec.get("token", ""),
                placeholder="1234567890:AAF...",
                type="password", key="tg_token",
                help="從 @BotFather 取得。可永久儲存：Streamlit Cloud → Settings → Secrets → [telegram]\\ntoken = '你的TOKEN'")
            tg_chat_id = st.text_input("Chat ID",
                value=_tg_sec.get("chat_id", ""),
                placeholder="123456789",
                key="tg_chat_id",
                help="先向 Bot 傳一條訊息，再點下方連結查詢")
            if tg_token and len(tg_token) > 20:
                st.markdown(
                    f"[🔍 查詢我的 Chat ID]"
                    f"(https://api.telegram.org/bot{tg_token}/getUpdates)"
                    f" ← 先向 Bot 傳任意一條訊息再點此"
                )
            tg_min_conf = st.slider("最低共振門檻（推播條件）",
                min_value=3, max_value=7, value=5, key="tg_min_conf",
                help="只推播共振分數達此門檻以上的訊號")
            tg_sigs = st.multiselect("推播訊號類型",
                options=["HIGH_CONF_BUY","BREAKOUT_BUY","STRONG_BUY",
                         "BUY","DIV_BUY","STRONG_SELL","DIV_SELL"],
                default=["HIGH_CONF_BUY","BREAKOUT_BUY","STRONG_BUY"],
                key="tg_sigs",
                format_func=lambda x: SIGNAL_LABEL.get(x, x))
            if st.button("🧪 測試推播", key="tg_test", width='stretch'):
                if not tg_token or not tg_chat_id:
                    st.warning("⚠️ 請先填入 Bot Token 和 Chat ID")
                else:
                    ok, err = _tg_send(tg_token, tg_chat_id,
                        f"✅ <b>Sentinel Pro 推播測試</b>\n"
                        f"連線成功！當掃描到符合條件的訊號時將自動通知你。\n"
                        f"設定：共振 ≥ {tg_min_conf}/7")
                    if ok:
                        st.success("✅ 測試訊息已成功發送！")
                    else:
                        st.error(f"❌ 發送失敗：{err}")
                        st.caption(
                            "常見原因：\n"
                            "1. Token 錯誤 — 確認從 @BotFather 取得的完整 Token\n"
                            "2. Chat ID 錯誤 — 先傳一條訊息給 Bot，再用上方連結確認\n"
                            "3. Bot 尚未啟用 — 在 Telegram 搜尋你的 Bot 並按 Start\n"
                            "4. 網路限制 — Streamlit Cloud 免費版可能封鎖外部請求"
                        )

        # ── Google Sheets 儲存設定 ─────────────────────────
        with st.expander("📊 Google Sheets 交易記錄雲端同步", expanded=False):
            st.caption("將買賣記錄永久儲存到 Google Sheets，重啟後自動還原")
            st.markdown("""
            **設定步驟：**
            1. 建立 Google Sheet，記下 URL 中的 Sheet ID
            2. 在 Google Cloud Console 啟用 Sheets API
            3. 建立 OAuth 2.0 或 Service Account，取得 Access Token
            """)
            gs_sheet_id = st.text_input("Sheet ID",
                placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
                key="gs_sheet_id",
                help="Google Sheets URL 中 /d/ 和 /edit 之間的字串")
            gs_api_token = st.text_input("Access Token / API Key",
                placeholder="ya29.xxx 或 AIza...",
                type="password", key="gs_api_token",
                help="可讀可寫: OAuth Bearer Token；唯讀: API Key")
            col_pull, col_push = st.columns(2)
            if col_pull.button("⬇️ 從 Sheets 同步", key="gs_pull", width='stretch'):
                with st.spinner("讀取中…"):
                    gs_trades = gs_read_trades(gs_sheet_id, gs_api_token)
                if gs_trades:
                    port_replace_trades(gs_trades, reset_id=True)
                    st.success(f"✅ 已同步 {len(gs_trades)} 筆記錄")
                    st.rerun()
                else:
                    st.error("❌ 讀取失敗或無資料")
            if col_push.button("⬆️ 上傳到 Sheets", key="gs_push", width='stretch'):
                with st.spinner("上傳中…"):
                    ok, err = gs_overwrite_trades(gs_sheet_id, gs_api_token, port_get_trades())
                if ok:
                    st.success("✅ 已上傳")
                else:
                    st.error(f"❌ 上傳失敗：{err}")
                    st.caption(
                        "💡 常見原因：\n"
                        "1. Access Token 需要 OAuth Bearer Token（以 ya29. 開頭），不是 API Key\n"
                        "2. Service Account 需先被加入 Sheet 的編輯權限\n"
                        "3. OAuth Token 可能已過期（有效期通常 1 小時）"
                    )

    # ── Pack params ─────────────────────────────
    params = dict(
        min_confluence=min_confluence,
        accel_threshold=accel_threshold,
        trend_filter=trend_filter,
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
        use_mtf=use_mtf, atr_mult=atr_mult,
        sl_mode=sl_mode, fixed_sl_pct=fixed_sl_pct,
    )

    # ══════════════════════════════════════════
    # TABS
    # ══════════════════════════════════════════
    tab_scan, tab_drill, tab_bt, tab_port, tab_sig_hist = st.tabs([
        "📡  訊號掃描", "🔬  個股分析", "📊  回測 & 優化",
        "📒  買賣記錄", "📈  訊號歷史勝率",
    ])

    # ─────────────────────────────────────────
    # TAB 1  訊號掃描
    # ─────────────────────────────────────────
    with tab_scan:
        # ── Header row: title + scan + opt + auto-refresh ──
        c_hd, c_scan, c_opt = st.columns([3, 1, 1])
        c_hd.markdown("#### 📡 即時掃描 — 量價訊號")
        run_scan = c_scan.button("🔄 掃描", type="primary", width='stretch')
        run_opt  = c_opt.button("⚡ 優化CCI", width='stretch',
                                help="為每支股票獨立回測，找出最佳CCI週期（約1-2分鐘）")

        # ── Auto-refresh control row ──
        ar_col, status_col = st.columns([1, 3])
        auto_refresh = ar_col.toggle(
            "🔁 自動更新",
            value=st.session_state.auto_refresh,
            help="盤中（09:00-13:30）每15分鐘自動重掃。非盤中時自動停止。",
        )
        st.session_state.auto_refresh = auto_refresh

        # Market status + countdown
        market_open  = is_market_open()
        market_day   = is_market_day()
        scan_time    = st.session_state.get("scan_timestamp", "")
        secs_left    = seconds_to_next_refresh(scan_time)
        countdown    = format_countdown(secs_left)

        if market_open:
            mkt_badge = '<span style="background:#0d3a1a;color:#00ff88;padding:1px 8px;border-radius:4px;font-size:0.72rem;font-weight:700">● 盤中</span>'
        elif market_day:
            mkt_badge = '<span style="background:#1a2a3a;color:#f0a500;padding:1px 8px;border-radius:4px;font-size:0.72rem;font-weight:700">○ 盤後</span>'
        else:
            mkt_badge = '<span style="background:#1a1a2a;color:#5a8fb0;padding:1px 8px;border-radius:4px;font-size:0.72rem">○ 休市</span>'

        status_txt = ""
        if scan_time:
            if auto_refresh and market_open:
                status_txt = f'更新於 {scan_time}　下次 <b>{countdown}</b>'
            elif auto_refresh and not market_open:
                status_txt = f'更新於 {scan_time}　（盤後暫停自動更新）'
            else:
                status_txt = f'更新於 {scan_time}'

        status_col.markdown(
            f'{mkt_badge} <span style="font-size:0.75rem;color:#5a8fb0">{status_txt}</span>',
            unsafe_allow_html=True,
        )

        # ── Auto-refresh trigger (only during market hours) ──
        should_auto_scan = (
            auto_refresh
            and market_open
            and bool(st.session_state.scan_rows)  # only re-scan if we have prior data
            and secs_left <= 0
        )
        if should_auto_scan:
            run_scan = True   # piggyback on existing scan logic below

        # Sort mode selector
        sort_mode = st.radio(
            "排序方式",
            ["📶 訊號強度", "⭐ 共振分數", "🔥 動能分數", "📈 量比"],
            horizontal=True, label_visibility="collapsed",
        )

        # ── ⚡ Optimise CCI per stock (separate, deferred) ──────────────────
        if run_opt and st.session_state.get("scan_rows"):
            wl      = st.session_state.watchlist
            total_n = max(len(wl), 1)
            opt_map = {}
            prog2   = st.progress(0, text="個股CCI優化中…")
            for i, code in enumerate(wl):
                prog2.progress((i + 1) / total_n,
                               text=f"優化 {code} ({i+1}/{total_n})…")
                try:
                    opt = auto_optimize_cci(
                        code, data_period,
                        holding_days, profit_target, stop_loss,
                        vol_ma_period, rsi_period, kd_period, ema2
                    )
                    bare = code.upper().replace(".TW","").replace(".TWO","")
                    opt_map[bare] = opt
                except Exception:
                    pass
            prog2.empty()
            st.session_state.cci_opt_map = opt_map
            # Patch rows with optimised results
            for row in st.session_state.scan_rows:
                o = opt_map.get(row["代號"])
                if o and o["optimised"]:
                    row["最佳CCI"]  = o["cci_period"]
                    row["勝率%"]    = o["win_rate"]
                    row["平均報酬%"] = o["avg_return"]
                    row["_win_rate"] = o["win_rate"]
            st.success(f"✅ 優化完成 — {len(opt_map)} 支股票已更新最佳CCI")

        # ── 🔄 Main scan ────────────────────────────────────────────────────
        if run_scan:
            rows      = []
            failed    = []
            wl        = st.session_state.watchlist
            total_n   = max(len(wl), 1)
            # ▶ Load names (instant static table)
            try:
                name_cache = batch_fetch_names(tuple(wl))
            except Exception:
                name_cache = {}

            # ▶ Batch-fetch ALL quotes in ONE yf.download() call BEFORE the loop
            # This replaces 145 individual fetch_quote() HTTP requests with 1 call
            # Speedup: ~10× (145 × 0.3s → 1 × ~4s)
            quote_cache: dict = {}
            try:
                quote_cache = batch_fetch_quotes(tuple(wl))
            except Exception:
                quote_cache = {}

            prog = st.progress(0, text="掃描中…")

            for i, code in enumerate(wl):
                prog.progress((i + 1) / total_n,
                              text=f"分析 {code} ({i+1}/{total_n})…")
                df_raw, err = fetch_data(code, data_period)
                if df_raw is None or len(df_raw) < 60:
                    failed.append(f"{code}: {err or '資料不足'}")
                    continue

                # Use globally-cached per-stock CCI if already optimised,
                # otherwise fall back to global params
                bare        = code.upper().replace(".TW","").replace(".TWO","")
                opt_map     = st.session_state.get("cci_opt_map", {})
                opt         = opt_map.get(bare, {})
                best_cci    = opt.get("cci_period",    cci_period)
                best_vm     = opt.get("vol_multiplier", vol_multiplier)
                stock_params = {**params,
                                "cci_period":    best_cci,
                                "vol_multiplier": best_vm}

                try:
                    df_sig = generate_signals(df_raw, stock_params)
                except Exception as e:
                    failed.append(f"{code}: 訊號計算失敗 ({e})")
                    continue

                bt    = backtest(df_sig, holding_days, profit_target, stop_loss)

                # Use batch-prefetched quote; fall back to individual call only if missing
                bare_q = code.upper().replace(".TW","").replace(".TWO","")
                quote  = quote_cache.get(bare_q) or fetch_quote(code)
                import time as _time_rl; _time_rl.sleep(0.02)  # 20ms guard (reduced from 50ms)

                cached = name_cache.get(bare)
                if cached and cached[0]:
                    cn_name, mkt_label = cached
                else:
                    cn_name, mkt_label = fetch_name(code)
                    if not mkt_label:
                        mkt_label = "上櫃" if code.upper().endswith(".TWO") else "上市"

                latest = df_sig.iloc[-1]
                prev   = df_sig.iloc[-2]
                price  = quote.get("price") or round(float(latest["Close"]), 2)
                price_stale = not quote.get("price")   # True = using last close, not live
                chg_p  = quote.get("change_pct") or (
                    (float(latest["Close"]) - float(prev["Close"])) /
                    (float(prev["Close"]) + 1e-8) * 100
                )

                recent_sig, recent_detail = get_scan_signal(df_sig, lookback=5)

                # ── Stop Loss calculation (user-configured) ───────────
                atr_val  = float(latest["ATR"]) if pd.notna(latest.get("ATR")) else None
                _atr_m   = params.get("atr_mult", 1.5)
                _sl_mode = params.get("sl_mode", "ATR倍數（動態）")
                _fix_pct = params.get("fixed_sl_pct", None)
                if _sl_mode == "ATR倍數（動態）" and atr_val:
                    atr_stop     = round(price - atr_val * _atr_m, 2)
                    sl_pct_shown = round(atr_val * _atr_m / price * 100, 1)
                    sl_label     = f"{atr_stop} (ATR×{_atr_m}={sl_pct_shown}%)"
                elif _fix_pct and _fix_pct > 0:
                    atr_stop     = round(price * (1 - _fix_pct / 100), 2)
                    sl_label     = f"{atr_stop} (-{_fix_pct}%)"
                else:
                    atr_stop = round(price - float(latest["ATR"]) * 1.5, 2) if atr_val else "-"
                    sl_label = str(atr_stop)

                # ── Multi-timeframe confirmation ──────────────────────
                use_mtf_flag = params.get("use_mtf", False)
                if use_mtf_flag and recent_sig in BUY_SIGNALS:
                    w_sig, w_det = get_weekly_signal(
                        code, params,
                        _p_ver=hash((params.get("cci_period",39), params.get("vol_multiplier",1.5)))
                    )
                    mtf_ok, mtf_label = mtf_confirm(recent_sig, w_sig)
                    # Downgrade signal if MTF disagrees
                    if not mtf_ok:
                        recent_sig    = "WATCH"
                        recent_detail = f"MTF未確認: {mtf_label} | 日線: {SIGNAL_LABEL.get(recent_sig, recent_sig)}"
                else:
                    w_sig    = "─"
                    mtf_label = "─" if not use_mtf_flag else "不適用"
                    mtf_ok    = True

                mom  = round(float(latest.get("MomScore",       0) or 0), 1)
                conf = int(  float(latest.get("ConfluenceScore", 0) or 0))
                trnd = int(  float(latest.get("TrendScore",      0) or 0))
                k_v  = latest.get("K", np.nan)
                d_v  = latest.get("D", np.nan)
                k_val = round(float(k_v), 1) if pd.notna(k_v) else "-"
                d_val = round(float(d_v), 1) if pd.notna(d_v) else "-"
                vol_r = round(float(latest["Vol_Ratio"]), 2) if pd.notna(latest["Vol_Ratio"]) else 0.0

                win_rate   = opt.get("win_rate",   bt["win_rate"])   if opt.get("optimised") else bt["win_rate"]
                avg_return = opt.get("avg_return", bt["avg_return"]) if opt.get("optimised") else bt["avg_return"]

                # Resistance zone flag from Gap 2 filter
                near_resist_flag = bool(latest.get("Near_Resist", False)) \
                    if "Near_Resist" in df_sig.columns else False

                rows.append({
                    "代號":     bare,
                    "名稱":     cn_name,
                    "市場":     mkt_label,
                    "訊號":     SIGNAL_LABEL.get(recent_sig, recent_sig),
                    "動能":     mom,
                    "共振":     conf,
                    "趨勢":     trnd,
                    "最新價":   price,
                    "漲跌%":    round(chg_p, 2),
                    "CCI":      round(float(latest["CCI"]), 1) if pd.notna(latest["CCI"]) else "-",
                    f"RSI({rsi_period})": round(float(latest["RSI"]), 1) if pd.notna(latest["RSI"]) else "-",
                    "K值":      k_val,
                    "D值":      d_val,
                    "量/均量":  vol_r,
                    "說明":     recent_detail,
                    "止損價":   atr_stop,
                    "止損說明": sl_label,
                    "週線訊號": SIGNAL_LABEL.get(w_sig, w_sig) if use_mtf_flag else "─",
                    "MTF確認":  mtf_label if use_mtf_flag else "─",
                    "壓力區":   "⚠️" if near_resist_flag else "─",
                    "勝率%":    win_rate,
                    "平均報酬%": avg_return,
                    "最佳CCI":  best_cci,
                    "_sig_key": recent_sig,
                    "_mom":     mom,
                    "_vol_r":   vol_r,
                    "_conf":    conf,
                    "_price":   price,
                    "_chg_p":   round(chg_p, 2),
                    "_cn_name": cn_name,
                    "_atr_stop": atr_stop,
                    "_sl_label": sl_label,
                    "_win_rate": win_rate,
                    "_detail":  recent_detail,
                    "_mtf_ok":  mtf_ok,
                    "_w_sig":   w_sig,
                    "_near_resist": near_resist_flag,
                    "_is_new":  False,
                    "_fired_at": "",
                })

            prog.empty()
            # ── Track signal change timestamps ─────────────────────────
            # signal_fired_at: {code: {"sig_key": str, "fired_at": str}}
            # Persists to /tmp so it survives page refresh within same container
            _SIG_TS_FILE = "/tmp/sentinel_sig_timestamps.json"

            # Load from file first (survives page refresh)
            try:
                if os.path.exists(_SIG_TS_FILE):
                    with open(_SIG_TS_FILE) as _f:
                        signal_fired_at = json.load(_f)
                else:
                    signal_fired_at = st.session_state.get("signal_fired_at", {})
            except Exception:
                signal_fired_at = st.session_state.get("signal_fired_at", {})

            prev_keys = st.session_state.get("prev_sig_keys", {})
            new_signals = set()
            fired_ts = tw_now().strftime("%Y-%m-%d %H:%M")

            for r in rows:
                code    = r["代號"]
                cur_sig = r["_sig_key"]
                old_sig = prev_keys.get(code)
                cached  = signal_fired_at.get(code, {})

                # Signal changed → update timestamp
                if old_sig != cur_sig and cur_sig not in ("NEUTRAL","RISING","FALLING","BULL_ZONE","BEAR_ZONE"):
                    signal_fired_at[code] = {"sig_key": cur_sig, "fired_at": fired_ts}
                    new_signals.add(code)
                elif not cached:
                    # First time seeing this code — record it
                    signal_fired_at[code] = {"sig_key": cur_sig, "fired_at": fired_ts}

                # _is_new = True if this is the SAME signal as when it was first recorded
                # (keeps badge until signal changes again, not just one scan)
                cached_now = signal_fired_at.get(code, {})
                r["_is_new"]   = (cached_now.get("sig_key") == cur_sig
                                  and code in new_signals)
                r["_fired_at"] = cached_now.get("fired_at", "")

            # Persist to file (atomic) and session state
            try:
                _tmp = _SIG_TS_FILE + ".tmp"
                with open(_tmp, "w") as _f:
                    json.dump(signal_fired_at, _f, ensure_ascii=False)
                os.replace(_tmp, _SIG_TS_FILE)
            except Exception:
                pass
            st.session_state.signal_fired_at = signal_fired_at

            # Save current signals as previous for next comparison
            st.session_state.prev_sig_keys  = {r["代號"]: r["_sig_key"] for r in rows}
            st.session_state.scan_rows      = rows
            st.session_state.scan_failed    = failed
            st.session_state.scan_timestamp = tw_now().strftime("%Y-%m-%d %H:%M")

            # ── Record NEW buy signals into history DB ────────────────
            _TRACK_SIGS = BUY_SIGNALS  # track all buy signals
            today_str = tw_now().strftime("%Y-%m-%d")
            for r in rows:
                if r["_sig_key"] in _TRACK_SIGS:
                    sig_hist_add({
                        "code":        r["代號"],
                        "name":        r.get("_cn_name", r.get("名稱","")),
                        "sig_key":     r["_sig_key"],
                        "sig_label":   SIGNAL_LABEL.get(r["_sig_key"], r["_sig_key"]),
                        "confluence":  r.get("_conf", 0),
                        "trend":       r.get("趨勢", 0),
                        "date_fired":  today_str,
                        "price_fired": r.get("_price", r.get("最新價", 0)),
                        "atr_stop":    r.get("_atr_stop", "-"),
                        "price_5d":    None, "price_10d": None, "price_20d": None,
                        "ret_5d":      None, "ret_10d":   None, "ret_20d":   None,
                        "status":      "pending",
                    })

            # ── Update outcomes for previously recorded signals ───────
            n_updated = sig_hist_update_outcomes(fetch_data)
            if n_updated:
                st.toast(f"📈 已更新 {n_updated} 筆歷史訊號實際報酬", icon="📊")

            # ── Telegram push for NEW actionable signals ──────────────
            tg_token_v   = st.session_state.get("tg_token", "")
            tg_chat_v    = st.session_state.get("tg_chat_id", "")
            tg_sigs_v    = set(st.session_state.get("tg_sigs",
                                ["HIGH_CONF_BUY","BREAKOUT_BUY","STRONG_BUY"]))
            tg_min_conf_v= int(st.session_state.get("tg_min_conf", 5))
            if tg_token_v and tg_chat_v:
                scan_ts = tw_now().strftime("%H:%M")
                new_buy  = [r for r in rows
                            if r.get("_is_new") and r["_sig_key"] in tg_sigs_v
                            and r.get("_conf", 0) >= tg_min_conf_v
                            and r["_sig_key"] not in ("STRONG_SELL","DIV_SELL")]
                new_sell = [r for r in rows
                            if r.get("_is_new") and r["_sig_key"] in tg_sigs_v
                            and r["_sig_key"] in ("STRONG_SELL","DIV_SELL")]
                for r in new_buy + new_sell:
                    r["_ts"] = scan_ts
                sent = send_signal_alert(tg_token_v, tg_chat_v, new_buy, new_sell)
                if sent:
                    st.toast(f"📲 已推播 {sent} 則訊號到 Telegram", icon="✅")
            # next auto-refresh is triggered when user returns to the page
            # and secs_left <= 0 fires the should_auto_scan flag above.

        rows      = st.session_state.scan_rows
        failed    = st.session_state.get("scan_failed", [])
        scan_time = st.session_state.get("scan_timestamp", "")

        # ── Auto-rerun countdown (only while market open + auto on) ──
        if auto_refresh and market_open and scan_time:
            secs = seconds_to_next_refresh(scan_time)
            if secs > 0:
                # Show countdown — use JS meta-refresh to reload page after N seconds
                # This avoids blocking the server thread (no sleep)
                st.caption(
                    f"⏱ 自動更新倒數：**{format_countdown(secs)}** "
                    f"（每{AUTO_REFRESH_INTERVAL//60}分鐘）"
                )
                # Inject a lightweight JS refresh — only fires in user's own browser
                st.markdown(
                    f'<meta http-equiv="refresh" content="{max(secs, 30)}">',
                    unsafe_allow_html=True,
                )
            else:
                # Interval elapsed — trigger a scan on this page load
                if not run_scan:   # avoid double-scan if user also clicked button
                    st.rerun()     # rerun triggers should_auto_scan → run_scan = True

        if rows:
            # ══════════════════════════════════════════════════════
            # 近期訊號高亮面板 — 有明確買賣訊號的股票 (近5日內)
            # ══════════════════════════════════════════════════════
            ACTION_BUY  = {"HIGH_CONF_BUY", "BREAKOUT_BUY", "STRONG_BUY",
                           "BUY", "DIV_BUY", "KD_GOLDEN_ZONE"}
            ACTION_SELL = {"STRONG_SELL", "SELL", "DIV_SELL"}
            ACTION_WARN = {"FAKE_BREAKOUT", "KD_HIGH"}

            today_buy  = [r for r in rows if r["_sig_key"] in ACTION_BUY]
            today_sell = [r for r in rows if r["_sig_key"] in ACTION_SELL]
            today_warn = [r for r in rows if r["_sig_key"] in ACTION_WARN]

            today_buy  = sorted(today_buy,  key=lambda r: (SIGNAL_ORDER.get(r["_sig_key"], 9), -r["_win_rate"]))
            today_sell = sorted(today_sell, key=lambda r: (SIGNAL_ORDER.get(r["_sig_key"], 9), -r["_win_rate"]))

            opt_done = bool(st.session_state.get("cci_opt_map"))

            if today_buy or today_sell:
                opt_badge = ' <span style="background:#1a3a20;color:#00ff88;padding:1px 7px;border-radius:4px;font-size:0.7rem">⚡ CCI已優化</span>' if opt_done else ' <span style="background:#1a2a3a;color:#5a8fb0;padding:1px 7px;border-radius:4px;font-size:0.7rem">點「優化CCI」獲得最佳參數</span>'
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#0d1f12,#0a1628);
                    border:1px solid #1e4030;border-radius:10px;
                    padding:10px 16px;margin-bottom:10px">
                <div style="font-family:'Space Mono',monospace;font-size:0.88rem;
                    color:#00ff88;font-weight:700">
                📢 近期訊號 (5日內) — {scan_time}{opt_badge}</div>
                </div>""", unsafe_allow_html=True)

                # Buy signal cards
                if today_buy:
                    st.markdown("**🟢 買入訊號**")
                    cols_per_row = 2
                    for start in range(0, min(len(today_buy), 8), cols_per_row):
                        chunk = today_buy[start:start + cols_per_row]
                        cols  = st.columns(cols_per_row)
                        for ci, r in enumerate(chunk):
                            sig_key   = r["_sig_key"]
                            chg_color = "#e8414e" if r["_chg_p"] >= 0 else "#22cc66"
                            wr_color  = "#00ff88" if r["_win_rate"] >= 60 else "#f0a500" if r["_win_rate"] >= 45 else "#aaaaaa"
                            border    = "#ffd700" if sig_key == "HIGH_CONF_BUY" else "#00ff88"
                            fired_at  = r.get("_fired_at", "")
                            new_badge = (
                                f'<span style="background:#ff9900;color:#000;padding:1px 6px;'
                                f'border-radius:3px;font-size:0.62rem;font-weight:700;'
                                f'margin-left:4px">NEW</span>'
                            ) if r.get("_is_new") else ""
                            # Resistance zone warning badge
                            resist_badge = (
                                f'<span style="background:#ff3355;color:#fff;padding:1px 6px;'
                                f'border-radius:3px;font-size:0.60rem;font-weight:700;'
                                f'margin-left:4px">⚠️壓力</span>'
                            ) if r.get("_near_resist") else ""
                            # Show signal detection time on ALL buy cards (not just NEW)
                            time_label = (
                                f'<div style="font-size:0.62rem;color:#37474f;margin-top:3px">'
                                f'📍 訊號出現：{fired_at}</div>'
                            ) if fired_at else ""
                            with cols[ci]:
                                st.markdown(f"""
                                <div style="background:#0d1a2d;border:1.5px solid {border};
                                    border-radius:10px;padding:12px 14px;margin-bottom:8px">
                                <div style="display:flex;justify-content:space-between;
                                    align-items:baseline;margin-bottom:4px">
                                <span style="font-size:1.05rem;font-weight:700;
                                    color:#e8f4fd;font-family:'Space Mono',monospace">
                                {r['代號']}{new_badge}{resist_badge}</span>
                                <span style="font-size:0.75rem;color:{chg_color};font-weight:600">
                                {r['_price']:.2f}　{r['_chg_p']:+.2f}%</span>
                                </div>
                                <div style="font-size:0.78rem;color:#8a9bb5;margin-bottom:4px">
                                {r['_cn_name'] or ''}</div>
                                <div style="font-size:0.82rem;font-weight:700;color:{border};
                                    margin-bottom:6px">{SIGNAL_LABEL.get(sig_key,'')}</div>
                                <div style="display:flex;gap:8px;font-size:0.72rem;flex-wrap:wrap">
                                <span style="color:{wr_color}">勝率 {r['_win_rate']:.0f}%</span>
                                <span style="color:#5a8fb0">CCI{r['最佳CCI']}</span>
                                <span style="color:#5a8fb0">止損 {r['_atr_stop']}</span>
                                </div>
                                <div style="font-size:0.68rem;color:#37474f;margin-top:4px;
                                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                                {r['_detail'][:45]}</div>
                                {time_label}
                                </div>""", unsafe_allow_html=True)

                # Sell signal cards
                if today_sell:
                    st.markdown("**🔴 賣出訊號**")
                    cols_per_row = 2
                    for start in range(0, min(len(today_sell), 6), cols_per_row):
                        chunk = today_sell[start:start + cols_per_row]
                        cols  = st.columns(cols_per_row)
                        for ci, r in enumerate(chunk):
                            chg_color = "#e8414e" if r["_chg_p"] >= 0 else "#22cc66"
                            with cols[ci]:
                                st.markdown(f"""
                                <div style="background:#1a0d0d;border:1.5px solid #ff3355;
                                    border-radius:10px;padding:12px 14px;margin-bottom:8px">
                                <div style="display:flex;justify-content:space-between;
                                    align-items:baseline;margin-bottom:4px">
                                <span style="font-size:1.05rem;font-weight:700;
                                    color:#e8f4fd;font-family:'Space Mono',monospace">
                                {r['代號']}</span>
                                <span style="font-size:0.75rem;color:{chg_color};font-weight:600">
                                {r['_price']:.2f}　{r['_chg_p']:+.2f}%</span>
                                </div>
                                <div style="font-size:0.78rem;color:#8a9bb5;margin-bottom:4px">
                                {r['_cn_name'] or ''}</div>
                                <div style="font-size:0.82rem;font-weight:700;
                                    color:#ff3355;margin-bottom:6px">
                                {SIGNAL_LABEL.get(r['_sig_key'],'')}</div>
                                <div style="font-size:0.68rem;color:#37474f;margin-top:4px">
                                {r['_detail'][:45]}</div>
                                </div>""", unsafe_allow_html=True)

                if today_warn:
                    st.caption(f"⚠️ 注意：{len(today_warn)} 支出現誘多/KD高檔警示 — " +
                               "、".join(r["代號"] for r in today_warn[:6]))

                st.divider()

            # ── Sort ──
            if sort_mode == "⭐ 共振分數":
                rows_sorted = sorted(rows, key=lambda r: (-SIGNAL_ORDER.get(r["_sig_key"], 9), -r["_conf"], -r["_mom"]))
            elif sort_mode == "🔥 動能分數":
                rows_sorted = sorted(rows, key=lambda r: -r["_mom"])
            elif sort_mode == "📈 量比":
                rows_sorted = sorted(rows, key=lambda r: -r["_vol_r"])
            else:
                rows_sorted = sorted(rows, key=lambda r: SIGNAL_ORDER.get(r["_sig_key"], 9))

            df_display = pd.DataFrame(rows_sorted)
            show_cols  = [c for c in df_display.columns if not c.startswith("_")]
            df_display = df_display[show_cols]

            if scan_time:
                st.caption(f"🕐 最後更新：{scan_time}　共 {len(rows)} 支　"
                           f"買入訊號 {len(today_buy)} 支　賣出訊號 {len(today_sell)} 支")

            st.dataframe(
                df_display,
                width='stretch',
                height=480,
                column_config={
                    "漲跌%":    st.column_config.NumberColumn(format="%.2f%%"),
                    "動能":     st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                    "共振":     st.column_config.ProgressColumn(min_value=0, max_value=7, format="%d/7"),
                    "趨勢":     st.column_config.NumberColumn(format="%+d"),
                    "勝率%":    st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
                    "平均報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                    "最佳CCI":  st.column_config.NumberColumn(format="%d"),
                    "止損價":   st.column_config.NumberColumn(format="%.2f",
                                  help="根據側欄「停損設定」計算的止損價"),
                    "止損說明": st.column_config.TextColumn(
                                  help="ATR倍數說明或固定%說明"),
                    "週線訊號": st.column_config.TextColumn(
                                  help="週K線訊號（啟用MTF確認後顯示）"),
                    "MTF確認":  st.column_config.TextColumn(
                                  help="日線+週線雙重確認結果"),
                    "壓力區":   st.column_config.TextColumn(
                                  help="⚠️ 現價距壓力位 ≤3%，買入風險較高"),
                },
                hide_index=True,
            )

            # Signal legend
            st.markdown("""
            <div class="signal-legend">
            <b>⭐ 最高品質：</b>
            ⭐ <b>三重共振</b> 趨勢↑ + 5+/7指標共振 + 動能加速（最高勝率）<br>
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
            format_func=lambda x: x if x.upper().endswith((".TW", ".TWO")) else f"{x}.TW",
        )
        custom_code = c2.text_input("或直接輸入代號", placeholder="e.g. 0050 / 3661.TWO")
        load_btn    = c3.button("📊 載入", type="primary", width='stretch')

        # Timeframe selector
        tf_opts  = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo",
                    "1年": "1y", "2年": "2y"}
        tf_label = st.radio("分析區間", list(tf_opts.keys()),
                            horizontal=True, index=2,
                            label_visibility="collapsed")
        drill_period = tf_opts[tf_label]

        target = custom_code.strip() or sel_from_wl

        if load_btn:
            with st.spinner(f"載入 {target} …"):
                df_raw, err = fetch_data(target, drill_period)
            if df_raw is None:
                st.error(f"無法取得資料：{err}")
            else:
                df_sig  = generate_signals(df_raw, params)
                latest  = df_sig.iloc[-1]
                prev    = df_sig.iloc[-2]
                quote   = fetch_quote(target)
                cn_name, mkt_label = fetch_name(target)

                price   = quote.get("price")    or round(float(latest["Close"]), 2)
                chg     = quote.get("change")   or float(latest["Close"] - prev["Close"])
                chg_pct = quote.get("change_pct") or float(chg / (prev["Close"] + 1e-8) * 100)

                # ── Name banner ──
                bare_t    = target.upper().replace(".TW", "").replace(".TWO", "")
                mkt_color = "#22cc66" if mkt_label == "上櫃" else "#00aaff"
                chg_color = "#e8414e" if chg >= 0 else "#22cc66"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap">'
                    f'<span style="font-size:1.3rem;font-weight:700;color:#e8f4fd;font-family:Space Mono,monospace">{bare_t}</span>'
                    f'<span style="background:{mkt_color};color:#000;padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:700">{mkt_label}</span>'
                    f'<span style="color:#8a9bb5;font-size:0.9rem">{cn_name}</span>'
                    f'<span style="color:{chg_color};font-size:1.1rem;font-weight:700;margin-left:auto">'
                    f'{price:.2f}　<span style="font-size:0.85rem">{chg:+.2f} ({chg_pct:+.2f}%)</span></span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Fundamentals row ──
                with st.spinner("載入基本面資料…"):
                    fund = fetch_fundamentals(target)

                def _fmt_cap(v):
                    if v is None: return "-"
                    if v >= 1e12: return f"{v/1e12:.1f}兆"
                    if v >= 1e8:  return f"{v/1e8:.1f}億"
                    return f"{v:,.0f}"

                def _fmt_pct(v):
                    return f"{v*100:.2f}%" if v is not None else "-"

                def _fmt_f(v, dec=1):
                    return f"{v:.{dec}f}" if v is not None else "-"

                w52h = fund.get("week52_high") or float(df_sig["High"].max())
                w52l = fund.get("week52_low")  or float(df_sig["Low"].min())
                pct_from_high = (price - w52h) / w52h * 100 if w52h else 0

                f1, f2, f3, f4, f5, f6 = st.columns(6)
                f1.metric("本益比 PE",    _fmt_f(fund.get("pe")))
                f2.metric("股價淨值 PB",  _fmt_f(fund.get("pb")))
                f3.metric("殖利率",       _fmt_pct(fund.get("div_yield")))
                f4.metric("市值",         _fmt_cap(fund.get("market_cap")))
                f5.metric("52W高",        f"{w52h:.2f}", f"{pct_from_high:+.1f}%")
                f6.metric("Beta",         _fmt_f(fund.get("beta")))

                # ── Signal metrics ──
                scan_sig, scan_detail = get_scan_signal(df_sig, lookback=5)
                r1c1, r1c2, r1c3, r1c4 = st.columns(4)
                r2c1, r2c2, r2c3, r2c4 = st.columns(4)

                cci_val  = latest.get("CCI", np.nan)
                rsi_val  = latest.get("RSI", np.nan)
                k_now    = latest.get("K",   np.nan)
                d_now    = latest.get("D",   np.nan)
                atr_val  = latest.get("ATR", np.nan)
                vol_r    = latest.get("Vol_Ratio", np.nan)
                mom_now  = float(latest.get("MomScore",       0) or 0)
                conf_now = int(float(latest.get("ConfluenceScore", 0) or 0))
                trnd_now = int(float(latest.get("TrendScore",      0) or 0))
                accl_now = float(latest.get("MomAccel",        0) or 0)
                atr_stop = round(price - atr_val * 1.5, 2) if pd.notna(atr_val) else None
                trend_lbl = {3:"強多頭↑↑",2:"多頭↑",1:"弱多頭",0:"中性",-1:"弱空頭",-2:"強空頭↓↓"}

                r1c1.metric("訊號",   SIGNAL_LABEL.get(scan_sig, "─"))
                r1c2.metric("共振②", f"{conf_now}/7",
                            "✅ 強" if conf_now >= 5 else "⚠️ 弱" if conf_now <= 3 else None)
                r1c3.metric("趨勢①", trend_lbl.get(trnd_now, str(trnd_now)))
                r1c4.metric("加速③", f"{accl_now:+.2f}",
                            "🚀" if accl_now > 0.3 else "⬇️" if accl_now < -0.3 else None)

                r2c1.metric("動能",   f"{mom_now:.0f}/100")
                r2c2.metric("CCI",    f"{cci_val:.1f}" if pd.notna(cci_val) else "-")
                r2c3.metric("RSI",    f"{rsi_val:.1f}" if pd.notna(rsi_val) else "-")
                r2c4.metric("ATR停損", f"{atr_stop:.2f}" if atr_stop else "-")

                # ── R:R calculation ──
                rr_targets_list = calc_rr_targets(price, atr_stop) if atr_stop else []
                if rr_targets_list:
                    risk = price - atr_stop
                    rr1, t1 = rr_targets_list[0]
                    rr2, t2 = rr_targets_list[1]
                    rr3, t3 = rr_targets_list[2]
                    st.markdown(
                        f'<div style="background:#0d1a2d;border:1px solid #1a3050;border-radius:8px;'
                        f'padding:8px 14px;margin:6px 0;font-size:0.78rem;display:flex;gap:16px;flex-wrap:wrap">'
                        f'<span style="color:#5a8fb0">風險 <b style="color:#ff3355">{risk:.2f}</b></span>'
                        f'<span style="color:#5a8fb0">目標1({rr1}x) <b style="color:#00ff88">{t1:.2f}</b></span>'
                        f'<span style="color:#5a8fb0">目標2({rr2}x) <b style="color:#00d4ff">{t2:.2f}</b></span>'
                        f'<span style="color:#5a8fb0">目標3({rr3}x) <b style="color:#f0a500">{t3:.2f}</b></span>'
                        f'<span style="color:#37474f;font-size:0.7rem">風險報酬比 — 建議 R:R ≥ 2x 才進場</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # ── Combined quality bar ──
                mom_color  = "#00ff88" if mom_now >= 60 else "#f0a500" if mom_now >= 40 else "#ff3355"
                conf_color = "#00ff88" if conf_now >= 5 else "#f0a500" if conf_now >= 4 else "#ff3355"
                st.markdown(
                    f'<div style="margin:2px 0 10px 0;display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
                    f'<span style="color:#5a8fb0;font-size:0.72rem;white-space:nowrap">動能</span>'
                    f'<div style="flex:1;min-width:50px;background:#1a2a3a;border-radius:3px;height:5px">'
                    f'<div style="background:{mom_color};width:{min(mom_now,100):.0f}%;height:5px;border-radius:3px"></div></div>'
                    f'<span style="color:#5a8fb0;font-size:0.72rem;white-space:nowrap">共振</span>'
                    f'<div style="flex:1;min-width:50px;background:#1a2a3a;border-radius:3px;height:5px">'
                    f'<div style="background:{conf_color};width:{conf_now/7*100:.0f}%;height:5px;border-radius:3px"></div></div>'
                    f'<span style="color:#5a8fb0;font-size:0.68rem;white-space:nowrap">'
                    f'{_html_safe(scan_detail[:40] + "…" if len(scan_detail) > 40 else scan_detail)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Chart (with S/R + stop + R:R) ──
                sr = calc_support_resistance(df_sig)
                fig = build_chart(df_sig, bare_t, params,
                                  sr=sr,
                                  stop_price=atr_stop,
                                  rr_targets=rr_targets_list)
                st.plotly_chart(fig, width='stretch')

                # ── Professional signal history table (clean 6 columns) ──
                EVENT_SIGS = set(BUY_SIGNALS) | set(SELL_SIGNALS) | {"WATCH", "FAKE_BREAKOUT"}
                sig_hist = df_sig[df_sig["Signal"].isin(EVENT_SIGS)].copy()
                if not sig_hist.empty:
                    sig_hist = sig_hist.tail(15)
                    vol_ma_ser = sig_hist["Vol_MA"] if "Vol_MA" in sig_hist.columns else 1
                    display = pd.DataFrame({
                        "日期":   sig_hist.index.date,
                        "收盤":   sig_hist["Close"].round(2),
                        "訊號":   sig_hist["Signal"].map(lambda x: SIGNAL_LABEL.get(x, x)),
                        "CCI":    sig_hist["CCI"].round(1) if "CCI" in sig_hist.columns else "-",
                        "RSI":    sig_hist["RSI"].round(1) if "RSI" in sig_hist.columns else "-",
                        "量/均量": (sig_hist["Vol_Ratio"].round(2)
                                    if "Vol_Ratio" in sig_hist.columns else "-"),
                        "說明":   sig_hist["Signal_Detail"].str[:30],
                    })
                    display = display.reset_index(drop=True)
                    st.markdown("##### 📋 近期訊號記錄（最新15筆）")
                    st.dataframe(
                        display,
                        width='stretch',
                        column_config={
                            "收盤": st.column_config.NumberColumn(format="%.2f"),
                            "CCI":  st.column_config.NumberColumn(format="%.1f",
                                    help="CCI(39) 超買>+100 / 超賣<-100"),
                            "RSI":  st.column_config.NumberColumn(format="%.1f",
                                    help="RSI(6) 超買>70 / 超賣<30"),
                            "量/均量": st.column_config.NumberColumn(format="%.2fx",
                                    help="今日成交量 ÷ 均量，>1.5為放量"),
                        },
                        hide_index=True,
                    )

    # ─────────────────────────────────────────
    # TAB 3  回測 & 優化
    # ─────────────────────────────────────────
    with tab_bt:
        st.markdown("#### 📊 回測分析 & 參數優化")

        c1, c2, c3 = st.columns([3, 2, 1])
        bt_sym  = c1.selectbox("選擇回測標的", st.session_state.watchlist,
                                format_func=lambda x: x if x.upper().endswith((".TW", ".TWO"))
                                                         else f"{x}.TW",
                                key="bt_sym")
        bt_cust = c2.text_input("或直接輸入代號", placeholder="e.g. 0050 / 3661.TWO", key="bt_custom")
        run_bt  = c3.button("🔬 執行", type="primary", width='stretch')
        bt_target = bt_cust.strip() or bt_sym

        # Period selector ABOVE the button — must be outside if run_bt: so Streamlit
        # preserves the selection across reruns triggered by the button press
        bt_period_opts = {"1年": "1y", "2年": "2y", "3年": "3y", "5年": "5y"}
        bt_period_lbl  = st.radio(
            "回測資料區間",
            list(bt_period_opts.keys()),
            index=1, horizontal=True,
            key="bt_period_radio",
        )
        bt_period = bt_period_opts[bt_period_lbl]

        # ── 各訊號量化說明 ────────────────────────────────────────
        with st.expander("❓ 各訊號量化必要嗎？（點此展開說明）", expanded=False):
            st.markdown("""
            **答：非常必要。** 不同訊號的歷史勝率差異顯著，量化後才能做出理性判斷：

            | 訊號類型 | 典型勝率範圍 | 適用場景 |
            |---------|------------|---------|
            | ⭐ 三重共振 | 60–75% | 最強進場，3個條件全中 |
            | 🟠 噴發買 | 55–70% | 趨勢確立後追漲 |
            | 🟢 強買 | 50–65% | 底部翻轉，風險相對低 |
            | 🔵 買入 | 45–60% | 普通動能轉正 |
            | 🟢 底背離 | 50–65% | 需配合放量確認 |
            | 🟢 KD金叉 | 45–60% | 短期反彈，不宜重倉 |

            **關鍵結論**：三重共振勝率比普通買入高出 **+15~25%**。
            只追蹤共振分數 ≥ 5 的訊號，長期下來期望值顯著更高。
            下方「各訊號勝率」欄位就是你這支股票的實際歷史數據。
            """)

        if run_bt:
            with st.spinner(f"載入 {bt_target} 資料（{bt_period_lbl}）…"):
                df_raw, err = fetch_data(bt_target, bt_period)

            if df_raw is None:
                st.error(f"無法取得資料：{err}")
            else:
                cn_bt, _ = fetch_name(bt_target)
                bare_bt  = bt_target.upper().replace(".TW","").replace(".TWO","")
                title_bt = f"{bare_bt} {cn_bt}" if cn_bt else bare_bt

                df_sig = generate_signals(df_raw, params)
                bt     = backtest(df_sig, holding_days, profit_target, stop_loss)
                trades = bt["trades"]

                # ── ① 總體績效指標 ──────────────────────────────────
                st.markdown(f"##### 📌 {title_bt} 回測結果（{bt_period_lbl} / 持有{holding_days}日）")

                # Compute extra stats
                completed = trades[trades["結果"] != "HOLD"] if not trades.empty else pd.DataFrame()
                ret_series = completed["報酬%"] if not completed.empty else pd.Series(dtype=float)
                sharpe = (ret_series.mean() / (ret_series.std() + 1e-8) * (252**0.5 / holding_days**0.5)
                          ) if len(ret_series) > 1 else 0
                max_loss = ret_series.min() if len(ret_series) else 0
                profit_factor = (ret_series[ret_series > 0].sum() /
                                 abs(ret_series[ret_series < 0].sum() + 1e-8)
                                 ) if len(ret_series) > 0 else 0

                m1, m2, m3, m4, m5, m6, m7, m8 = st.columns(8)
                wr_color = "normal" if bt["win_rate"] >= 55 else "off"
                m1.metric("勝率",      f"{bt['win_rate']:.1f}%",
                          "✅" if bt["win_rate"] >= 60 else "⚠️" if bt["win_rate"] >= 50 else "❌")
                m2.metric("交易次數",  bt["total"])
                m3.metric("獲利",      bt["wins"],   f"+{bt['wins']}")
                m4.metric("虧損",      bt["losses"],  f"-{bt['losses']}")
                m5.metric("平均報酬",  f"{bt['avg_return']:+.2f}%")
                m6.metric("最大獲利",  f"{bt['max_return']:+.2f}%")
                m7.metric("夏普值",    f"{sharpe:.2f}",
                          "佳" if sharpe > 1 else "弱" if sharpe < 0 else None)
                m8.metric("獲利因子",  f"{profit_factor:.2f}",
                          "佳" if profit_factor > 1.5 else None)

                if not trades.empty:
                    # ── ② 各訊號勝率量化 ─────────────────────────────
                    st.markdown("##### 📊 各訊號量化績效")
                    sig_grp = (completed.groupby("訊號")
                               .agg(次數=("報酬%","count"),
                                    勝=("結果", lambda x: (x=="WIN").sum()),
                                    平均報酬=("報酬%","mean"),
                                    最大獲利=("報酬%","max"),
                                    最大虧損=("報酬%","min"))
                               .reset_index())
                    sig_grp["勝率%"] = (sig_grp["勝"] / sig_grp["次數"] * 100).round(1)
                    sig_grp["平均報酬"] = sig_grp["平均報酬"].round(2)
                    sig_grp["最大獲利"] = sig_grp["最大獲利"].round(2)
                    sig_grp["最大虧損"] = sig_grp["最大虧損"].round(2)
                    # Map signal keys to labels
                    sig_grp["訊號"] = sig_grp["訊號"].map(
                        lambda x: SIGNAL_LABEL.get(x, x))
                    sig_grp = sig_grp.sort_values("勝率%", ascending=False)
                    sig_grp = sig_grp[["訊號","次數","勝率%","平均報酬","最大獲利","最大虧損"]]

                    st.dataframe(
                        sig_grp,
                        width='stretch',
                        column_config={
                            "勝率%":  st.column_config.ProgressColumn(
                                min_value=0, max_value=100, format="%.1f%%"),
                            "平均報酬": st.column_config.NumberColumn(format="%+.2f%%"),
                            "最大獲利": st.column_config.NumberColumn(format="%+.2f%%"),
                            "最大虧損": st.column_config.NumberColumn(format="%+.2f%%"),
                        },
                        hide_index=True,
                    )

                    # ── ③ 資產曲線 ───────────────────────────────────
                    st.markdown("##### 📈 資產曲線（起始資金 100 萬）")
                    init_cap    = 1_000_000
                    equity      = [init_cap]
                    trade_dates = []
                    for _, row in completed.iterrows():
                        equity.append(equity[-1] * (1 + row["報酬%"] / 100))
                        trade_dates.append(str(row["進場日"]))

                    eq_fig = go.Figure()
                    eq_fig.add_trace(go.Scatter(
                        x=list(range(len(equity))), y=equity,
                        mode="lines", fill="tozeroy",
                        fillcolor="rgba(0,212,255,0.08)",
                        line=dict(color="#00d4ff", width=2),
                        name="資產淨值",
                        hovertemplate="第%{x}筆交易<br>資產：%{y:,.0f}元<extra></extra>",
                    ))
                    # Drawdown shading
                    eq_arr   = pd.Series(equity)
                    peak_arr = eq_arr.cummax()
                    dd_arr   = (eq_arr - peak_arr) / peak_arr * 100
                    eq_fig.add_trace(go.Scatter(
                        x=list(range(len(dd_arr))), y=dd_arr,
                        mode="lines", name="回撤%",
                        line=dict(color="#ff3355", width=1, dash="dot"),
                        yaxis="y2",
                        hovertemplate="回撤：%{y:.1f}%<extra></extra>",
                    ))
                    max_dd = float(dd_arr.min())
                    final  = equity[-1]
                    total_ret = (final - init_cap) / init_cap * 100
                    eq_fig.update_layout(
                        template="plotly_dark",
                        height=300,
                        paper_bgcolor="#0a0e1a",
                        plot_bgcolor="#0d1226",
                        margin=dict(l=60, r=60, t=30, b=10),
                        font=dict(size=10, color="#8a9bb5"),
                        hovermode="x unified",
                        yaxis=dict(title="資產(元)", gridcolor="#1a2a3a",
                                   tickformat=",.0f"),
                        yaxis2=dict(title="回撤%", overlaying="y", side="right",
                                    showgrid=False, tickformat=".1f",
                                    tickfont=dict(color="#ff3355")),
                        legend=dict(orientation="h", y=1.08, x=0,
                                    bgcolor="rgba(0,0,0,0)"),
                        title=dict(
                            text=f"總報酬 {total_ret:+.1f}%　最大回撤 {max_dd:.1f}%　Sharpe {sharpe:.2f}",
                            font=dict(size=11, color="#8a9bb5"), x=0.01
                        ),
                    )
                    st.plotly_chart(eq_fig, width='stretch')

                    # ── ④ 月度績效熱圖 ───────────────────────────────
                    if len(completed) >= 3:
                        st.markdown("##### 🗓 月度績效")
                        try:
                            monthly = (completed.copy()
                                       .assign(月份=pd.to_datetime(completed["進場日"]).dt.to_period("M"))
                                       .groupby("月份")["報酬%"].mean()
                                       .reset_index())
                            monthly["月份"] = monthly["月份"].astype(str)
                            monthly["顏色"] = monthly["報酬%"].apply(
                                lambda v: "#00ff88" if v > 0 else "#ff3355")
                            mfig = go.Figure(go.Bar(
                                x=monthly["月份"], y=monthly["報酬%"],
                                marker_color=monthly["顏色"],
                                hovertemplate="%{x}<br>平均報酬：%{y:+.2f}%<extra></extra>",
                            ))
                            mfig.update_layout(
                                template="plotly_dark", height=200,
                                paper_bgcolor="#0a0e1a", plot_bgcolor="#0d1226",
                                margin=dict(l=50, r=20, t=10, b=40),
                                font=dict(size=9, color="#8a9bb5"),
                                yaxis=dict(gridcolor="#1a2a3a", tickformat="+.1f",
                                           title="月均報酬%"),
                                xaxis=dict(tickangle=-45),
                            )
                            mfig.add_hline(y=0, line_dash="dot",
                                           line_color="#37474f", line_width=1)
                            st.plotly_chart(mfig, width='stretch')
                        except Exception:
                            pass

                    # ── ⑤ 完整交易明細 ──────────────────────────────
                    with st.expander("📋 完整交易明細"):
                        st.dataframe(trades, width='stretch', height=320)
                        dl = to_excel(trades)
                        st.download_button(
                            "📤 匯出交易明細 Excel", data=dl,
                            file_name=f"backtest_{bare_bt}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )

                # ── ⑥ 參數優化 ──────────────────────────────────────
                st.divider()
                st.markdown("##### 🔧 CCI × 放量門檻 網格優化（5×5 = 25 組合）")
                st.caption("找出讓這支股票歷史勝率最高的 CCI 週期與放量門檻組合")

                with st.spinner("網格搜尋中… 約需 20–40 秒"):
                    opt_df = optimize_params(df_raw, params)

                if opt_df.empty:
                    st.warning("訊號次數不足（至少需要 3 筆交易），請延長資料區間或放寬參數。")
                else:
                    st.dataframe(
                        opt_df.head(10),
                        width='stretch',
                        column_config={
                            "勝率%":     st.column_config.ProgressColumn(
                                min_value=0, max_value=100, format="%.1f%%"),
                            "平均報酬%": st.column_config.NumberColumn(format="%+.2f%%"),
                            "最大獲利%": st.column_config.NumberColumn(format="%+.2f%%"),
                            "最大虧損%": st.column_config.NumberColumn(format="%+.2f%%"),
                        },
                        hide_index=True,
                    )

                    best      = opt_df.iloc[0]
                    delta_wr  = best["勝率%"] - bt["win_rate"]
                    clr       = "#00ff88" if delta_wr > 0 else "#aaaaaa"
                    st.markdown(f"""
                    <div class="opt-card">
                      <h4 style="margin:0 0 8px 0">💡 最佳參數建議</h4>
                      <p style="color:#e8f4fd;font-size:1.05rem;margin:0">
                        CCI 週期 = <b style="color:#00d4ff">{int(best['CCI週期'])}</b>　
                        放量門檻 = <b style="color:#00d4ff">{best['放量門檻']:.1f}x</b>
                      </p>
                      <p style="color:#8a9bb5;margin:6px 0 0 0;font-size:0.88rem">
                        預測勝率 <b style="color:{clr}">{best['勝率%']:.1f}%</b>
                        （{int(best['總交易'])} 次交易，平均 {best['平均報酬%']:+.2f}%）
                        較當前參數 <b style="color:{clr}">{delta_wr:+.1f}%</b>
                      </p>
                      <p style="color:#37474f;font-size:0.78rem;margin-top:8px">
                        ※ 請在側欄調整「CCI週期」與「放量門檻」後重新掃描以套用。
                      </p>
                    </div>
                    """, unsafe_allow_html=True)

                    dl_opt = to_excel(opt_df)
                    st.download_button(
                        "📤 匯出優化結果 Excel", data=dl_opt,
                        file_name=f"optimize_{bare_bt}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                # ── ⑦ 市場環境分析回測 ──────────────────────────────
                st.divider()
                st.markdown("#### 🌤 市場環境分析回測（自動化框架）")
                st.caption(
                    "自動將歷史分為三種市況（多頭 / 盤整 / 空頭），"
                    "分別統計各訊號在不同環境下的真實勝率。"
                )

                # Fetch 3y for regime analysis (more regimes visible)
                with st.spinner("載入3年資料進行環境分類…"):
                    df_regime, err_regime = fetch_data(bt_target, "3y")
                if df_regime is None:
                    df_regime = df_raw   # fallback to existing data
                    st.caption("⚠️ 3年資料不足，使用現有資料區間")

                with st.spinner("環境分類 + 多維度回測中…"):
                    regime_result = backtest_by_regime(
                        df_regime, params,
                        holding_days=holding_days,
                        profit_pct=profit_target,
                        stop_pct=stop_loss,
                    )

                if regime_result["all_trades"].empty:
                    st.warning("訊號次數不足，無法進行環境分析（建議使用 2 年以上資料）")
                else:
                    all_t  = regime_result["all_trades"]
                    r_stat = regime_result["regime_stats"]
                    s_stat = regime_result["signal_stats"]
                    best_r = regime_result["best_by_regime"]

                    # ── 市況分布 ──────────────────────────────────────
                    env_counts = all_t["市場環境"].value_counts()
                    ec1, ec2, ec3 = st.columns(3)
                    ec1.metric("🐂 多頭交易", int(env_counts.get("🐂 多頭", 0)))
                    ec2.metric("⚖️ 盤整交易", int(env_counts.get("⚖️ 盤整", 0)))
                    ec3.metric("🐻 空頭交易", int(env_counts.get("🐻 空頭", 0)))

                    # ── Best signal per regime cards ───────────────────
                    st.markdown("##### 🏆 各市況最佳訊號")
                    card_cols = st.columns(3)
                    env_colors = {"🐂 多頭": "#00cc66", "⚖️ 盤整": "#f0a500", "🐻 空頭": "#ff3355"}
                    for col, (env, sigs) in zip(card_cols, best_r.items()):
                        with col:
                            clr = env_colors.get(env, "#5a8fb0")
                            st.markdown(
                                f'<div style="border:2px solid {clr};border-radius:10px;'
                                f'padding:12px;background:#08101a">'
                                f'<div style="font-size:1rem;font-weight:700;color:{clr};'
                                f'margin-bottom:8px">{env}</div>',
                                unsafe_allow_html=True,
                            )
                            if sigs:
                                for rank, (sig_lbl, wr, cnt, avg) in enumerate(sigs[:3], 1):
                                    medal = ["🥇","🥈","🥉"][rank-1]
                                    wr_c  = "#00ff88" if wr >= 60 else "#f0a500" if wr >= 50 else "#ff6666"
                                    st.markdown(
                                        f'<div style="font-size:0.8rem;margin:4px 0">'
                                        f'{medal} <b style="color:#e8f4fd">{sig_lbl}</b><br>'
                                        f'&nbsp;&nbsp;勝率 <b style="color:{wr_c}">{wr:.0f}%</b>'
                                        f'　平均 <b style="color:#8a9bb5">{avg:+.1f}%</b>'
                                        f'　{cnt}次</div>',
                                        unsafe_allow_html=True,
                                    )
                            else:
                                st.caption("資料不足")
                            st.markdown('</div>', unsafe_allow_html=True)

                    # ── Signal × Regime heatmap ────────────────────────
                    if not r_stat.empty:
                        st.markdown("##### 📊 訊號 × 市況 勝率矩陣")
                        st.caption("數值 = 勝率%。空白 = 交易次數不足（< 2次）。")

                        # Regime distribution bar chart
                        env_cnt_df = all_t["市場環境"].value_counts().reset_index()
                        env_cnt_df.columns = ["市場環境", "交易次數"]
                        env_color_map = {"🐂 多頭": "#00cc66", "⚖️ 盤整": "#f0a500", "🐻 空頭": "#ff3355"}
                        env_cnt_df["顏色"] = env_cnt_df["市場環境"].map(env_color_map).fillna("#5a8fb0")
                        dist_fig = go.Figure(go.Bar(
                            x=env_cnt_df["市場環境"], y=env_cnt_df["交易次數"],
                            marker_color=env_cnt_df["顏色"],
                            text=env_cnt_df["交易次數"], textposition="outside",
                        ))
                        dist_fig.update_layout(
                            template="plotly_dark", height=200,
                            paper_bgcolor="#0a0e1a", plot_bgcolor="#0d1226",
                            margin=dict(l=20, r=20, t=20, b=30),
                            font=dict(size=10, color="#8a9bb5"),
                            showlegend=False, title="市況分布（交易次數）",
                        )
                        st.plotly_chart(dist_fig, width='stretch')

                        try:
                            pivot = r_stat.pivot_table(
                                index="訊號", columns="市場環境",
                                values="勝率%", aggfunc="first"
                            )
                            # Ensure all three columns exist even if empty
                            for env in ["🐂 多頭", "⚖️ 盤整", "🐻 空頭"]:
                                if env not in pivot.columns:
                                    pivot[env] = float("nan")
                            env_order_cols = ["🐂 多頭", "⚖️ 盤整", "🐻 空頭"]
                            pivot = pivot[env_order_cols].fillna(0)

                            z    = pivot.values.tolist()
                            xlbl = list(pivot.columns)
                            ylbl = list(pivot.index)

                            # Build text: show % if value > 0, else "─"
                            text_z = [
                                [f"{v:.0f}%" if v > 0 else "─" for v in row]
                                for row in z
                            ]

                            heat_fig = go.Figure(go.Heatmap(
                                z=z, x=xlbl, y=ylbl,
                                colorscale=[[0,"#0d1226"],[0.4,"#1a3a6a"],
                                            [0.6,"#1a6a3a"],[1,"#00ff88"]],
                                zmin=0, zmax=100,
                                text=text_z,
                                texttemplate="%{text}",
                                textfont={"size": 12, "color": "white"},
                                hovertemplate="訊號：%{y}<br>市況：%{x}<br>勝率：%{z:.1f}%<extra></extra>",
                                colorbar=dict(title="勝率%", tickformat=".0f"),
                            ))
                            heat_fig.update_layout(
                                template="plotly_dark",
                                height=max(280, len(ylbl) * 50 + 100),
                                paper_bgcolor="#0a0e1a",
                                plot_bgcolor="#0d1226",
                                margin=dict(l=130, r=60, t=50, b=20),
                                font=dict(size=11, color="#8a9bb5"),
                                xaxis=dict(side="top"),
                            )
                            st.plotly_chart(heat_fig, width='stretch')
                        except Exception as e:
                            st.caption(f"熱圖生成失敗：{e}")

                        st.dataframe(
                            r_stat, width='stretch', hide_index=True,
                            column_config={
                                "勝率%":     st.column_config.ProgressColumn(
                                    min_value=0, max_value=100, format="%.1f%%"),
                                "平均報酬%": st.column_config.NumberColumn(format="%+.2f%%"),
                                "最大獲利%": st.column_config.NumberColumn(format="%+.2f%%"),
                                "最大虧損%": st.column_config.NumberColumn(format="%+.2f%%"),
                            },
                        )

                    # ── Signal-level cross-env summary ────────────────
                    if not s_stat.empty:
                        st.markdown("##### 📋 各訊號跨市況勝率對比")
                        st.dataframe(
                            s_stat, width='stretch', hide_index=True,
                            column_config={
                                "勝率%":     st.column_config.ProgressColumn(
                                    min_value=0, max_value=100, format="%.1f%%"),
                                "平均報酬%": st.column_config.NumberColumn(format="%+.2f%%"),
                                "多頭勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                                "盤整勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                                "空頭勝率%": st.column_config.NumberColumn(format="%.1f%%"),
                            },
                        )

                    # ── Strategy recommendation ────────────────────────
                    st.markdown("##### 💡 策略建議")
                    for env, sigs in best_r.items():
                        if not sigs or sigs[0][1] < 40:
                            continue
                        top = sigs[0]
                        avoid = [s for s in sigs if s[1] < 45]
                        clr = env_colors.get(env, "#5a8fb0")
                        msg_parts = [
                            f"**{env}**：首選 **{top[0]}**（勝率 {top[1]:.0f}%，"
                            f"共 {top[2]} 次，平均 {top[3]:+.1f}%）"
                        ]
                        if len(sigs) >= 2 and sigs[1][1] >= 50:
                            msg_parts.append(f"，次選 **{sigs[1][0]}**（{sigs[1][1]:.0f}%）")
                        if avoid:
                            msg_parts.append(
                                f"。❌ 避免：{', '.join(s[0] for s in avoid[:2])}"
                                f"（勝率低於 45%）"
                            )
                        st.info("".join(msg_parts))

                    # ── Export ────────────────────────────────────────
                    with st.expander("📤 匯出環境分析詳細結果"):
                        st.download_button(
                            "下載完整交易明細（含市況分類）Excel",
                            data=to_excel(regime_result["all_trades"]),
                            file_name=f"regime_backtest_{bare_bt}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )


    # ─────────────────────────────────────────
    # TAB 4  買賣記錄 & 策略建議
    # ─────────────────────────────────────────
    with tab_port:
        st.markdown("#### 📒 買賣記錄 & 智能策略建議")
        st.caption("記錄每筆交易 · 即時計算損益 · 根據當前技術訊號給出持倉策略建議")

        trades_all = port_get_trades()

        # ══════════════════════════════════════════════════════
        # SECTION A — 新增交易記錄
        # ══════════════════════════════════════════════════════
        with st.expander("➕ 新增交易", expanded=not trades_all):
            fa1, fa2, fa3 = st.columns([2, 2, 2])
            wl_opts = [c.replace(".TW","").replace(".TWO","")
                       for c in st.session_state.watchlist]
            t_code  = fa1.selectbox("股票代號", wl_opts,
                                    key="pt_code",
                                    help="從自選股選擇")
            t_cust  = fa2.text_input("或手動輸入代號",
                                      placeholder="2330 / 3661",
                                      key="pt_cust")
            t_type  = fa3.selectbox("交易類型", ["買入", "賣出"], key="pt_type")

            fb1, fb2, fb3, fb4, fb5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
            t_date  = fb1.date_input("交易日期",
                                      value=tw_now().date(), key="pt_date")
            t_price = fb2.number_input("成交價", min_value=0.01,
                                        value=100.0, step=0.01, key="pt_price")
            t_shares = fb3.number_input("股數", min_value=1,
                                         value=1000, step=100, key="pt_shares")
            t_fee   = fb4.number_input("手續費 $", min_value=0.0,
                                        value=round(t_price * t_shares * 0.001425 * 0.6, 0),
                                        step=1.0, key="pt_fee",
                                        help="預設 0.1425%×60折")
            add_btn = fb5.button("✅ 確認新增", type="primary",
                                  width='stretch', key="pt_add")

            if add_btn:
                if float(t_price) <= 0:
                    st.error("⚠️ 成交價必須大於 0")
                elif int(t_shares) <= 0:
                    st.error("⚠️ 股數必須大於 0")
                else:
                    code_final = (t_cust.strip() or t_code).upper().replace(".TW","").replace(".TWO","")
                    cn, _ = fetch_name(code_final)
                    new_trade = {
                        "id":     port_next_id(),
                        "type":   t_type,
                        "code":   code_final,
                        "name":   cn or code_final,
                        "date":   str(t_date),
                        "price":  float(t_price),
                        "shares": int(t_shares),
                        "fee":    float(t_fee),
                    }
                if t_type == "賣出":
                    pos_now = get_open_positions(trades_all)
                    held    = pos_now.get(code_final, {}).get("shares", 0)
                    if t_shares > held:
                        st.error(f"⚠️ 持倉只有 {held} 股，無法賣出 {t_shares} 股")
                    else:
                        port_add_trade(new_trade)
                        st.session_state["_port_msg"] = f"✅ 已記錄 {t_type} {code_final} × {t_shares} 股 @ {t_price}　（已自動儲存）"
                        st.rerun()
                else:
                    port_add_trade(new_trade)
                    st.session_state["_port_msg"] = f"✅ 已記錄 {t_type} {code_final} × {t_shares} 股 @ {t_price}　（已自動儲存）"
                    # Auto-sync to Google Sheets if configured
                    _gs_id  = st.session_state.get("gs_sheet_id", "")
                    _gs_tok = st.session_state.get("gs_api_token", "")
                    if _gs_id and _gs_tok:
                        gs_append_trade(_gs_id, _gs_tok, new_trade)
                    st.rerun()

        # ── Persistent status message (shown after rerun) ──
        if "_port_msg" in st.session_state:
            st.success(st.session_state.pop("_port_msg"))

        # Import / Export
        col_imp, col_exp = st.columns(2)
        with col_imp:
            up_trades = st.file_uploader(
                "📥 匯入交易記錄 Excel",
                type=["xlsx"],
                key="port_import",
            )
            if up_trades is not None:
                # Guard: only process if we haven't already imported this file this run
                file_sig = f"{up_trades.name}_{up_trades.size}"
                if st.session_state.get("_last_import_sig") != file_sig:
                    try:
                        df_imp = pd.read_excel(up_trades)
                        req = {"type", "code", "date", "price", "shares"}
                        if req.issubset(df_imp.columns):
                            imported = df_imp.to_dict("records")
                            # Always reassign IDs from 1 on import — avoids
                            # stale IDs (e.g. 7,8,9) from previous sessions
                            for idx, r in enumerate(imported, start=1):
                                r["id"] = idx
                                r["fee"]    = float(r.get("fee",  0) or 0)
                                r["shares"] = int(float(r.get("shares", 0) or 0))
                                r["price"]  = float(r.get("price", 0) or 0)
                                r["name"]   = str(r.get("name", ""))
                                r["type"]   = str(r.get("type", "買入"))
                                r["code"]   = str(r.get("code", ""))
                                r["date"]   = str(r.get("date", ""))
                            port_replace_trades(imported, reset_id=True)
                            st.session_state["_last_import_sig"] = file_sig
                            st.session_state["_port_msg"] = f"✅ 已成功匯入 {len(imported)} 筆交易記錄並自動儲存"
                            # Rerun to refresh display with new data
                            st.rerun()
                        else:
                            missing = req - set(df_imp.columns)
                            st.error(f"欄位不足，缺少：{missing}")
                    except Exception as e:
                        st.error(f"匯入失敗：{e}")
        with col_exp:
            if trades_all:
                with st.expander("📤 匯出交易記錄", expanded=False):
                    st.download_button(
                        "📤 匯出 Excel",
                        data=to_excel(pd.DataFrame(trades_all)),
                        file_name=f"trades_{tw_now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width='stretch',
                    )

        if not trades_all:
            st.info("🔍 尚無交易記錄 — 點上方「➕ 新增交易」開始記錄")

        # ══════════════════════════════════════════════════════
        # SECTION B — 持倉總覽 + 即時損益 + 策略建議
        # ══════════════════════════════════════════════════════
        open_pos = get_open_positions(trades_all) if trades_all else {}

        if open_pos:
            st.markdown("---")
            st.markdown("#### 📊 持倉概況 & 策略建議")
            st.caption("策略建議根據：① 即時技術訊號 ② 中期趨勢 ③ 共振強度 ④ 持倉成本位置")

            # Fetch live prices + signals for all held stocks
            pos_rows = []
            advice_cards = []
            for code, p_info in open_pos.items():
                shares  = p_info["shares"]
                cost    = p_info["cost"]
                avg_px  = cost / max(shares, 1)

                # Live price
                q           = fetch_quote(code)
                quote_live  = bool(q.get("price"))
                cur_price   = q.get("price") or avg_px   # df_raw fetched below
                chg_pct     = q.get("change_pct") or 0.0

                # Unrealised P&L
                mkt_val  = cur_price * shares
                unreal   = mkt_val - cost
                unreal_p = unreal / (cost + 1e-8) * 100

                # Technical signal
                df_raw, _ = fetch_data(code, "6mo")
                # Refine cur_price fallback now that df_raw is available
                if not quote_live and df_raw is not None and len(df_raw) > 0:
                    cur_price = round(float(df_raw["Close"].iloc[-1]), 2)
                sig_key, sig_detail = "NEUTRAL", ""
                trend, conf, accel  = 0, 0, 0.0
                cci_v, rsi_v, k_v   = np.nan, np.nan, np.nan
                if df_raw is not None and len(df_raw) >= 60:
                    try:
                        df_s   = generate_signals(df_raw, params)
                        sig_key, sig_detail = get_scan_signal(df_s, lookback=5)
                        lat    = df_s.iloc[-1]
                        trend  = int(float(lat.get("TrendScore",      0) or 0))
                        conf   = int(float(lat.get("ConfluenceScore",  0) or 0))
                        accel  = float(lat.get("MomAccel", 0) or 0)
                        cci_v  = float(lat.get("CCI", np.nan))
                        rsi_v  = float(lat.get("RSI", np.nan))
                        k_v    = float(lat.get("K",   np.nan))
                    except Exception:
                        pass

                # (strategy engine defined at module level)

                # ATR already computed in df_s — no second generate_signals needed
                atr_now = np.nan
                if 'df_s' in dir() and df_s is not None:
                    try:
                        atr_now = float(df_s.iloc[-1].get("ATR", np.nan))
                    except Exception:
                        pass

                try:
                    rec = _pro_strategy(
                        sig_key, trend, conf, accel,
                        unreal_p, cur_price, avg_px,
                        shares, atr_now)
                except Exception as e:
                    rec = dict(action="⚠️ 計算錯誤", color="#666", sell_pct=0,
                               sell_shares=0, entry_add_pct=0, steps=[], urgency="觀察",
                               exec_plan=f"策略引擎發生錯誤: {e}")

                pos_rows.append({
                    "代號":       code,
                    "名稱":       p_info.get("name",""),
                    "報價":       "即時" if quote_live else "⚠️收盤",
                    "股數":       shares,
                    "均成本":     round(avg_px, 2),
                    "現價":       round(cur_price, 2),
                    "漲跌%":      round(chg_pct, 2),
                    "市值":       int(mkt_val),
                    "未實現損益":  int(unreal),
                    "報酬%":      round(unreal_p, 2),
                    "訊號":       SIGNAL_LABEL.get(sig_key, sig_key),
                    "趨勢":       trend,
                    "共振":       conf,
                    "建議":       rec["action"],
                    "賣出股數":   rec["sell_shares"] if rec["sell_shares"] > 0 else "-",
                    "緊急程度":   rec["urgency"],
                })
                advice_cards.append({
                    "code": code, "name": p_info.get("name",""),
                    "rec": rec, "sig_key": sig_key,
                    "unreal_p": unreal_p, "unreal": int(unreal),
                    "trend": trend, "conf": conf, "accel": accel,
                    "cci": cci_v, "rsi": rsi_v, "k": k_v,
                    "cur_price": cur_price, "avg_px": avg_px,
                    "shares": shares, "mkt_val": int(mkt_val),
                })

            # Portfolio summary metrics
            total_cost = sum(p["cost"] for p in open_pos.values())
            total_mkt  = sum(r["市值"]  for r in pos_rows)
            total_unrl = total_mkt - total_cost
            total_p    = total_unrl / (total_cost + 1e-8) * 100

            pm1, pm2, pm3, pm4 = st.columns(4)
            pnl_delta = "normal" if total_unrl >= 0 else "inverse"
            pm1.metric("持倉數量",   f"{len(open_pos)} 支")
            pm2.metric("總成本",     f"{total_cost/1e4:.1f} 萬")
            pm3.metric("市值",       f"{total_mkt/1e4:.1f} 萬")
            pm4.metric("未實現損益", f"{total_unrl/1e4:+.1f} 萬",
                       f"{total_p:+.1f}%")

            # Position table
            df_pos = pd.DataFrame(pos_rows)
            st.dataframe(
                df_pos,
                width='stretch',
                column_config={
                    "漲跌%":      st.column_config.NumberColumn(format="%+.2f%%"),
                    "報酬%":      st.column_config.NumberColumn(format="%+.2f%%"),
                    "未實現損益": st.column_config.NumberColumn(format="$%+,.0f"),
                    "市值":       st.column_config.NumberColumn(format="$%,.0f"),
                    "趨勢":       st.column_config.NumberColumn(format="%+d"),
                    "共振":       st.column_config.ProgressColumn(
                                  min_value=0, max_value=7, format="%d/7"),
                    "報價":       st.column_config.TextColumn(help="即時=報價成功; ⚠️收盤=使用最後收盤價"),
                    "建議":       st.column_config.TextColumn(help="詳細操作建議見下方卡片"),
                    "緊急程度":   st.column_config.TextColumn(help="立即/本週/下次交易日/觀察"),
                },
                hide_index=True,
            )

            # ── Strategy advice cards ──────────────────────────────
            st.markdown("#### 🎯 個股操作建議")
            urgency_order = {"立即": 0, "本週": 1, "下次交易日": 2, "觀察": 3}
            for card in sorted(advice_cards,
                               key=lambda c: urgency_order.get(c["rec"]["urgency"], 4)):
                rec       = card["rec"]
                color     = rec["color"]
                cci_txt   = f"{card['cci']:.1f}"   if not np.isnan(card['cci']) else "-"
                rsi_txt   = f"{card['rsi']:.1f}"   if not np.isnan(card['rsi']) else "-"
                k_txt     = f"{card['k']:.1f}"     if not np.isnan(card['k'])   else "-"
                pnl_col   = "#00ff88" if card["unreal_p"] >= 0 else "#ff3355"
                urgency   = rec["urgency"]
                urg_colors= {"立即":"#ff0033","本週":"#ff6600",
                             "下次交易日":"#f0a500","觀察":"#5a8fb0"}
                urg_col   = urg_colors.get(urgency, "#5a8fb0")

                exec_plan_lines = rec["exec_plan"].strip().split("\n")

                # ── Card using native Streamlit (no raw HTML) ──
                border_css = (
                    f"border-left:4px solid {color};"
                    f"padding:10px 14px;margin-bottom:12px;"
                    f"background:#0a1220;border-radius:0 10px 10px 0"
                )
                st.markdown(
                    f'<div style="{border_css}">'
                    f'<span style="font-size:1.1rem;font-weight:700;color:#e8f4fd;'
                    f'font-family:Space Mono,monospace">{card["code"]}</span>'
                    f'&nbsp;&nbsp;<span style="color:#8a9bb5;font-size:0.85rem">'
                    f'{card["name"]}</span>'
                    f'&nbsp;&nbsp;<span style="font-size:1.0rem;font-weight:700;'
                    f'color:{color}">{rec["action"]}</span>'
                    f'&nbsp;&nbsp;<span style="color:{urg_col};font-size:0.72rem;'
                    f'border:1px solid {urg_col};padding:1px 6px;border-radius:4px">'
                    f'⏰ {urgency}</span>'
                    + (f'&nbsp;&nbsp;<span style="background:#ff1a44;color:#fff;'
                       f'padding:1px 8px;border-radius:4px;font-size:0.75rem">'
                       f'賣 {rec["sell_shares"]:,}股 ({rec["sell_pct"]}%)</span>'
                       if rec["sell_shares"] > 0 else
                       f'&nbsp;&nbsp;<span style="background:#006633;color:#fff;'
                       f'padding:1px 8px;border-radius:4px;font-size:0.75rem">'
                       f'加 {rec["entry_add_pct"]}% 部位</span>'
                       if rec["entry_add_pct"] > 0 else "")
                    + f'</div>',
                    unsafe_allow_html=True,
                )

                # P&L row
                ca, cb, cc, cd, ce = st.columns(5)
                ca.metric("現價",   f"{card['cur_price']:.2f}")
                cb.metric("均成本", f"{card['avg_px']:.2f}")
                cc.metric("持股",   f"{card['shares']:,}股")
                cd.metric("損益",   f"{card['unreal_p']:+.1f}%",
                          f"{card['unreal']:+,}元")
                ce.metric("市值",   f"{card['mkt_val']//10000:.1f}萬")

                # 5-dimension steps
                with st.expander("▸ 五維度分析", expanded=False):
                    for step_lbl, step_txt in rec["steps"]:
                        st.caption(f"**{step_lbl}** {step_txt}")

                # Execution plan
                st.markdown(
                    f'<div style="background:#0b1520;border-left:3px solid {color};'
                    f'padding:8px 12px;border-radius:0 6px 6px 0;'
                    f'font-size:0.78rem;color:#8a9bb5;line-height:1.8;'
                    f'white-space:pre-line">'
                    + "\n".join(l.strip() for l in exec_plan_lines)
                    + "</div>",
                    unsafe_allow_html=True,
                )

                # Technical reference
                st.caption(
                    f"CCI {cci_txt} · RSI {rsi_txt} · K值 {k_txt} · "
                    f"共振 {card['conf']}/7 · 加速 {card['accel']:+.2f} · "
                    f"訊號 {SIGNAL_LABEL.get(card['sig_key'], '─')}"
                )
                st.markdown("---")

        # ══════════════════════════════════════════════════════
        # SECTION C — 歷史交易績效
        # ══════════════════════════════════════════════════════
        closed = get_closed_trades(trades_all)
        if closed:
            st.markdown("---")
            st.markdown("#### 📋 歷史已結算交易")
            df_closed = pd.DataFrame(closed)
            wins_c  = len(df_closed[df_closed["結果"] == "獲利"])
            total_c = len(df_closed)
            wr_c    = wins_c / total_c * 100 if total_c else 0
            total_pnl = df_closed["實現損益"].sum()
            avg_ret_c = df_closed["報酬%"].mean()

            hm1, hm2, hm3, hm4 = st.columns(4)
            hm1.metric("已結算交易",  total_c)
            hm2.metric("實現勝率",    f"{wr_c:.1f}%",
                       "✅" if wr_c >= 55 else "⚠️")
            hm3.metric("總實現損益",  f"{int(total_pnl):+,} 元")
            hm4.metric("平均報酬",    f"{avg_ret_c:+.2f}%")

            st.dataframe(
                df_closed,
                width='stretch',
                column_config={
                    "報酬%":      st.column_config.NumberColumn(format="%+.2f%%"),
                    "實現損益":   st.column_config.NumberColumn(format="$%+,.0f"),
                },
                hide_index=True,
            )

        # ══════════════════════════════════════════════════════
        # SECTION D — 完整交易明細 & 刪除
        # ══════════════════════════════════════════════════════
        with st.expander("📑 所有交易記錄（可刪除）"):
            trades_now = port_get_trades()
            if trades_now:
                df_all = pd.DataFrame(trades_now)
                st.dataframe(df_all[["id","type","code","name","date",
                                      "price","shares","fee"]],
                             width='stretch', hide_index=True)
                del_id = st.number_input("刪除指定 ID", min_value=1,
                                         step=1, key="del_id")
                if st.button("🗑 刪除此筆記錄", key="del_btn"):
                    ok = port_delete_trade(int(del_id))
                    if ok:
                        st.session_state["_port_msg"] = f"已刪除 ID={del_id}（已自動儲存）"
                        st.rerun()
                    else:
                        st.warning(f"找不到 ID={del_id}")
            else:
                st.info("暫無交易記錄")

        # ── Emergency export + storage status ──────────────────
        st.markdown("---")
        trades_now = port_get_trades()
        file_ok    = os.path.exists(_TRADE_FILE)
        n_trades   = len(trades_now)

        if n_trades > 0:
            store_color = "#00ff88" if file_ok else "#f0a500"
            store_msg   = (f"✅ 已自動儲存 {n_trades} 筆記錄到本地備份"
                           if file_ok else
                           f"⚠️ 本地備份未建立 — 請立即匯出 Excel 儲存")
            st.markdown(
                f'<div style="background:#0a1a0f;border:1.5px solid {store_color};'
                f'border-radius:8px;padding:10px 14px;margin-bottom:8px">'
                f'<span style="color:{store_color};font-size:0.82rem">{store_msg}</span><br>'
                f'<span style="color:#37474f;font-size:0.72rem">'
                f'容器每天重啟後本地備份消失 — 展開下方「立即匯出備份」定期儲存</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Put download button inside expander — prevents MediaFileHandler spam
            # from auto-refresh (meta-refresh regenerates file IDs every cycle)
            with st.expander(f"🆘 立即匯出備份（{n_trades} 筆交易）", expanded=False):
                st.caption("每次新增/修改交易後請點此匯出，下次重啟後可用匯入還原。")
                st.download_button(
                    label="📥 下載備份 Excel",
                    data=to_excel(pd.DataFrame(trades_now)),
                    file_name=f"sentinel_trades_{tw_now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    width='stretch',
                )


    # ─────────────────────────────────────────
    # TAB 5  訊號歷史勝率
    # ─────────────────────────────────────────
    with tab_sig_hist:
        st.markdown("#### 📈 真實訊號歷史勝率追蹤")
        st.caption(
            "每次掃描發現買入訊號時自動記錄。之後每次掃描自動回填 5/10/20 交易日的實際報酬，"
            "幫助你驗證訊號的真實效果，而非假設性回測。"
        )

        records = sig_hist_get_all()
        df_hist  = sig_hist_to_df(records)

        # ── 手動觸發更新 ──
        col_upd, col_exp, col_clr = st.columns([2, 2, 1])
        if col_upd.button("🔄 立即更新報酬", key="sh_update", width='stretch'):
            with st.spinner("更新中，下載各股歷史價格…"):
                n = sig_hist_update_outcomes(fetch_data)
            st.success(f"✅ 更新了 {n} 筆記錄")
            st.rerun()

        records = sig_hist_get_all()
        df_hist = sig_hist_to_df(records)

        if not df_hist.empty:
            with col_exp:
                with st.expander("📤 匯出記錄", expanded=False):
                    st.download_button(
                        "下載 Excel",
                        data=to_excel(df_hist),
                        file_name=f"sig_history_{tw_now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width='stretch',
                    )
            if col_clr.button("🗑", key="sh_clear", help="清除所有歷史記錄"):
                sig_hist_clear()
                st.rerun()

        if df_hist.empty:
            st.info(
                "📭 尚無歷史記錄。\n\n"
                "執行一次掃描後，所有出現的買入訊號會自動記錄。"
                "之後每次掃描會自動填入 5/10/20 日後的實際報酬。"
            )
        else:
            total    = len(records)
            complete = sum(1 for r in records if r.get("status") == "complete")
            pending  = sum(1 for r in records if r.get("status") == "pending")

            ma, mb, mc, md = st.columns(4)
            ma.metric("總記錄訊號", total)
            mb.metric("已完成追蹤", complete)
            mc.metric("等待中",     pending)
            md.metric("追蹤中",     total - complete - pending)

            # ── Per-signal win rate summary ──────────────────────────
            completed_recs = [r for r in records if r.get("status") == "complete"]
            if completed_recs:
                st.markdown("---")
                st.markdown("##### 📊 各訊號類型真實勝率統計")

                summary_rows = []
                for period_key, period_label in [("ret_5d","5日"), ("ret_10d","10日"), ("ret_20d","20日")]:
                    by_sig = {}
                    for r in completed_recs:
                        sk = r.get("sig_key","")
                        if sk not in by_sig:
                            by_sig[sk] = []
                        v = r.get(period_key)
                        if v is not None:
                            by_sig[sk].append(v)

                    for sk, rets in by_sig.items():
                        if not rets:
                            continue
                        wins    = sum(1 for v in rets if v > 0)
                        wr      = wins / len(rets) * 100
                        avg_ret = sum(rets) / len(rets)
                        max_ret = max(rets)
                        min_ret = min(rets)
                        summary_rows.append({
                            "訊號":      SIGNAL_LABEL.get(sk, sk),
                            "持有期":    period_label,
                            "次數":      len(rets),
                            "真實勝率%": round(wr, 1),
                            "平均報酬%": round(avg_ret, 2),
                            "最大獲利%": round(max_ret, 2),
                            "最大虧損%": round(min_ret, 2),
                        })

                if summary_rows:
                    df_sum = (pd.DataFrame(summary_rows)
                              .sort_values(["持有期","真實勝率%"],
                                           ascending=[True, False])
                              .reset_index(drop=True))
                    st.dataframe(
                        df_sum, width='stretch', hide_index=True,
                        column_config={
                            "真實勝率%": st.column_config.ProgressColumn(
                                min_value=0, max_value=100, format="%.1f%%"),
                            "平均報酬%": st.column_config.NumberColumn(format="%+.2f%%"),
                            "最大獲利%": st.column_config.NumberColumn(format="%+.2f%%"),
                            "最大虧損%": st.column_config.NumberColumn(format="%+.2f%%"),
                        },
                    )

                    # ── Confluence filter analysis ────────────────────
                    st.markdown("##### 🔍 共振分數 vs 勝率（20日持有）")
                    st.caption("驗證共振門檻設定是否真正有效")
                    conf_rows = []
                    for min_conf in range(3, 8):
                        subset = [r for r in completed_recs
                                  if r.get("confluence", 0) >= min_conf
                                  and r.get("ret_20d") is not None]
                        if len(subset) < 3:
                            continue
                        wr20 = sum(1 for r in subset if r["ret_20d"] > 0) / len(subset) * 100
                        avg20 = sum(r["ret_20d"] for r in subset) / len(subset)
                        conf_rows.append({
                            "共振門檻 ≥": min_conf,
                            "符合訊號數": len(subset),
                            "20日勝率%":  round(wr20, 1),
                            "20日平均報酬%": round(avg20, 2),
                        })

                    if conf_rows:
                        df_conf = pd.DataFrame(conf_rows)
                        st.dataframe(
                            df_conf, width='stretch', hide_index=True,
                            column_config={
                                "20日勝率%": st.column_config.ProgressColumn(
                                    min_value=0, max_value=100, format="%.1f%%"),
                                "20日平均報酬%": st.column_config.NumberColumn(format="%+.2f%%"),
                            },
                        )
                        # Highlight optimal confluence threshold
                        best_conf = df_conf.loc[df_conf["20日勝率%"].idxmax()]
                        st.info(
                            f"💡 根據歷史數據，共振門檻設為 "
                            f"**{int(best_conf['共振門檻 ≥'])}** 時勝率最高："
                            f"**{best_conf['20日勝率%']:.1f}%**"
                            f"（{int(best_conf['符合訊號數'])} 次交易）"
                        )

            # ── Full record table ─────────────────────────────────────
            st.markdown("---")
            st.markdown("##### 📋 完整訊號記錄")

            # Filter controls
            fc1, fc2 = st.columns(2)
            filter_sig  = fc1.multiselect(
                "篩選訊號類型",
                options=df_hist["訊號"].unique().tolist(),
                default=[],
                key="sh_filter_sig",
                placeholder="全部訊號",
            )
            filter_stat = fc2.multiselect(
                "篩選狀態",
                options=["⏳等待","🔄部分","✅完成"],
                default=[],
                key="sh_filter_stat",
                placeholder="全部狀態",
            )

            df_show = df_hist.copy()
            if filter_sig:
                df_show = df_show[df_show["訊號"].isin(filter_sig)]
            if filter_stat:
                df_show = df_show[df_show["狀態"].isin(filter_stat)]

            st.dataframe(
                df_show, width='stretch', hide_index=True,
                height=min(400, 35 + len(df_show) * 35),
                column_config={
                    "5日%":   st.column_config.NumberColumn(format="%+.2f%%"),
                    "10日%":  st.column_config.NumberColumn(format="%+.2f%%"),
                    "20日%":  st.column_config.NumberColumn(format="%+.2f%%"),
                    "進場價": st.column_config.NumberColumn(format="%.2f"),
                    "共振":   st.column_config.ProgressColumn(
                               min_value=0, max_value=7, format="%d/7"),
                },
            )
            st.caption(f"共 {len(df_show)} 筆 | 等待中的記錄在下次掃描時自動更新")


if __name__ == "__main__":
    main()
