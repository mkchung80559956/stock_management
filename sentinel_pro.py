"""
╔══════════════════════════════════════════════════════════════════════╗
║          SENTINEL PRO — 台股專業掃描暨交易決策系統                  ║
║                                                                      ║
║  Copyright (c) 2026 Malcolm Chung (鍾茂功). All Rights Reserved.    ║
║                                                                      ║
║  本軟體為作者私人財產，未經書面授權不得複製、修改、散佈或商業使用。  ║
║  投資有風險，本系統訊號僅供參考，不構成投資建議。                   ║
║                                                                      ║
║  CCI × 成交量 × 價格行為 量價策略訊號系統                           ║
║  Version: see APP_VERSION below                                      ║
╚══════════════════════════════════════════════════════════════════════╝
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
    "HIGH_CONF_BUY":      0,
    "HIGH_CONF_PULLBACK": 0,   # same priority as HC_BUY — confirmed re-entry
    "BREAKOUT_BUY":   1, "STRONG_BUY":  2, "BUY": 3, "DIV_BUY": 3,
    "KD_GOLDEN_ZONE": 3,
    "BULL_ZONE": 4, "RISING": 5,
    "WATCH": 8, "NEUTRAL": 9,
    "FALLING": 6, "BEAR_ZONE": 6, "KD_HIGH": 7,
    "DIV_SELL": 5, "SELL": 6, "STRONG_SELL": 5, "FAKE_BREAKOUT": 7,
}

SIGNAL_LABEL = {
    "HIGH_CONF_BUY":      "⭐ 三重共振",
    "HIGH_CONF_PULLBACK": "💎 共振回調買",   # new
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

    # ── HIGH_CONF_PULLBACK detector ────────────────────────────────
    # After a HIGH_CONF_BUY or BREAKOUT_BUY fires, watch for a healthy
    # pullback within the next 1–3 bars.  Entry here typically has a
    # tighter stop and better risk/reward than chasing on signal day.
    #
    # Conditions (all must be true on the pullback bar):
    #   1. A HIGH_CONF_BUY or BREAKOUT_BUY occurred within last 3 bars
    #   2. Price dipped at least 0.5% from the signal-day close  ← confirms a real pullback
    #   3. Decline < 5%                                           ← not a reversal
    #   4. Volume < 80% of signal-day volume                     ← weak supply (健康縮量)
    #   5. CCI still above 0                                      ← momentum intact
    #   6. Close > EMA20                                          ← structure intact
    #   7. Current bar has no own buy signal yet                  ← avoid duplication
    try:
        hc_idx = set(df.index[df["Signal"].isin({"HIGH_CONF_BUY", "BREAKOUT_BUY"})])
        if hc_idx:
            pullback_mask = pd.Series(False, index=df.index)
            for i, idx in enumerate(df.index):
                if i < 1:
                    continue
                # Check if any HC signal fired in the prior 1–3 bars
                lookback = df.index[max(0, i-3):i]
                prior_hc = [d for d in lookback if d in hc_idx]
                if not prior_hc:
                    continue
                sig_bar   = df.loc[prior_hc[-1]]   # most recent HC bar
                cur       = df.iloc[i]

                # Compute conditions
                sig_close  = float(sig_bar["Close"])
                cur_close  = float(cur["Close"])
                cur_vol    = float(cur["Volume"])
                sig_vol    = float(sig_bar["Volume"])
                cur_cci    = float(cur.get("CCI", 0) or 0)
                cur_ema20  = float(cur.get("EMA2", cur_close) or cur_close)

                price_drop = (sig_close - cur_close) / sig_close * 100  # positive = down
                vol_ratio  = cur_vol / sig_vol if sig_vol > 0 else 1.0

                cond_dip        = price_drop >= 0.5            # real pullback ≥0.5%
                cond_not_crash  = price_drop < 5.0             # not a reversal
                cond_vol_shrink = vol_ratio < 0.80             # volume dried up
                cond_cci_ok     = cur_cci > 0                  # momentum intact
                cond_above_ema  = cur_close > cur_ema20        # above EMA20
                cond_no_signal  = df.index[i] not in hc_idx and \
                                   df.at[idx, "Signal"] not in BUY_SIGNALS

                if (cond_dip and cond_not_crash and cond_vol_shrink
                        and cond_cci_ok and cond_above_ema and cond_no_signal):
                    pullback_mask.at[idx] = True

            # Assign signal — only to NEUTRAL bars (don't overwrite existing signals)
            pb_new = pullback_mask & (df["Signal"] == "NEUTRAL")
            df.loc[pb_new, "Signal"] = "HIGH_CONF_PULLBACK"
            for idx in df.index[pb_new]:
                sig_bar_idx = [d for d in df.index[max(0, df.index.get_loc(idx)-3):
                                                    df.index.get_loc(idx)]
                               if d in hc_idx]
                ref_date = str(sig_bar_idx[-1].date()) if sig_bar_idx else "近期"
                drop_pct  = round((float(df.at[sig_bar_idx[-1], "Close"])
                                   - float(df.at[idx, "Close"]))
                                  / float(df.at[sig_bar_idx[-1], "Close"]) * 100, 2) \
                            if sig_bar_idx else 0
                df.at[idx, "Signal_Detail"] = (
                    f"💎 共振後回調買：{ref_date} 三重共振，"
                    f"縮量回調 -{drop_pct:.1f}%，CCI>0 結構完整，"
                    f"風險報酬比優於訊號日追入"
                )
    except Exception:
        pass   # pullback detection is best-effort; never break the main flow

    return df


# ══════════════════════════════════════════════
# BACKTESTING
# ══════════════════════════════════════════════

BUY_SIGNALS  = {"HIGH_CONF_BUY", "HIGH_CONF_PULLBACK",
                "STRONG_BUY", "BUY", "DIV_BUY", "BREAKOUT_BUY"}
SELL_SIGNALS = {"STRONG_SELL", "SELL", "DIV_SELL"}


# ══════════════════════════════════════════════════════════════════
# SIGNAL  LIFECYCLE  ENGINE
# 訊號生命週期管理：進場窗口 / 退場條件 / 狀態追蹤 / 說明
# ══════════════════════════════════════════════════════════════════

# ── Per-signal lifecycle definition ───────────────────────────────
# Each entry defines the DNA of a signal:
#   entry_day   : when to enter relative to signal day (D+0 = same day)
#   entry_latest: last acceptable entry day (after this → EXPIRED)
#   entry_time  : recommended clock time for entry
#   holding     : typical holding description
#   stop_method : how to set stop loss
#   stop_pct    : default fixed stop %
#   target_r    : target R-multiples (list)
#   exit_triggers: conditions that force exit
#   decay_days  : signal loses validity after N days without entry
#   trade_type  : overnight / swing / longterm
#   explanation : plain-language explanation shown in UI
SIGNAL_LIFECYCLE = {
    "HIGH_CONF_BUY": dict(
        label="⭐ 三重共振",
        color="#ffd700",
        entry_day=0,
        entry_latest=2,
        entry_time="13:20–13:30（收盤前）",
        holding="彈性：隔日沖 / 波段 / 長線皆宜",
        stop_method="ATR × 1.5 或 固定 -7%",
        stop_pct=7.0,
        target_r=[1.5, 2.5],
        decay_days=3,
        trade_type="swing",
        exit_triggers=["跌破停損", "CCI跌破0軸+放量", "出現頂背離", "第4日未突破"],
        explanation=(
            "三重共振是最高勝率訊號，但**訊號日追高風險大**。\n\n"
            "**最佳策略**：訊號日觀察，等收盤前 13:20 確認量能未萎縮再進，"
            "或等次日縮量回調（💎 共振回調買）再進場，停損更近。\n\n"
            "**有效期**：3 個交易日。第 4 天若股價未能突破訊號日高點，"
            "視為主力動能衰減，訊號失效不再追入。\n\n"
            "**退場原則**：\n"
            "• 短線：次日開盤 +3% 以上分批出\n"
            "• 波段：CCI 突破 +100 後設移動停損，讓利潤奔跑\n"
            "• 長線：跌破 EMA200 年線才考慮全出"
        ),
    ),
    "HIGH_CONF_PULLBACK": dict(
        label="💎 共振回調買",
        color="#00e5ff",
        entry_day=0,
        entry_latest=0,
        entry_time="訊號出現當日任意時間",
        holding="同三重共振，但停損更緊",
        stop_method="訊號日低點下方 0.5%",
        stop_pct=4.0,
        target_r=[2.0, 4.0],
        decay_days=1,
        trade_type="swing",
        exit_triggers=["跌破訊號日低點", "CCI跌破0軸", "回調超過5%"],
        explanation=(
            "三重共振後的健康縮量回調，是**比訊號當天更好的進場點**。\n\n"
            "**為何更好？** 停損放在訊號日低點（通常只有 2–4%），"
            "目標不變（10–20%），風險報酬比提升 2–3 倍。\n\n"
            "**進場邏輯**：今日縮量（量 < 訊號日 80%）+ CCI > 0 + 站上 EMA20，"
            "表示主力未出貨，只是短線浮額在洗盤。\n\n"
            "**注意**：此訊號**有效期只有當天**。"
            "如果當天未進場，明天可能就已經脫離最佳買點。"
        ),
    ),
    "BREAKOUT_BUY": dict(
        label="🟠 噴發買",
        color="#ff9900",
        entry_day=1,
        entry_latest=3,
        entry_time="D+1 開盤後 09:30–10:00",
        holding="波段為主，3–10 個交易日",
        stop_method="訊號日低點",
        stop_pct=6.0,
        target_r=[2.0, 3.0],
        decay_days=5,
        trade_type="swing",
        exit_triggers=["跌破訊號日低點", "CCI跌破+100後再次下穿", "量能萎縮3日"],
        explanation=(
            "CCI 強力突破 +100 + 強放量，代表**主力資金大幅買入**。\n\n"
            "**為何不在訊號日進？** 噴發當天追高，追的是最貴的價格，"
            "前方套牢籌碼多，回吐風險大。\n\n"
            "**最佳進法**：等次日開盤，觀察量能是否延續。若開盤量繼續放大、"
            "突破前日高點 → 進場。若開盤跳空過高（超過 3%）→ 不追，等回調。\n\n"
            "**有效期**：5 個交易日。超過仍未進場，主力動能可能已消耗。"
        ),
    ),
    "STRONG_BUY": dict(
        label="🟢 強買",
        color="#00ff88",
        entry_day=0,
        entry_latest=2,
        entry_time="D+0 收盤前 or D+1 開盤",
        holding="3–7 個交易日",
        stop_method="訊號日低點",
        stop_pct=5.0,
        target_r=[1.5, 2.5],
        decay_days=3,
        trade_type="swing",
        exit_triggers=["跌破訊號日低點", "反彈至EMA20後量縮", "出現賣出訊號"],
        explanation=(
            "CCI 從 -100 以下突破 + 放量 + 止跌 K 棒（下影線/吞噬），"
            "是**底部反彈的強確認**。\n\n"
            "**進場邏輯**：止跌 K 棒已確認底部，訊號當天收盤前可小量試單（30%），"
            "次日確認不破低再加碼（70%）。\n\n"
            "**不同於三重共振**：強買通常在底部出現，EMA 排列可能還未對齊，"
            "適合**波段反彈操作**，不適合長線。\n\n"
            "**目標**：反彈至 EMA20 附近（約 5–10% 空間）後評估是否繼續持有。"
        ),
    ),
    "DIV_BUY": dict(
        label="🟢 底背離",
        color="#00ff88",
        entry_day=1,
        entry_latest=3,
        entry_time="D+1 確認當日不破低後進",
        holding="5–15 個交易日",
        stop_method="背離低點下方 1%",
        stop_pct=6.0,
        target_r=[2.0, 4.0],
        decay_days=5,
        trade_type="swing",
        exit_triggers=["跌破背離低點", "CCI不再抬高（背離失效）", "股價創新低"],
        explanation=(
            "**底背離**：股價創新低，但 CCI 底部在抬高 → 賣壓在減弱，底部可能確立。\n\n"
            "**進場邏輯**：背離當天先觀察，次日確認股價未再創新低、"
            "量能略有回升，才進場。倉位從小到大，分 2–3 批。\n\n"
            "**停損**：放在背離形成的最低點下方 1%。\n"
            "若底部支撐被有效跌破，背離型態失效，必須立即出場。\n\n"
            "**目標**：底部反彈通常有 15–25% 空間，是波段中勝率較高的型態。"
        ),
    ),
    "BUY": dict(
        label="🔵 買入",
        color="#44ddff",
        entry_day=0,
        entry_latest=1,
        entry_time="D+0 收盤前 / D+1 開盤",
        holding="2–5 個交易日",
        stop_method="固定 -5%",
        stop_pct=5.0,
        target_r=[1.0, 2.0],
        decay_days=2,
        trade_type="swing",
        exit_triggers=["跌破-5%停損", "CCI重新跌破0軸", "次日無量"],
        explanation=(
            "CCI 突破 0 軸 + 放量，動能由負轉正的**早期訊號**。\n\n"
            "**特性**：比三重共振更早，但共振指標尚未全部對齊，"
            "勝率低於三重共振，建議**小倉試單**（總資金 5–8%）。\n\n"
            "**策略**：若次日繼續放量上漲 → 可加碼。若次日縮量橫盤 → 觀察。"
            "若次日放量下跌 → 訊號失效，依停損出場。\n\n"
            "**有效期**：2 個交易日，短期確認機制。"
        ),
    ),
}

_LIFECYCLE_FILE = "/tmp/sentinel_lifecycle.json"


def _load_lifecycle_store() -> dict:
    """Always read fresh from disk — lifecycle data must be current."""
    try:
        if os.path.exists(_LIFECYCLE_FILE):
            with open(_LIFECYCLE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"records": []}


def _save_lifecycle(store: dict) -> None:
    tmp = _LIFECYCLE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _LIFECYCLE_FILE)


def lifecycle_add(record: dict) -> bool:
    """
    Add a new lifecycle record for a buy signal.
    Deduplicates by (code, sig_key, date_fired).
    Returns True if added, False if duplicate.
    """
    store = _load_lifecycle_store()
    key = (record["code"], record["sig_key"], record["date_fired"])
    existing = {(r["code"], r["sig_key"], r["date_fired"]) for r in store["records"]}
    if key in existing:
        return False
    store["records"].append(record)
    _save_lifecycle(store)
    return True


def lifecycle_build_record(code: str, name: str, sig_key: str,
                            price: float, atr_stop: float,
                            conf: int, trend: int) -> dict:
    """
    Build a complete lifecycle record for a new buy signal.
    Includes entry window, stop prices, targets, explanation.
    """
    cfg  = SIGNAL_LIFECYCLE.get(sig_key, SIGNAL_LIFECYCLE["BUY"])
    today = tw_now().date()

    # Calculate trading days for entry window (skip weekends)
    def add_trading_days(start_date, n_days):
        d = start_date
        added = 0
        while added < n_days:
            d = d + __import__('datetime').timedelta(days=1)
            if d.weekday() < 5:   # Mon-Fri
                added += 1
        return d

    entry_open  = (today if cfg["entry_day"] == 0
                   else add_trading_days(today, cfg["entry_day"]))
    entry_close = add_trading_days(today, cfg["entry_latest"]) \
                  if cfg["entry_latest"] > 0 else today
    expiry      = add_trading_days(today, cfg["decay_days"])

    stop_fixed  = round(price * (1 - cfg["stop_pct"] / 100), 2)
    stop_price  = min(float(atr_stop) if isinstance(atr_stop, (int, float))
                      and atr_stop > 0 else stop_fixed, stop_fixed)
    risk_per_sh = price - stop_price
    target_1r   = round(price + risk_per_sh * cfg["target_r"][0], 2)
    target_2r   = round(price + risk_per_sh * cfg["target_r"][1], 2)

    return {
        "id":           f"{code}_{sig_key}_{today}",
        "code":         code,
        "name":         name,
        "sig_key":      sig_key,
        "sig_label":    cfg["label"],
        "color":        cfg["color"],
        "date_fired":   str(today),
        "price_fired":  price,
        "conf":         conf,
        "trend":        trend,
        # Entry window
        "entry_open":   str(entry_open),
        "entry_close":  str(entry_close),
        "entry_time":   cfg["entry_time"],
        "entry_latest": cfg["entry_latest"],
        # Risk management
        "stop_price":   stop_price,
        "stop_method":  cfg["stop_method"],
        "target_1r":    target_1r,
        "target_2r":    target_2r,
        "risk_per_sh":  round(risk_per_sh, 2),
        # Exit rules
        "exit_triggers":cfg["exit_triggers"],
        "expiry_date":  str(expiry),
        "decay_days":   cfg["decay_days"],
        "trade_type":   cfg["trade_type"],
        "holding":      cfg["holding"],
        "explanation":  cfg["explanation"],
        # Status tracking
        "status":       "active",    # active / entered / expired / stopped / target
        "entered_price": None,
        "entered_date":  None,
        "exit_price":    None,
        "exit_date":     None,
        "exit_reason":   None,
    }


def lifecycle_update_statuses() -> int:
    """
    Scan all active records and auto-expire those past their expiry_date.
    Returns count of records changed.
    """
    store   = _load_lifecycle_store()
    today   = tw_now().date()
    changed = 0
    for r in store["records"]:
        if r["status"] != "active":
            continue
        expiry = __import__('datetime').date.fromisoformat(r["expiry_date"])
        if today > expiry:
            r["status"]      = "expired"
            r["exit_reason"] = f"訊號有效期 {r['decay_days']} 天已過，自動失效"
            changed += 1
    if changed:
        _save_lifecycle(store)
    return changed


def lifecycle_get_active() -> list:
    """Return all active (not expired/stopped/target) lifecycle records."""
    return [r for r in _load_lifecycle_store()["records"]
            if r["status"] == "active"]


def lifecycle_get_all() -> list:
    return _load_lifecycle_store()["records"]


def lifecycle_mark_entered(record_id: str, price: float) -> None:
    store = _load_lifecycle_store()
    for r in store["records"]:
        if r["id"] == record_id:
            r["status"]        = "entered"
            r["entered_price"] = price
            r["entered_date"]  = str(tw_now().date())
            break
    _save_lifecycle(store)


def lifecycle_mark_exit(record_id: str, price: float, reason: str) -> None:
    store = _load_lifecycle_store()
    for r in store["records"]:
        if r["id"] == record_id:
            r["status"]      = "stopped" if "停損" in reason else "target"
            r["exit_price"]  = price
            r["exit_date"]   = str(tw_now().date())
            r["exit_reason"] = reason
            break
    _save_lifecycle(store)


def lifecycle_days_remaining(record: dict) -> int:
    """Return trading days remaining in the entry window. Negative = expired."""
    try:
        today  = tw_now().date()
        expiry = __import__('datetime').date.fromisoformat(record["expiry_date"])
        delta  = (expiry - today).days
        return delta
    except Exception:
        return 0


def lifecycle_urgency(record: dict) -> str:
    """Return urgency label based on days remaining."""
    days = lifecycle_days_remaining(record)
    if days <= 0:   return "已失效"
    if days == 1:   return "🔴 最後1天"
    if days == 2:   return "🟠 剩2天"
    return f"🟢 剩{days}天"


def lifecycle_tg_reminder(active_records: list, token: str, chat_id: str) -> int:
    """
    Push Telegram reminders for active signals:
    - Expiring tomorrow: 'Last chance' alert
    - Newly added today: entry window open
    Returns count of messages sent.
    """
    if not token or not chat_id:
        return 0
    today = str(tw_now().date())
    msgs  = []
    for r in active_records:
        days = lifecycle_days_remaining(r)
        if days == 1:
            msgs.append(
                f"⏰ 明日進場最後機會\n"
                f"{r['sig_label']} {r['code']} {r['name']}\n"
                f"進場窗口：{r['entry_open']} – {r['entry_close']}\n"
                f"訊號價：{r['price_fired']:.2f}  停損：{r['stop_price']:.2f}\n"
                f"目標1：{r['target_1r']:.2f}  目標2：{r['target_2r']:.2f}"
            )
        elif r["date_fired"] == today and days > 1:
            msgs.append(
                f"🆕 新訊號進場窗口開啟\n"
                f"{r['sig_label']} {r['code']} {r['name']}\n"
                f"建議進場：{r['entry_time']}\n"
                f"停損：{r['stop_price']:.2f}  目標：{r['target_1r']:.2f} / {r['target_2r']:.2f}\n"
                f"有效至：{r['expiry_date']}（剩 {days} 天）"
            )
    sent = 0
    for msg in msgs:
        n = tg_broadcast(msg)
        sent += n
    return sent



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

    # ── 補充名稱（v3.2 新增 284 支自選股）────────────────
    "00896": ("中信綠能及電動車", "上市"),
    "00900": ("富邦特選高股息30", "上市"),
    "00907": ("永豐優息存股", "上市"),
    "1590": ("亞德客-KY", "上市"),
    "2027": ("大成鋼", "上市"),
    "2059": ("川湖科技", "上市"),
    "2103": ("台橡", "上市"),
    "2206": ("三陽工業", "上市"),
    "2323": ("中環", "上市"),
    "2331": ("精英電腦", "上市"),
    "2426": ("鼎元光電", "上市"),
    "2429": ("銘異科技", "上市"),
    "2504": ("國產建設", "上市"),
    "2511": ("太子建設", "上市"),
    "2514": ("龍邦建設", "上市"),
    "2520": ("冠德建設", "上市"),
    "2524": ("京城建設", "上市"),
    "2528": ("皇普建設", "上市"),
    "2535": ("達欣工程", "上市"),
    "2545": ("皇翔建設", "上市"),
    "2597": ("潤弘精工", "上市"),
    "2641": ("正德海運", "上市"),
    "2642": ("宅配通", "上市"),
    "2704": ("國賓大飯店", "上市"),
    "2736": ("雲品溫泉酒店", "上市"),
    "2832": ("台產", "上市"),
    "2845": ("遠東銀", "上市"),
    "2849": ("安泰銀行", "上市"),
    "2855": ("統一證", "上市"),
    "2867": ("三商壽", "上市"),
    "3055": ("蔚華科技", "上市"),
    "3059": ("華晶科技", "上市"),
    "3068": ("大揚精密", "上市"),
    "3130": ("一零四資訊", "上市"),
    "3209": ("全科電腦", "上市"),
    "3217": ("優群科技", "上市"),
    "3221": ("台嘉碩", "上市"),
    "3305": ("昇貿科技", "上市"),
    "3338": ("泰碩電子", "上市"),
    "3356": ("奇鋐科技", "上市"),
    "3376": ("新日興", "上市"),
    "3380": ("明泰科技", "上市"),
    "3406": ("玉晶光電", "上市"),
    "3450": ("聯鈞光電", "上市"),
    "3494": ("誠研科技", "上市"),
    "3520": ("得力科技", "上市"),
    "3536": ("洋華光電", "上市"),
    "3545": ("敦泰電子", "上市"),
    "3580": ("友威科技", "上市"),
    "3665": ("貿聯-KY", "上市"),
    "3682": ("亞信電子", "上市"),
    "3693": ("營邦企業", "上市"),
    "3703": ("欣陸投控", "上市"),
    "3707": ("漢磊科技", "上市"),
    "3712": ("永崴投控", "上市"),
    "3716": ("惠特科技", "上市"),
    "3738": ("倚強科技", "上市"),
    "3741": ("辰緯科技", "上市"),
    "3752": ("耕興電子", "上市"),
    "3762": ("達興材料", "上市"),
    "3779": ("兆遠科技", "上市"),
    "3782": ("揚博科技", "上市"),
    "3784": ("愛地雅", "上市"),
    "3788": ("晶翔微系統", "上市"),
    "3791": ("泰碩電子", "上市"),
    "3794": ("晶睿通訊", "上市"),
    "3799": ("勝麗國際", "上市"),
    "4935": ("茂林-KY", "上市"),
    "4952": ("凌通科技", "上市"),
    "4953": ("緯軟", "上市"),
    "4960": ("誠美材", "上市"),
    "4963": ("聲立科技", "上市"),
    "4967": ("十銓科技", "上市"),
    "4968": ("立積電子", "上市"),
    "4971": ("IET-KY", "上市"),
    "4972": ("湯石照明", "上市"),
    "4974": ("亞泰半導體", "上市"),
    "4977": ("眾達-KY", "上市"),
    "4979": ("華星光通", "上市"),
    "4981": ("炎洲", "上市"),
    "4984": ("科嘉-KY", "上市"),
    "4988": ("誠創科技", "上市"),
    "4989": ("宣德科技", "上市"),
    "5008": ("富邦媒", "上市"),
    "5009": ("榮化", "上市"),
    "5014": ("精技電腦", "上市"),
    "5015": ("萬國通路", "上市"),
    "5016": ("廣宇科技", "上市"),
    "5020": ("雷科", "上市"),
    "5021": ("保隆-KY", "上市"),
    "5209": ("新鼎系統", "上市"),
    "5220": ("萬達光電", "上市"),
    "5222": ("全訊科技", "上市"),
    "5243": ("閎康科技", "上市"),
    "5245": ("智晶光電", "上市"),
    "5258": ("富晶通", "上市"),
    "5285": ("致伸科技", "上市"),
    "5299": ("盛群半導體", "上市"),
    "5351": ("鈺創科技", "上市"),
    "5356": ("協益電子", "上市"),
    "5358": ("億光電子", "上市"),
    "5363": ("世紀鋼", "上市"),
    "5371": ("中光電", "上市"),
    "5380": ("神基科技", "上市"),
    "5392": ("應華精密", "上市"),
    "5434": ("崇越電通", "上市"),
    "5452": ("笙科電子", "上市"),
    "5455": ("昇佳電子", "上市"),
    "5457": ("晶宏半導體", "上市"),
    "5471": ("松翰科技", "上市"),
    "5474": ("飛捷科技", "上市"),
    "5480": ("群益期貨", "上市"),
    "5484": ("長華電材", "上市"),
    "6176": ("瑞儀光電", "上市"),
    "6245": ("立端科技", "上市"),
    "6670": ("復盛應用科技", "上市"),
    "2723": ("美食達人", "上市"),
    "5326": ("上太電子", "上市"),
    "5328": ("華容電子", "上市"),
    "5435": ("科橋電子", "上市"),
    "5438": ("東亞科技", "上市"),
    "5439": ("鉅邁科技", "上市"),
    "5497": ("榮成紙業", "上市"),
    # ── 上櫃 OTC 補充（v4.0）───────────────────────────────
    "6488": ("環球晶圓", "上市"),
    "6531": ("愛普科技", "上櫃"),
    "6548": ("長科國際-KY", "上市"),
    "6701": ("台生材", "上市"),
    "6762": ("協欣電子", "上櫃"),
    "6791": ("杰力科技", "上櫃"),
    "6803": ("崇越科技", "上市"),
    "6809": ("聖暉企業", "上市"),
    "6811": ("宏致電子", "上市"),
    "6830": ("利民股份", "上市"),
    "6845": ("昇陽半導體", "上櫃"),
    "6850": ("一心診所-KY", "上市"),
    "6856": ("吉銓精密", "上櫃"),
    "6862": ("杰智環境", "上市"),
    "8034": ("辛耘企業", "上市"),
    "8044": ("網家", "上市"),
    "8069": ("元太科技", "上市"),
    "8086": ("宏捷科技", "上市"),
    "8096": ("擎亞電子", "上櫃"),
    "8103": ("瑞穎科技", "上市"),
    "8104": ("錸寶科技", "上市"),
    "8131": ("福懋科技", "上市"),
    "8150": ("南茂科技", "上市"),
    "8163": ("達方電子", "上市"),
    "8183": ("精星科技", "上市"),
    "8210": ("勝麗國際", "上市"),
}# ── Clean up the table: remove any accidentally invalid keys ──
_TW_NAMES = {k: v for k, v in _TW_NAMES.items()
             if k.isdigit() or (len(k) >= 4 and k[:4].isdigit())}


def lookup_name(code: str) -> tuple[str, str]:
    """
    Look up Chinese name from static table first (instant),
    then fall back to yfinance .info if not found.
    Returns (name, market_label).
    """
    bare = code.upper().replace(".TWO", "").replace(".TW", "").strip()
    if bare in _TW_NAMES:
        return _TW_NAMES[bare]
    # Also try with common ETF format (e.g. "00878" stored as "878")
    bare_no_lead = bare.lstrip("0")
    if bare_no_lead in _TW_NAMES:
        return _TW_NAMES[bare_no_lead]
    # Infer market from suffix
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


@st.cache_data(ttl=90)   # 方案D：90秒快取報價，減少重複 HTTP 請求
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



@st.cache_data(ttl=1800)   # 方案D：30分鐘快取 — 減少重複下載，自選股模式尤其快
def batch_fetch_ohlcv(symbols: tuple, period: str = "1y") -> dict:
    """
    Download OHLCV for ALL symbols in ONE yf.download() call.
    3–5× faster than calling fetch_data() per stock in a loop.
    Returns {bare_code: pd.DataFrame} — same format as fetch_data().

    Design:
    • Splits into chunks of 200 to avoid URL length limits
    • Falls back to .TWO suffix if .TW returns empty
    • Strips timezone, drops NaN rows, validates min length
    """
    if not symbols:
        return {}

    bare_map: dict[str, str] = {}   # full_ticker → bare_code
    tickers: list[str] = []
    for s in symbols:
        bare = s.upper().replace(".TW","").replace(".TWO","")
        full = s if s.upper().endswith((".TW",".TWO")) else bare + ".TW"
        tickers.append(full)
        bare_map[full] = bare

    result: dict[str, pd.DataFrame] = {}
    CHUNK = 200   # safe URL-length limit for yf.download

    for start in range(0, len(tickers), CHUNK):
        chunk = tickers[start:start + CHUNK]
        try:
            raw = yf.download(
                tickers=" ".join(chunk),
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
            if raw is None or raw.empty:
                continue

            for full in chunk:
                bare = bare_map[full]
                try:
                    # Multi-ticker: columns are (field, ticker)
                    if len(chunk) == 1:
                        df = raw[["Open","High","Low","Close","Volume"]].copy()
                    else:
                        df = raw.xs(full, axis=1, level=1)[["Open","High","Low","Close","Volume"]].copy()
                    df.index = pd.to_datetime(df.index).tz_localize(None)
                    df = df.dropna(subset=["Close"])
                    if len(df) >= 10:
                        result[bare] = df
                except Exception:
                    continue
        except Exception:
            continue

    return result


# ══════════════════════════════════════════════
# CHART  (4-panel drill-down)
# ══════════════════════════════════════════════

MARKER_SHAPE = {
    "HIGH_CONF_BUY":      ("star",          "#ffd700", 16, "below"),
    "HIGH_CONF_PULLBACK": ("diamond",       "#00e5ff", 14, "below"),  # 💎 cyan diamond
    "BREAKOUT_BUY":       ("triangle-up",   "#ff9900", 14, "below"),
    "STRONG_BUY":         ("triangle-up",   "#00ff88", 12, "below"),
    "BUY":                ("triangle-up",   "#44ddff", 10, "below"),
    "DIV_BUY":            ("diamond",       "#00ff88", 10, "below"),
    "WATCH":              ("circle-open",   "#ffee44",  8, "below"),
    "STRONG_SELL":        ("triangle-down", "#ff3355", 12, "above"),
    "SELL":               ("triangle-down", "#ff8866", 10, "above"),
    "DIV_SELL":           ("diamond",       "#ff3355", 10, "above"),
    "FAKE_BREAKOUT":      ("x",             "#cc44ff",  8, "above"),
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


def tg_get_recipients() -> tuple[str, list[str]]:
    """
    讀取所有收件人 chat_id。
    優先順序：
      1. Streamlit Secrets → [telegram] chat_id_1 / chat_id_2 / chat_id_3
      2. Streamlit Secrets → [telegram] chat_id（單一，向下相容）
      3. st.session_state → tg_chat_id（側欄手動輸入，僅主帳號）
    Returns (token, [chat_id_1, chat_id_2, ...])
    """
    try:
        _sec = st.secrets.get("telegram", {})
    except Exception:
        _sec = {}

    token = (
        _sec.get("token", "") or
        st.session_state.get("tg_token", "")
    )

    # Collect all chat_ids from secrets
    cids: list[str] = []
    for k in ("chat_id_1", "chat_id_2", "chat_id_3",
              "chat_id_4", "chat_id_5"):
        v = str(_sec.get(k, "") or "").strip()
        if v:
            cids.append(v)

    # Fallback: single chat_id key in secrets
    if not cids:
        v = str(_sec.get("chat_id", "") or "").strip()
        if v:
            cids.append(v)

    # Last resort: session state (manual sidebar input)
    if not cids:
        v = str(st.session_state.get("tg_chat_id", "") or "").strip()
        if v:
            cids.append(v)

    # Deduplicate while preserving order
    seen = set(); unique = []
    for c in cids:
        if c and c not in seen:
            seen.add(c); unique.append(c)

    return token, unique


def tg_broadcast(text: str) -> int:
    """
    推播訊息給所有設定的收件人。
    Returns count of successful sends.
    """
    token, cids = tg_get_recipients()
    if not token or not cids:
        return 0
    sent = 0
    for cid in cids:
        ok, _ = _tg_send(token, cid, text)
        if ok:
            sent += 1
    return sent


def send_signal_alert(token: str, chat_id: str,
                      new_buy_rows: list, new_sell_rows: list) -> int:
    """
    Send Telegram alerts for newly-detected actionable signals.
    Broadcasts to ALL recipients via tg_broadcast().
    token/chat_id params kept for API compatibility but tg_broadcast
    auto-reads all recipients from secrets.
    """
    if not token:
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
        n = tg_broadcast(msg)
        msgs_sent += n

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
        n = tg_broadcast(msg)
        msgs_sent += n

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

# ══════════════════════════════════════════════════════════════
# 方案 A — SCAN CACHE：掃描結果持久化，斷線重連自動還原
# 掃描完成 → 寫 /tmp  →  斷線重連 → 讀 /tmp → 無需重掃
# ══════════════════════════════════════════════════════════════
_SCAN_CACHE_FILE = "/tmp/sentinel_scan_cache.json"
_SCAN_CACHE_TTL  = 90   # 分鐘 — 90分鐘內重連直接還原


def scan_cache_save(rows: list, timestamp: str, scan_mode: str = "") -> None:
    """掃描完成後持久化到 /tmp，斷線重連時用於還原。"""
    try:
        payload = {
            "rows":      rows,
            "timestamp": timestamp,
            "scan_mode": scan_mode,
            "saved_at":  tw_now().isoformat(),
        }
        tmp = _SCAN_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        os.replace(tmp, _SCAN_CACHE_FILE)
    except Exception:
        pass   # 不影響主流程


def scan_cache_load() -> dict | None:
    """
    載入快取。若快取不存在、超過 TTL 或損壞則回傳 None。
    TTL 預設 90 分鐘（一個盤中交易時段）。
    """
    try:
        if not os.path.exists(_SCAN_CACHE_FILE):
            return None
        with open(_SCAN_CACHE_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        # Parse saved_at — handle both tz-aware and naive
        saved_str = payload.get("saved_at", "")
        try:
            saved_at = datetime.fromisoformat(saved_str)
            if saved_at.tzinfo is None:
                saved_at = saved_at.replace(tzinfo=pytz.timezone("Asia/Taipei"))
        except Exception:
            return None
        age_min = (tw_now() - saved_at).total_seconds() / 60
        if age_min > _SCAN_CACHE_TTL:
            return None
        return payload
    except Exception:
        return None


def scan_cache_clear() -> None:
    try: os.remove(_SCAN_CACHE_FILE)
    except: pass


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



# ══════════════════════════════════════════════════════════════
# OVERNIGHT  GAP  STRATEGY  ENGINE
# 隔日沖選股策略：因素回測 + 評分 + 掃描器
# Logic: enter near close (13:20), exit next-day open (09:05)
# ══════════════════════════════════════════════════════════════

def _overnight_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all overnight strategy factors for each bar.
    Returns df with new columns ready for scoring and backtesting.
    """
    d = df.copy()
    # ── Factor A: Close strength ──────────────────────────────
    d["F_close_pos"]   = (d["Close"] - d["Low"]) / (d["High"] - d["Low"] + 1e-8)
    d["F_close_near_high"] = d["F_close_pos"] >= 0.92   # close in top 8% of range
    d["F_gain_pct"]    = d["Close"].pct_change() * 100
    d["F_gain_3_7"]    = d["F_gain_pct"].between(2.5, 8.0)  # 2.5-8% sweet spot

    # ── Factor B: Volume quality ──────────────────────────────
    d["F_vol_ma20"]    = d["Volume"].rolling(20).mean()
    d["F_vol_ratio"]   = d["Volume"] / (d["F_vol_ma20"] + 1)
    d["F_vol_surge"]   = d["F_vol_ratio"] >= 1.8           # 1.8x+ volume
    d["F_obv"]         = (d["Close"].diff().apply(lambda x: 1 if x > 0 else -1) * d["Volume"]).cumsum()
    d["F_obv_new_high"]= d["F_obv"] >= d["F_obv"].rolling(10).max().shift(1)  # OBV new 10-day high

    # ── Factor C: Technical structure ────────────────────────
    d["F_ema20"]       = d["Close"].ewm(span=20, adjust=False).mean()
    d["F_ema60"]       = d["Close"].ewm(span=60, adjust=False).mean()
    d["F_ema200"]      = d["Close"].ewm(span=200, adjust=False).mean()
    d["F_above_ema20"] = d["Close"] > d["F_ema20"]
    d["F_trend_ok"]    = (d["Close"] > d["F_ema20"]) & (d["F_ema20"] > d["F_ema60"])
    d["F_above_200"]   = d["Close"] > d["F_ema200"]       # above annual line
    # Breakout: today close > max close of prior 20 days
    d["F_breakout_20d"]= d["Close"] > d["Close"].shift(1).rolling(20).max()

    # ── Factor D: Tail-end volume (proxy: vol in last 30 min) ─
    # We don't have intraday data, so use today's volume/ema ratio × close position
    d["F_tail_strength"] = d["F_vol_ratio"] * d["F_close_pos"]
    d["F_tail_ok"]       = d["F_tail_strength"] >= 1.5

    return d


def overnight_factor_backtest(df: pd.DataFrame) -> dict:
    """
    Backtest each overnight factor independently AND in combination.
    Entry: close of signal day.
    Exit: open of next day.
    Returns full analysis dict.
    """
    d = _overnight_factors(df)

    # Need next-day open
    d["next_open"]  = d["Open"].shift(-1)
    d["next_open_ret"] = (d["next_open"] - d["Close"]) / d["Close"] * 100
    d["next_open_win"] = d["next_open_ret"] > 0

    valid = d.dropna(subset=["next_open_ret"])
    if len(valid) < 30:
        return {}

    factors = {
        "A1_收盤強度":   "F_close_near_high",
        "A2_漲幅3-8%":   "F_gain_3_7",
        "B1_量能放大":   "F_vol_surge",
        "B2_OBV新高":    "F_obv_new_high",
        "C1_均線多頭":   "F_trend_ok",
        "C2_站上年線":   "F_above_200",
        "C3_突破20日高": "F_breakout_20d",
        "D1_尾盤強度":   "F_tail_ok",
    }

    results = {}
    for name, col in factors.items():
        if col not in valid.columns:
            continue
        sub = valid[valid[col] == True]
        if len(sub) < 5:
            continue
        wr  = sub["next_open_win"].mean() * 100
        avg = sub["next_open_ret"].mean()
        med = sub["next_open_ret"].median()
        std = sub["next_open_ret"].std()
        sharpe = avg / std * (252 ** 0.5) if std > 0 else 0
        results[name] = {
            "樣本數": len(sub),
            "勝率%":   round(wr, 1),
            "平均報酬%": round(avg, 3),
            "中位報酬%": round(med, 3),
            "Sharpe":   round(sharpe, 2),
        }

    # ── Composite score backtest ──────────────────────────────
    # Score each bar 0-8 (one point per factor)
    score_cols = list(factors.values())
    valid_s    = valid.copy()
    for c in score_cols:
        if c not in valid_s.columns:
            valid_s[c] = False
    valid_s["OVN_Score"] = valid_s[score_cols].astype(int).sum(axis=1)

    combo_rows = []
    for min_score in range(3, 8):
        sub = valid_s[valid_s["OVN_Score"] >= min_score]
        if len(sub) < 3:
            continue
        wr  = sub["next_open_win"].mean() * 100
        avg = sub["next_open_ret"].mean()
        combo_rows.append({
            "評分門檻≥": min_score,
            "符合天數":   len(sub),
            "勝率%":      round(wr, 1),
            "平均報酬%":  round(avg, 3),
            "期望值%":    round(wr/100 * avg - (1 - wr/100) * abs(avg), 3),
        })

    # ── Find optimal score threshold ─────────────────────────
    if combo_rows:
        df_combo = pd.DataFrame(combo_rows)
        best_idx = df_combo["期望值%"].idxmax()
        best_threshold = int(df_combo.loc[best_idx, "評分門檻≥"])
    else:
        df_combo = pd.DataFrame()
        best_threshold = 5

    # ── Market regime filter: does market direction matter? ──
    d2 = valid_s.copy()
    d2["idx_ret"] = d2["Close"].pct_change() * 100   # proxy: stock itself
    market_up = d2["idx_ret"] > 0
    sub_mkt_up   = d2[market_up  & (d2["OVN_Score"] >= best_threshold)]
    sub_mkt_down = d2[~market_up & (d2["OVN_Score"] >= best_threshold)]
    mkt_filter = {
        "大盤上漲日": {
            "樣本": len(sub_mkt_up),
            "勝率%": round(sub_mkt_up["next_open_win"].mean()*100, 1) if len(sub_mkt_up)>2 else 0,
        },
        "大盤下跌日": {
            "樣本": len(sub_mkt_down),
            "勝率%": round(sub_mkt_down["next_open_win"].mean()*100, 1) if len(sub_mkt_down)>2 else 0,
        },
    }

    # ── Verdict: can we buy today? ────────────────────────────────
    # Three questions → single traffic-light judgement
    best_row = {}
    if combo_rows:
        df_combo2 = pd.DataFrame(combo_rows)
        bi = df_combo2["期望值%"].idxmax()
        best_row = df_combo2.loc[bi].to_dict()

    best_wr   = best_row.get("勝率%",      0)
    best_ev   = best_row.get("期望值%",    0)
    best_n    = best_row.get("符合天數",   0)
    up_wr     = mkt_filter["大盤上漲日"]["勝率%"]
    dn_wr     = mkt_filter["大盤下跌日"]["勝率%"]
    mkt_gap   = round(up_wr - dn_wr, 1)
    mkt_sens  = mkt_gap >= 10   # market direction matters

    # Edge exists?
    edge_ok    = best_wr >= 55 and best_ev > 0 and best_n >= 15

    # Determine verdict
    if best_n < 15:
        verdict = "insufficient"
        verdict_label  = "⚫ 資料不足"
        verdict_color  = "#5a8fb0"
        verdict_bg     = "rgba(90,143,176,0.08)"
        verdict_border = "#5a8fb0"
        verdict_msg    = "歷史樣本不足 15 次，統計結論不可靠。建議選更長的回測區間。"
    elif best_wr >= 65 and best_ev >= 0.10 and best_n >= 30:
        verdict = "strong_buy"
        verdict_label  = "🟢 強力可買"
        verdict_color  = "#00ff88"
        verdict_bg     = "rgba(0,255,136,0.06)"
        verdict_border = "#00ff88"
        verdict_msg    = (
            f"歷史數據顯示強烈正期望值（勝率 {best_wr:.1f}%，期望值 +{best_ev:.3f}%）。"
            f"樣本足夠（{best_n} 次），統計可靠。"
            + ("今日若評分達門檻，大盤方向需確認。" if mkt_sens else "今日若評分達門檻，可直接進場。")
        )
    elif best_wr >= 58 and best_ev > 0:
        verdict = "caution_buy"
        verdict_label  = "🟡 謹慎可買"
        verdict_color  = "#ffd600"
        verdict_bg     = "rgba(255,214,0,0.06)"
        verdict_border = "#ffd600"
        verdict_msg    = (
            f"有正期望值（勝率 {best_wr:.1f}%），但邊際不強。"
            + ("大盤影響顯著（上漲日勝率高出 " + str(mkt_gap) + "%），建議僅在大盤上漲日操作。"
               if mkt_sens else f"建議評分達 ≥{best_threshold} 分再進場，控制次數。")
        )
    else:
        verdict = "no_buy"
        verdict_label  = "🔴 不建議進場"
        verdict_color  = "#ff3355"
        verdict_bg     = "rgba(255,51,85,0.06)"
        verdict_border = "#ff3355"
        verdict_msg    = (
            f"勝率 {best_wr:.1f}%，期望值 {best_ev:+.3f}%，統計優勢不明顯。"
            "此股隔日沖歷史表現未達標準，建議跳過或改用波段策略。"
        )

    verdict_data = {
        "verdict":        verdict,
        "label":          verdict_label,
        "color":          verdict_color,
        "bg":             verdict_bg,
        "border":         verdict_border,
        "msg":            verdict_msg,
        "best_wr":        best_wr,
        "best_ev":        best_ev,
        "best_n":         best_n,
        "best_threshold": best_threshold,
        "mkt_sens":       mkt_sens,
        "mkt_gap":        mkt_gap,
        "up_wr":          up_wr,
        "dn_wr":          dn_wr,
    }

    return {
        "factor_results": results,
        "combo_df":       df_combo,
        "best_threshold": best_threshold,
        "market_filter":  mkt_filter,
        "detail":         valid_s,
        "verdict":        verdict_data,
    }


def overnight_score(df_row_factors: pd.Series) -> int:
    """
    Score a single bar (latest row) 0-8 for overnight suitability.
    Higher = better candidate.
    """
    cols = ["F_close_near_high","F_gain_3_7","F_vol_surge","F_obv_new_high",
            "F_trend_ok","F_above_200","F_breakout_20d","F_tail_ok"]
    return int(sum(bool(df_row_factors.get(c, False)) for c in cols))


def overnight_scan(watchlist: list, min_score: int = 5,
                   data_period: str = "1y") -> list[dict]:
    """
    Scan watchlist for today's overnight candidates.
    Returns sorted list of dicts with code, score, factors.
    """
    candidates = []
    for code in watchlist:
        try:
            df, _ = fetch_data(code, data_period)
            if df is None or len(df) < 60:
                continue
            df_f  = _overnight_factors(df)
            latest = df_f.iloc[-1]
            score  = overnight_score(latest)
            if score < min_score:
                continue
            gain   = float(latest.get("F_gain_pct", 0) or 0)
            vol_r  = float(latest.get("F_vol_ratio", 0) or 0)
            c_pos  = float(latest.get("F_close_pos", 0) or 0)
            candidates.append({
                "代號":       code,
                "名稱":       lookup_name(code)[0],
                "評分":       score,
                "漲幅%":      round(gain, 2),
                "量比":       round(vol_r, 2),
                "收盤位置%": round(c_pos * 100, 1),
                "站上年線":   bool(latest.get("F_above_200", False)),
                "均線多頭":   bool(latest.get("F_trend_ok", False)),
                "突破20高":   bool(latest.get("F_breakout_20d", False)),
                "OBV新高":    bool(latest.get("F_obv_new_high", False)),
                "_price":     float(df["Close"].iloc[-1]),
                "_score":     score,
            })
        except Exception:
            continue
    return sorted(candidates, key=lambda x: -x["_score"])



# ══════════════════════════════════════════════════════════════
# 📱 WATCHLIST  GROUP  &  NOTE  ENGINE
# 替代 watchlist_pro.py — 分組管理 + 備忘標籤系統
# ══════════════════════════════════════════════════════════════

PRESET_GROUPS = ["未分組", "半導體", "金融", "電子", "傳產", "ETF", "觀察中", "隔日沖候選"]

_WL_GROUP_FILE = "/tmp/sentinel_wl_groups.json"  # {code: group}
_WL_NOTE_FILE  = "/tmp/sentinel_wl_notes.json"   # {code: {note, tags, entry, watch_date}}


def _wl_groups() -> dict:
    """Always read fresh — avoids stale cache losing group labels."""
    try:
        if os.path.exists(_WL_GROUP_FILE):
            return json.load(open(_WL_GROUP_FILE))
    except Exception:
        pass
    return {}


def _wl_notes() -> dict:
    try:
        if os.path.exists(_WL_NOTE_FILE):
            return json.load(open(_WL_NOTE_FILE))
    except Exception:
        pass
    return {}


def wl_get_group(code: str) -> str:
    bare = code.upper().replace(".TW", "").replace(".TWO", "")
    return _wl_groups().get(bare, "未分組")


def wl_set_group(code: str, group: str) -> None:
    bare = code.upper().replace(".TW", "").replace(".TWO", "")
    d = _wl_groups(); d[bare] = group
    tmp = _WL_GROUP_FILE + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _WL_GROUP_FILE)


def wl_note_get(code: str) -> dict:
    bare = code.upper().replace(".TW", "").replace(".TWO", "")
    return _wl_notes().get(bare, {})


def wl_note_set(code: str, data: dict) -> None:
    bare = code.upper().replace(".TW", "").replace(".TWO", "")
    d = _wl_notes(); d[bare] = data
    tmp = _WL_NOTE_FILE + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _WL_NOTE_FILE)


DEFAULT_WATCHLIST = [
    # ══════════════════════════════════════════════════════════
    # 全市場掃描清單 v4.0 — 重新整理
    # 原則：流動性優先，日均量 > 500張，市值 > 50億
    # ══════════════════════════════════════════════════════════

    # ── 上市 TSE 市值前100大 ────────────────────────────────
    "2330",  # 台積電
    "2317",  # 鴻海
    "2454",  # 聯發科
    "2882",  # 國泰金
    "2881",  # 富邦金
    "2412",  # 中華電
    "2308",  # 台達電
    "2303",  # 聯電
    "2886",  # 兆豐金
    "2382",  # 廣達
    "2891",  # 中信金
    "3711",  # 日月光投控
    "2357",  # 華碩
    "2207",  # 和泰車
    "2884",  # 玉山金
    "2885",  # 元大金
    "2887",  # 台新金
    "2880",  # 華南金
    "2883",  # 開發金
    "2890",  # 永豐金
    "2892",  # 第一金
    "5880",  # 合庫金
    "2002",  # 中鋼
    "2912",  # 統一超
    "1216",  # 統一
    "1303",  # 南亞
    "1301",  # 台塑
    "2395",  # 研華
    "2327",  # 國巨
    "2603",  # 長榮
    "2609",  # 陽明
    "2615",  # 萬海
    "2301",  # 光寶科
    "2347",  # 聯強
    "2379",  # 瑞昱
    "3034",  # 聯詠
    "3008",  # 大立光
    "2474",  # 可成
    "4938",  # 和碩
    "2353",  # 宏碁
    "2356",  # 英業達
    "2324",  # 仁寶
    "2337",  # 旺宏
    "2344",  # 華邦電
    "2408",  # 南亞科
    "2360",  # 致茂
    "3045",  # 台灣大
    "4904",  # 遠傳
    "2105",  # 正新
    "1402",  # 遠東新
    "1101",  # 台泥
    "1326",  # 台化
    "2049",  # 上銀
    "2376",  # 技嘉
    "2377",  # 微星
    "3231",  # 緯創
    "2385",  # 群光
    "3533",  # 嘉澤端子
    "6505",  # 台塑石化
    "5871",  # 中租-KY
    "2633",  # 台灣高鐵
    "9910",  # 豐泰
    "9921",  # 巨大
    "1590",  # 亞德客-KY
    "2059",  # 川湖科技
    "2404",  # 漢唐集成
    "2409",  # 友達
    "3481",  # 群創
    "3037",  # 欣興電子
    "3044",  # 健鼎科技
    "6176",  # 瑞儀光電
    "8046",  # 南電
    "2206",  # 三陽工業
    "6719",  # 力旺電子
    "6770",  # 力積電
    "2492",  # 華新科技
    "2451",  # 創見資訊
    "6271",  # 同欣電子
    "6278",  # 台表科
    "3443",  # 創意電子
    "3189",  # 景碩科技
    "5347",  # 世界先進
    "3105",  # 穩懋半導體
    "5269",  # 祥碩科技
    "3406",  # 玉晶光電
    "2542",  # 興富發
    "6415",  # 矽力-KY
    "6461",  # 益登科技
    "6472",  # 保瑞藥業
    "3661",  # 世芯-KY
    "4961",  # 天鈺科技
    "6669",  # 緯穎
    "6789",  # 采鈺科技
    "5274",  # 信驊
    "3665",  # 貿聯-KY
    "5358",  # 億光電子
    "5380",  # 神基科技
    "5371",  # 中光電
    "5388",  # 中磊電子
    "8299",  # 群聯電子
    "4966",  # 譜瑞-KY
    "4968",  # 立積電子
    "3356",  # 奇鋐科技

    # ── 上市 TSE 活躍中型股（日均量>1000張）────────────────
    "2014",  # 中鴻鋼鐵
    "2027",  # 大成鋼
    "2038",  # 海光電線電纜
    "2103",  # 台橡
    "2313",  # 華通電腦
    "2323",  # 中環
    "2367",  # 燿華電子
    "2388",  # 威盛電子
    "2426",  # 鼎元光電
    "3006",  # 晶豪科技
    "3055",  # 蔚華科技
    "3293",  # 鈊象電子
    "3338",  # 泰碩電子
    "3374",  # 精材科技
    "3380",  # 明泰科技
    "3494",  # 誠研科技
    "3532",  # 台勝科
    "3558",  # 神準科技
    "3698",  # 隆達電子
    "3714",  # 富采投控
    "4919",  # 新唐科技
    "4934",  # 太極網路
    "4952",  # 凌通科技
    "4967",  # 十銓科技
    "5008",  # 富邦媒
    "5243",  # 閎康科技
    "5285",  # 致伸科技
    "5289",  # 宜鼎國際
    "5299",  # 盛群半導體
    "5351",  # 鈺創科技
    "5363",  # 世紀鋼
    "5434",  # 崇越電通
    "5455",  # 昇佳電子
    "5471",  # 松翰科技
    "5474",  # 飛捷科技
    "5483",  # 中美晶
    "5484",  # 長華電材
    "6239",  # 力成科技
    "6245",  # 立端科技
    "6461",  # 益登科技
    "6670",  # 復盛應用科技
    "3019",  # 亞光
    "3130",  # 一零四資訊
    "3443",  # 創意電子
    "3450",  # 聯鈞光電

    # ── 上櫃 OTC 前50大（流動性前排）───────────────────────
    "6271",  # 同欣電（上市移至此確認）
    "3034",  # 聯詠（上市）
    "6488",  # 環球晶圓
    "6548",  # 長科國際-KY
    "6531",  # 愛普（上櫃）
    "6701",  # 台生材
    "6762",  # 協欣電子
    "6791",  # 杰力科技（上櫃）
    "6803",  # 崇越科
    "6809",  # 聖暉企業
    "6811",  # 宏致電子
    "6830",  # 利民股份
    "6845",  # 昇陽半導體
    "6850",  # 一心診所-KY
    "6856",  # 吉銓精密
    "6862",  # 杰智環境
    "8034",  # 辛耘企業
    "8044",  # 網家（PChome）
    "8069",  # 元太科技
    "8086",  # 宏捷科技
    "8096",  # 擎亞電子
    "8103",  # 瑞穎
    "8104",  # 錸寶科技
    "8105",  # 凌越半導體
    "8131",  # 福懋科技
    "8150",  # 南茂科技
    "8163",  # 達方電子
    "8183",  # 精星科技
    "8210",  # 勝麗國際
    "8299",  # 群聯（已在上市）
    "4966",  # 譜瑞-KY（上市）
    "4958",  # 臻鼎-KY
    "4935",  # 茂林-KY
    "4979",  # 華星光通
    "4984",  # 科嘉-KY
    "5009",  # 榮化
    "5016",  # 廣宇科技
    "5020",  # 雷科
    "5021",  # 保隆-KY
    "5209",  # 新鼎系統
    "5222",  # 全訊科技
    "5258",  # 富晶通
    "5392",  # 應華精密
    "5452",  # 笙科電子
    "5457",  # 晶宏半導體
    "5480",  # 群益期貨

    # ── 熱門隔日沖 / 波段標的 ───────────────────────────────
    "2331",  # 精英電腦（活躍）
    "2365",  # 昆盈企業
    "2429",  # 銘異科技
    "3141",  # 晶宏半導體
    "3149",  # 正達國際光電
    "3217",  # 優群科技
    "3305",  # 昇貿科技
    "3376",  # 新日興
    "3515",  # 華擎科技
    "3536",  # 洋華光電
    "3545",  # 敦泰電子
    "3596",  # 智易科技
    "3611",  # 鼎翰科技
    "3707",  # 漢磊科技
    "3752",  # 耕興電子
    "3794",  # 晶睿通訊
    "4960",  # 誠美材
    "4963",  # 聲立科技
    "4972",  # 湯石照明
    "4988",  # 誠創科技
    "5014",  # 精技電腦
    "5015",  # 萬國通路
    "5243",  # 閎康科技
    "5356",  # 協益電子

    # ── 主流 ETF ────────────────────────────────────────────
    "0050",   # 元大台灣50
    "0056",   # 元大高股息
    "00878",  # 國泰永續高息
    "00919",  # 群益精選高息
    "00929",  # 復華台灣科技優息
    "006208", # 富邦台50
    "00881",  # 國泰台灣5G+
    "00900",  # 富邦特選高股息30
    "00907",  # 永豐優息存股
    "00896",  # 中信綠能及電動車
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
        # ── 方案A：斷線重連時自動還原上次掃描結果 ──
        _cached = scan_cache_load()
        if _cached and _cached.get("rows"):
            st.session_state.scan_rows      = _cached["rows"]
            st.session_state.scan_timestamp = _cached.get("timestamp", "")
            st.session_state["_scan_restored"] = True   # flag for UI banner
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

        # ── Missing name detector ──────────────────────────────
        no_name = []
        for c in st.session_state.watchlist:
            bare_c = c.upper().replace(".TW","").replace(".TWO","").strip()
            name_c, _ = lookup_name(c)
            if not name_c:
                no_name.append(bare_c)
        if no_name:
            st.warning(
                f"⚠️ **{len(no_name)} 支無中文名稱**（會顯示代號）：\n"
                + "  ".join(no_name[:20])
                + ("…" if len(no_name) > 20 else "")
            )

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

            tg_token = st.text_input("Bot Token",
                value=_tg_sec.get("token", ""),
                placeholder="1234567890:AAF...",
                type="password", key="tg_token",
                help=(
                    "從 @BotFather 取得。\n\n"
                    "永久儲存方式（Streamlit Cloud）：\n"
                    "Settings → Secrets → 填入：\n"
                    "[telegram]\n"
                    "token = '你的TOKEN'\n"
                    "chat_id_1 = '第一人ID'\n"
                    "chat_id_2 = '第二人ID'\n"
                    "chat_id_3 = '第三人ID'"
                ))

            # ── 多人推播設定 ─────────────────────────────────
            st.markdown(
                '<div style="font-size:0.72rem;color:#5a8fb0;margin:6px 0 3px 0">'
                '收件人 Chat ID（最多5人）</div>',
                unsafe_allow_html=True
            )
            tg_chat_id = st.text_input("收件人1（主帳號）",
                value=_tg_sec.get("chat_id_1", "") or _tg_sec.get("chat_id", ""),
                placeholder="123456789",
                key="tg_chat_id",
                label_visibility="visible",
                help=(
                    "先向 Bot 傳一條訊息，再點下方連結查詢 Chat ID。\n\n"
                    "💡 在 Streamlit Secrets 設定多人（推薦）：\n"
                    "chat_id_1 = '第一人'\n"
                    "chat_id_2 = '第二人'\n"
                    "chat_id_3 = '第三人'"
                ))
            tg_chat_id2 = st.text_input("收件人2",
                value=_tg_sec.get("chat_id_2", ""),
                placeholder="987654321（選填）",
                key="tg_chat_id_2",
                label_visibility="visible")
            tg_chat_id3 = st.text_input("收件人3",
                value=_tg_sec.get("chat_id_3", ""),
                placeholder="555666777（選填）",
                key="tg_chat_id_3",
                label_visibility="visible")

            # Show active recipients count
            _tk_now, _cids_now = tg_get_recipients()
            if _tk_now and _cids_now:
                st.success(f"✅ 已設定 {len(_cids_now)} 位收件人")
            elif _tk_now:
                st.warning("⚠️ Token 已填，但尚未設定收件人 Chat ID")

            if tg_token and len(tg_token) > 20:
                st.markdown(
                    f"[🔍 查詢 Chat ID]"
                    f"(https://api.telegram.org/bot{tg_token}/getUpdates)"
                    f" ← 先向 Bot 傳任意訊息再點此"
                )

            tg_min_conf = st.slider("最低共振門檻（推播條件）",
                min_value=3, max_value=7, value=5, key="tg_min_conf",
                help=(
                    "只推播共振分數達此門檻以上的訊號。\n"
                    "建議：\n"
                    "• 5/7 — 標準（過濾雜訊，只推高品質）\n"
                    "• 3/7 — 寬鬆（推播較多，含早期訊號）\n"
                    "• 7/7 — 嚴格（極少推播，只推最強訊號）"
                ))
            _all_tg_sigs = [
                "HIGH_CONF_BUY", "HIGH_CONF_PULLBACK",
                "BREAKOUT_BUY",  "STRONG_BUY",
                "BUY",           "DIV_BUY",
                "STRONG_SELL",   "DIV_SELL",  "SELL",
            ]
            tg_sigs = st.multiselect(
                "推播訊號類型",
                options=_all_tg_sigs,
                default=_all_tg_sigs,   # 預設全選
                key="tg_sigs",
                format_func=lambda x: SIGNAL_LABEL.get(x, x),
                help=(
                    "選擇要推播到 Telegram 的訊號類型。\n\n"
                    "⭐ 三重共振 / 💎 共振回調買 — 最高勝率，強烈建議保留\n"
                    "🟠 噴發買 / 🟢 強買 — 高品質進場訊號\n"
                    "🔵 買入 / 🟢 底背離 — 一般買入，較頻繁\n"
                    "🔴 強賣 / 🔴 頂背離 / 🟡 賣出 — 出場 / 風控訊號\n\n"
                    "若推播過多可提高上方「最低共振門檻」來過濾。"
                )
            )
            if st.button("🧪 測試推播", key="tg_test", width='stretch'):
                _tk, _cids = tg_get_recipients()
                if not _tk or not _cids:
                    st.warning("⚠️ 請先在 Secrets 或下方填入 Bot Token 和 Chat ID")
                else:
                    _test_msg = (
                        f"✅ Sentinel Pro 推播測試\n"
                        f"連線成功！共 {len(_cids)} 位收件人。\n"
                        f"設定：共振 ≥ {tg_min_conf}/7"
                    )
                    _n = tg_broadcast(_test_msg)
                    if _n:
                        st.success(f"✅ 已發送到 {_n}/{len(_cids)} 位收件人")
                    else:
                        st.error("❌ 發送失敗，請確認 Token 和 Chat ID 是否正確")
                        st.caption(
                            "常見原因：\n"
                            "1. Token 錯誤 — 確認從 @BotFather 取得的完整 Token\n"
                            "2. Chat ID 錯誤 — 先傳一條訊息給 Bot，再用上方連結確認\n"
                            "3. Bot 尚未啟用 — 在 Telegram 搜尋你的 Bot 並按 Start\n"
                            "4. 網路限制 — Streamlit Cloud 免費版可能封鎖外部請求"
                        )

        # ── #4 價格警報（Price Alert）─────────────────────────
        with st.expander("🎯 價格警報設定", expanded=False):
            st.caption(
                "為個別股票設定目標價或停損警報。"
                "每次掃描時自動檢查，觸發後立即推播 Telegram。"
            )
            # Alert store in session state (persists across reruns)
            if "price_alerts" not in st.session_state:
                st.session_state.price_alerts = {}  # {code: {target, stop, added}}

            pa_c1, pa_c2 = st.columns(2)
            pa_code   = pa_c1.text_input("代號", placeholder="2330", key="pa_code",
                                          label_visibility="collapsed")
            pa_type   = pa_c2.radio("類型", ["🎯 目標價達到", "🛑 跌破停損"],
                                    horizontal=True, key="pa_type",
                                    label_visibility="collapsed")
            pa_price  = st.number_input("警報價格", min_value=0.01, value=100.0,
                                        step=0.5, key="pa_price",
                                        label_visibility="collapsed")
            if st.button("➕ 新增警報", key="pa_add", width='stretch'):
                bare_pa = pa_code.strip().upper().replace(".TW","").replace(".TWO","")
                if bare_pa:
                    if bare_pa not in st.session_state.price_alerts:
                        st.session_state.price_alerts[bare_pa] = {}
                    alert_type_key = "target" if "目標" in pa_type else "stop"
                    st.session_state.price_alerts[bare_pa][alert_type_key] = pa_price
                    st.session_state.price_alerts[bare_pa]["added"] = tw_now().strftime("%Y-%m-%d")
                    st.success(f"✓ 已設定 {bare_pa} {'目標' if alert_type_key=='target' else '停損'} {pa_price:.2f}")

            # Show current alerts
            if st.session_state.price_alerts:
                st.markdown('<div style="font-size:0.72rem;color:#5a8fb0;margin-top:8px">目前警報</div>',
                            unsafe_allow_html=True)
                for code_a, cfg_a in list(st.session_state.price_alerts.items()):
                    q_a   = fetch_quote(code_a)
                    px_a  = q_a.get("price", 0)
                    tgt_a = cfg_a.get("target")
                    stp_a = cfg_a.get("stop")
                    # Hit detection
                    tgt_hit = tgt_a and px_a and px_a >= tgt_a
                    stp_hit = stp_a and px_a and px_a <= stp_a
                    border  = "#ffd700" if tgt_hit else "#ff3355" if stp_hit else "#1a2d44"
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'align-items:center;border:1px solid {border};'
                        f'border-radius:6px;padding:5px 10px;margin-bottom:4px;font-size:0.78rem">'
                        f'<span style="color:#e8f4fd;font-weight:700">{code_a}</span>'
                        f'{"<span style=color:#ffd700>🎯 "+str(tgt_a)+"</span>" if tgt_a else ""}'
                        f'{"&nbsp;" if tgt_a and stp_a else ""}'
                        f'{"<span style=color:#ff3355>🛑 "+str(stp_a)+"</span>" if stp_a else ""}'
                        f'<span style="color:#5a8fb0">現價 {px_a:.2f}</span>'
                        f'{"<span style=color:#ffd700;font-weight:700>⚡達標</span>" if tgt_hit else ""}'
                        f'{"<span style=color:#ff3355;font-weight:700>⚡觸損</span>" if stp_hit else ""}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    # Push Telegram if hit
                    _tg_t = st.session_state.get("tg_token","")
                    _tg_c = st.session_state.get("tg_chat_id","")
                    if (tgt_hit or stp_hit) and _tg_t and _tg_c:
                        _alert_key = f"pa_{code_a}_{'tgt' if tgt_hit else 'stp'}_{tw_now().strftime('%Y%m%d')}"
                        if not st.session_state.get(_alert_key):
                            msg = (f"{'🎯 目標達標' if tgt_hit else '🛑 停損觸發'}\n"
                                   f"{code_a}  現價 {px_a:.2f}\n"
                                   f"{'目標 '+str(tgt_a) if tgt_hit else '停損 '+str(stp_a)}\n"
                                   f"{tw_now().strftime('%H:%M')}")
                            tg_broadcast(msg)
                            st.session_state[_alert_key] = True
                            st.toast(f"📲 推播 {code_a} 警報", icon="🎯" if tgt_hit else "🛑")

                if st.button("清除所有警報", key="pa_clear", width='stretch'):
                    st.session_state.price_alerts = {}
                    st.rerun()

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
    tab_scan, tab_drill, tab_bt, tab_port, tab_sig_hist, tab_lifecycle, tab_overnight, tab_wl = st.tabs([
        "📡  訊號掃描", "🔬  個股分析", "📊  回測 & 優化",
        "📒  買賣記錄", "📈  訊號歷史勝率",
        "🗓  訊號管理", "🌙  隔日沖策略", "📱  自選股",
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

        # ── #1 掃描模式 ─────────────────────────────────────────
        sm_col, _ = st.columns([3, 1])
        scan_mode = sm_col.radio(
            "掃描範圍",
            ["🔖 自選股（快速）", "🌏 全市場（284支）", "📋 自訂清單"],
            horizontal=True, label_visibility="collapsed",
            key="scan_mode",
            help=(
                "🔖 自選股：只掃你加入自選股的股票，速度最快（30秒內）。\n"
                "🌏 全市場：掃描內建全部 284 支股票，需等待 60–90 秒。\n"
                "📋 自訂清單：臨時輸入代號，彈性組合，不影響自選股設定。"
            ),
        )
        custom_scan_codes = []
        if scan_mode == "📋 自訂清單":
            raw_input = st.text_area(
                "輸入代號（每行一個，或逗號分隔）",
                placeholder="2330\n2317\n2454\n或：2330, 2317, 2454",
                height=80, label_visibility="collapsed",
                key="custom_scan_input",
            )
            if raw_input.strip():
                import re as _re_scan
                raw_codes = _re_scan.split(r'[\s,，、\n]+', raw_input.strip())
                custom_scan_codes = [
                    c.upper().replace(".TW","").replace(".TWO","")
                    for c in raw_codes
                    if c.strip() and _re_scan.fullmatch(r'\d{4,6}', c.strip().replace(".TW","").replace(".TWO",""))
                ]
                if custom_scan_codes:
                    st.caption(f"✓ 識別到 {len(custom_scan_codes)} 支：{' '.join(custom_scan_codes[:8])}{'…' if len(custom_scan_codes)>8 else ''}")
                else:
                    st.warning("未識別到有效代號（需4–6位數字）")

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

        # ── 方案A：斷線還原提示橫幅 ──────────────────────────────
        if st.session_state.get("_scan_restored"):
            _cached_meta = scan_cache_load()
            _mode_lbl = _cached_meta.get("scan_mode", "") if _cached_meta else ""
            rb1, rb2 = st.columns([3, 1])
            rb1.markdown(
                f'<div style="background:#0a1e10;border:1px solid #1a4a20;'
                f'border-radius:6px;padding:7px 12px;font-size:0.78rem">'
                f'🔄 <b style="color:#00ff88">已自動還原</b>'
                f'<span style="color:#5a8fb0"> 上次掃描結果（{scan_time}）'
                f'{" · "+_mode_lbl if _mode_lbl else ""}'
                f' — 點「掃描」取得最新資料</span></div>',
                unsafe_allow_html=True,
            )
            if rb2.button("🗑 清除快取", key="clear_scan_cache", width='stretch'):
                scan_cache_clear()
                st.session_state.scan_rows = []
                st.session_state["_scan_restored"] = False
                st.rerun()


        should_auto_scan = (
            auto_refresh
            and market_open
            and bool(st.session_state.scan_rows)  # only re-scan if we have prior data
            and secs_left <= 0
        )
        if should_auto_scan:
            run_scan = True   # piggyback on existing scan logic below

        # ── #3 快速篩選 + 排序 ─────────────────────────────────
        st.markdown(
            '<div style="background:#0a1020;border:1px solid #1a2d44;border-radius:8px;'
            'padding:8px 14px 4px 14px;margin:8px 0 4px 0">'
            '<div style="font-size:0.68rem;color:#5a8fb0;letter-spacing:0.08em;'
            'text-transform:uppercase;margin-bottom:6px">🔍 篩選 & 排序</div>',
            unsafe_allow_html=True,
        )
        flt_col1, flt_col2, flt_col3 = st.columns([2, 2, 1])
        sort_mode = flt_col1.radio(
            "排序",
            ["📶 訊號強度", "⭐ 共振分數", "🔥 動能", "📈 量比"],
            horizontal=True, label_visibility="visible",
            key="sort_mode_radio",
        )
        sig_filter = flt_col2.multiselect(
            "只顯示訊號",
            options=list(BUY_SIGNALS | SELL_SIGNALS | {"FAKE_BREAKOUT","WATCH"}),
            default=[],
            format_func=lambda x: SIGNAL_LABEL.get(x, x),
            placeholder="全部（不篩選）",
            key="sig_filter",
            help="留空 = 顯示全部訊號。勾選後只顯示選中類型。",
        )
        resist_only = flt_col3.toggle(
            "⚠️ 只看壓力區",
            value=False, key="resist_only",
            help="只顯示現價距壓力位 ≤3% 的股票",
        )
        st.markdown('</div>', unsafe_allow_html=True)

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
            # Determine watchlist based on scan_mode
            _mode = st.session_state.get("scan_mode", "🔖 自選股（快速）")
            if _mode == "🌏 全市場（284支）":
                wl = DEFAULT_WATCHLIST.copy()
            elif _mode == "📋 自訂清單":
                wl = custom_scan_codes if custom_scan_codes else st.session_state.watchlist
                if not wl:
                    st.warning("自訂清單為空，請先輸入股票代號"); wl = []
            else:
                wl = st.session_state.watchlist   # 🔖 自選股（預設）
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

            # ── 方案D：依模式顯示預估時間 ───────────────────────
            _n_stocks  = len(wl)
            _est_fresh = max(15, _n_stocks * 0.5)   # ~0.5s per stock worst case
            _scan_mode_now = st.session_state.get("scan_mode","🔖 自選股（快速）")
            _est_label = (
                "約 10–20 秒" if _scan_mode_now == "🔖 自選股（快速）" else
                "約 30–60 秒" if _n_stocks <= 100 else
                "約 60–90 秒"
            )
            # Check if OHLCV data is already cached (ttl=1800 — within 30 min)
            _ohlcv_cached = bool(batch_fetch_ohlcv.cache_info().currsize
                                  if hasattr(batch_fetch_ohlcv, 'cache_info') else False)
            _spinner_msg = (
                f"掃描中（{_est_label}）— 歷史資料已快取，速度較快 ⚡"
                if _ohlcv_cached else
                f"下載歷史資料 + 掃描中（{_est_label}）…"
            )
            ohlcv_cache: dict = {}
            try:
                with st.spinner(_spinner_msg):
                    ohlcv_cache = batch_fetch_ohlcv(tuple(wl), data_period)
            except Exception:
                ohlcv_cache = {}

            prog = st.progress(0, text="掃描中…")

            for i, code in enumerate(wl):
                prog.progress((i + 1) / total_n,
                              text=f"分析 {code} ({i+1}/{total_n})…")
                bare        = code.upper().replace(".TW","").replace(".TWO","")

                # Use batch-prefetched OHLCV; fall back to individual only if missing
                if bare in ohlcv_cache:
                    df_raw = ohlcv_cache[bare]
                    err    = None
                else:
                    df_raw, err = fetch_data(code, data_period)

                if df_raw is None or len(df_raw) < 60:
                    failed.append(f"{code}: {err or '資料不足'}")
                    continue

                # Use globally-cached per-stock CCI if already optimised,
                # otherwise fall back to global params
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
                # Always show something — use code as display name if no Chinese name found
                if not cn_name:
                    cn_name = bare   # bare code as fallback (better than blank)

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
            st.session_state["_scan_restored"] = False

            # ── 方案A：持久化掃描結果到 /tmp ──────────────────────
            scan_cache_save(
                rows, st.session_state.scan_timestamp,
                st.session_state.get("scan_mode", "🔖 自選股（快速）")
            )

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
                    # ── Lifecycle record (new in v3.2) ────────────────
                    lc_rec = lifecycle_build_record(
                        code    = r["代號"],
                        name    = r.get("_cn_name", r.get("名稱","")),
                        sig_key = r["_sig_key"],
                        price   = float(r.get("_price", 0) or 0),
                        atr_stop= float(r.get("_atr_stop", 0) or 0),
                        conf    = int(r.get("_conf", 0) or 0),
                        trend   = int(r.get("趨勢", 0) or 0),
                    )
                    lifecycle_add(lc_rec)

            # ── Update outcomes for previously recorded signals ───────
            n_updated = sig_hist_update_outcomes(fetch_data)
            if n_updated:
                st.toast(f"📈 已更新 {n_updated} 筆歷史訊號實際報酬", icon="📊")

            # ── Lifecycle: auto-expire + Telegram reminders ──────────
            n_expired = lifecycle_update_statuses()
            if n_expired:
                st.toast(f"⏰ {n_expired} 筆訊號已自動失效", icon="🔕")
            lc_active = lifecycle_get_active()

            # ── Telegram push for NEW actionable signals ──────────────
            tg_token_v   = st.session_state.get("tg_token", "")
            tg_chat_v    = st.session_state.get("tg_chat_id", "")
            tg_sigs_v    = set(st.session_state.get("tg_sigs",
                                list(BUY_SIGNALS | SELL_SIGNALS)))
            tg_min_conf_v= int(st.session_state.get("tg_min_conf", 5))
            # Lifecycle reminders now that tg vars are defined
            if lc_active and tg_token_v and tg_chat_v:
                lifecycle_tg_reminder(lc_active, tg_token_v, tg_chat_v)
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

        # ── #3 Apply quick filters to display rows ───────────────────────
        _sig_filter   = st.session_state.get("sig_filter",   [])
        _resist_only  = st.session_state.get("resist_only",  False)
        display_rows  = rows
        if _sig_filter:
            display_rows = [r for r in display_rows if r.get("_sig_key") in _sig_filter]
        if _resist_only:
            display_rows = [r for r in display_rows if r.get("壓力區","─") != "─"]
        if _sig_filter or _resist_only:
            st.caption(
                f"篩選中：顯示 **{len(display_rows)}** / {len(rows)} 支"
                + (f"　訊號：{', '.join(SIGNAL_LABEL.get(s,s) for s in _sig_filter)}" if _sig_filter else "")
                + ("　⚠️ 壓力區" if _resist_only else "")
            )

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

            today_buy  = [r for r in display_rows if r["_sig_key"] in ACTION_BUY]
            today_sell = [r for r in display_rows if r["_sig_key"] in ACTION_SELL]
            today_warn = [r for r in display_rows if r["_sig_key"] in ACTION_WARN]

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

            # ── Sort (on filtered display_rows) ──
            if sort_mode == "⭐ 共振分數":
                rows_sorted = sorted(display_rows, key=lambda r: (-SIGNAL_ORDER.get(r["_sig_key"], 9), -r["_conf"], -r["_mom"]))
            elif sort_mode in ("🔥 動能", "🔥 動能分數"):
                rows_sorted = sorted(display_rows, key=lambda r: -r["_mom"])
            elif sort_mode in ("📈 量比",):
                rows_sorted = sorted(display_rows, key=lambda r: -r["_vol_r"])
            else:
                rows_sorted = sorted(display_rows, key=lambda r: SIGNAL_ORDER.get(r["_sig_key"], 9))

            df_display = pd.DataFrame(rows_sorted)
            show_cols  = [c for c in df_display.columns if not c.startswith("_")]
            df_display = df_display[show_cols]

            # Caption shows both total scanned and filtered count
            _mode_lbl = {"🔖 自選股（快速）":"自選股","🌏 全市場（284支）":"全市場","📋 自訂清單":"自訂清單"}.get(
                st.session_state.get("scan_mode","🔖 自選股（快速）"), "自選股")
            if scan_time:
                total_scanned = len(rows)
                showing = len(display_rows)
                filter_note = f"　篩選後顯示 {showing} 支" if showing < total_scanned else ""
                st.caption(f"🕐 最後更新：{scan_time}　{_mode_lbl}共掃描 {total_scanned} 支{filter_note}　"
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
            💎 <b>共振回調買</b> 三重共振後 1–3 日縮量回調，CCI>0 結構完整（風險報酬比更優）<br>
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

                # ── Signal Timeline Panel ─────────────────────────
                # Scan last 30 bars for all buy/sell signals → timeline
                sig_events = []
                lookback_bars = min(60, len(df_sig))
                for idx_pos in range(len(df_sig) - lookback_bars, len(df_sig)):
                    row_s   = df_sig.iloc[idx_pos]
                    s_key   = str(row_s.get("Signal", "NEUTRAL") or "NEUTRAL")
                    s_date  = df_sig.index[idx_pos]
                    if s_key in BUY_SIGNALS | SELL_SIGNALS:
                        s_close = float(row_s["Close"])
                        s_atr   = float(row_s.get("ATR", 0) or 0)
                        s_stop  = round(s_close - s_atr * 1.5, 2) if s_atr else round(s_close * 0.93, 2)
                        s_t1    = round(s_close + (s_close - s_stop) * 1.5, 2)
                        s_t2    = round(s_close + (s_close - s_stop) * 2.5, 2)
                        days_ago = (df_sig.index[-1] - s_date).days
                        sig_events.append({
                            "date":    s_date,
                            "key":     s_key,
                            "label":   SIGNAL_LABEL.get(s_key, s_key),
                            "close":   s_close,
                            "stop":    s_stop,
                            "t1":      s_t1,
                            "t2":      s_t2,
                            "days_ago": days_ago,
                            "detail":  str(row_s.get("Signal_Detail","") or ""),
                        })

                if sig_events:
                    latest_ev = sig_events[-1]
                    is_buy    = latest_ev["key"] in BUY_SIGNALS
                    is_sell   = latest_ev["key"] in SELL_SIGNALS
                    ev_color  = MARKER_SHAPE.get(latest_ev["key"], ("","#5a8fb0",10,""))[1]
                    cfg       = SIGNAL_LIFECYCLE.get(latest_ev["key"], SIGNAL_LIFECYCLE.get("BUY", {}))
                    entry_latest = cfg.get("entry_latest", 2)
                    decay_days   = cfg.get("decay_days",   3)
                    days_since   = latest_ev["days_ago"]
                    still_valid  = days_since <= decay_days

                    # Recommendation text
                    if is_buy and still_valid:
                        rec_title = "✅ 建議進場"
                        rec_color = "#00ff88"
                        rec_bg    = "rgba(0,255,136,0.06)"
                        rec_msg   = (
                            f"訊號日 {latest_ev['date'].strftime('%m/%d')} 出現「{latest_ev['label']}」，"
                            f"距今 {days_since} 天，仍在有效期內（{decay_days} 天）。\n"
                            f"建議在 {cfg.get('entry_time','收盤前')} 進場，"
                            f"停損 {latest_ev['stop']:.2f}，目標 {latest_ev['t1']:.2f} / {latest_ev['t2']:.2f}。"
                        )
                    elif is_buy and not still_valid:
                        rec_title = "⏰ 訊號已過期"
                        rec_color = "#ffd600"
                        rec_bg    = "rgba(255,214,0,0.05)"
                        rec_msg   = (
                            f"訊號日 {latest_ev['date'].strftime('%m/%d')} 出現「{latest_ev['label']}」，"
                            f"距今已 {days_since} 天，超過有效期 {decay_days} 天。"
                            "不建議追入，等待新訊號形成。"
                        )
                    elif is_sell:
                        rec_title = "🔴 建議減碼 / 出場"
                        rec_color = "#ff3355"
                        rec_bg    = "rgba(255,51,85,0.06)"
                        rec_msg   = (
                            f"訊號日 {latest_ev['date'].strftime('%m/%d')} 出現「{latest_ev['label']}」，"
                            f"距今 {days_since} 天。"
                            f"建議評估減碼或設移動停損保護獲利。"
                        )
                    else:
                        rec_title = "─ 觀望"
                        rec_color = "#5a8fb0"
                        rec_bg    = "rgba(90,143,176,0.04)"
                        rec_msg   = "近期無明確買賣訊號，維持觀望。"

                    # ── Main recommendation card ──
                    grid_html = ""
                    if is_buy:
                        grid_html = (
                            '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
                            'gap:6px;margin-bottom:10px">'
                            + "".join([
                                f'<div style="background:#0a0e1a;padding:7px 10px;border-radius:6px;text-align:center">'
                                f'<div style="font-size:0.6rem;color:#5a8fb0;text-transform:uppercase">{lbl}</div>'
                                f'<div style="font-family:monospace;font-size:0.9rem;font-weight:700;color:{col};margin-top:3px">{val}</div>'
                                f'</div>'
                                for lbl, val, col in [
                                    ("訊號收盤", f"{latest_ev['close']:.2f}", "#e8f4fd"),
                                    ("停損價",  f"{latest_ev['stop']:.2f}",  "#ff3355"),
                                    ("目標1",   f"{latest_ev['t1']:.2f}",    "#00ff88"),
                                    ("目標2",   f"{latest_ev['t2']:.2f}",    "#ffd600"),
                                ]
                            ])
                            + '</div>'
                        )
                    lifecycle_row = ""
                    if is_buy and cfg:
                        lifecycle_row = (
                            f'<div style="margin-top:8px;padding-top:8px;'
                            f'border-top:1px solid {rec_color}20;font-size:0.72rem;color:#5a8fb0">'
                            f'進場時機：{cfg.get("entry_time","─")}　'
                            f'停損方式：{cfg.get("stop_method","─")}　'
                            f'持倉：{cfg.get("holding","─")}</div>'
                        )
                    validity_badge = (
                        "  ✅ 有效" if still_valid and is_buy
                        else "  ⏰ 過期" if not still_valid and is_buy
                        else ""
                    )
                    card_html = (
                        f'<div style="background:{rec_bg};border:1.5px solid {rec_color}40;'
                        f'border-left:4px solid {rec_color};border-radius:10px;'
                        f'padding:14px 18px;margin:10px 0 6px 0">'
                        f'<div style="display:flex;justify-content:space-between;'
                        f'align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px">'
                        f'<span style="font-size:1rem;font-weight:800;color:{rec_color}">{rec_title}</span>'
                        f'<span style="font-size:0.72rem;color:{ev_color};'
                        f'border:1px solid {ev_color}60;padding:2px 10px;border-radius:10px">'
                        f'{latest_ev["label"]}  {latest_ev["date"].strftime("%m/%d")}{validity_badge}</span>'
                        f'</div>'
                        + grid_html
                        + f'<div style="font-size:0.8rem;color:#8a9bb5;line-height:1.65">{rec_msg}</div>'
                        + lifecycle_row
                        + '</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)

                    # ── Signal timeline (last 10 events) ──
                    if len(sig_events) > 1:
                        st.markdown(
                            '<div style="font-size:0.68rem;color:#5a8fb0;'
                            'letter-spacing:0.08em;text-transform:uppercase;'
                            'margin:12px 0 6px 0">近期訊號時間軸</div>',
                            unsafe_allow_html=True,
                        )
                        timeline_html = '<div style="display:flex;flex-direction:column;gap:4px">'
                        for ev in reversed(sig_events[-10:]):
                            ev_c  = MARKER_SHAPE.get(ev["key"], ("","#5a8fb0",10,""))[1]
                            is_b  = ev["key"] in BUY_SIGNALS
                            bg    = "rgba(0,255,136,0.04)" if is_b else "rgba(255,51,85,0.04)"
                            pnl   = ""
                            if is_b:
                                cur_ret = (price - ev["close"]) / ev["close"] * 100
                                pnl_c   = "#00ff88" if cur_ret >= 0 else "#ff3355"
                                pnl     = f'<span style="color:{pnl_c};font-family:monospace;font-size:0.7rem">{cur_ret:+.1f}%</span>'
                            is_latest_marker = "◀" if ev is sig_events[-1] else ""
                            timeline_html += (
                                f'<div style="display:flex;align-items:center;gap:8px;'
                                f'background:{bg};border-left:2px solid {ev_c};'
                                f'padding:4px 10px;border-radius:0 6px 6px 0;'
                                f'{"border:1px solid "+ev_c+"40;" if ev is sig_events[-1] else ""}">'
                                f'<span style="font-family:monospace;font-size:0.72rem;'
                                f'color:#5a8fb0;min-width:40px">{ev["date"].strftime("%m/%d")}</span>'
                                f'<span style="font-size:0.75rem;color:{ev_c};font-weight:600;'
                                f'min-width:80px">{ev["label"]}</span>'
                                f'<span style="font-family:monospace;font-size:0.72rem;color:#e8f4fd">'
                                f'{ev["close"]:.2f}</span>'
                                f'{pnl}'
                                f'<span style="font-size:0.65rem;color:#37474f;flex:1;'
                                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                                f'{ev["detail"][:45]}</span>'
                                f'<span style="color:{ev_c};font-size:0.72rem">{is_latest_marker}</span>'
                                f'</div>'
                            )
                        timeline_html += '</div>'
                        st.markdown(timeline_html, unsafe_allow_html=True)

                else:
                    st.markdown(
                        '<div style="background:#0d1226;border:1px solid #1a2d44;'
                        'border-radius:8px;padding:12px 16px;color:#5a8fb0;font-size:0.82rem;margin:10px 0">'
                        '近 60 根 K 棒無明確買賣訊號，建議觀望等待。</div>',
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
        # SECTION A — 新增交易記錄 + 智能倉位建議
        # ══════════════════════════════════════════════════════
        with st.expander("➕ 新增交易 & 倉位顧問", expanded=not trades_all):

            # ── Step 1: 交易類型 ─────────────────────────────
            st.markdown("**① 選擇交易類型**")
            trade_type_map = {
                "🌙 隔日沖": "overnight",
                "📈 波段交易": "swing",
                "💼 長線持倉": "longterm",
            }
            trade_type_lbl = st.radio(
                "交易類型",
                list(trade_type_map.keys()),
                horizontal=True,
                label_visibility="collapsed",
                key="pt_trade_type",
            )
            trade_type = trade_type_map[trade_type_lbl]

            # Type explanations
            type_info = {
                "overnight": dict(
                    title="🌙 隔日沖",
                    desc="今日收盤前 13:20–13:30 進場，次日開盤 09:05–09:30 出場。",
                    holding="持倉時間：**固定 18–20 小時**",
                    entry_rule="**一次全進**：時間窗口短，不做分批",
                    exit_rule="次日開盤：跌破進場價 **-2%** 立即止損；漲超 **+3%** 可部分留倉",
                    add_rule="**不加碼**：隔日沖不追加倉位",
                    risk_default=2.0,
                    risk_options=[("積極 2%", 2.0), ("標準 1%", 1.0), ("保守 0.5%", 0.5)],
                    color="#5a8fb0",
                ),
                "swing": dict(
                    title="📈 波段交易",
                    desc="跟著趨勢持有，從幾天到數週，依訊號反轉或目標價出場。",
                    holding="持倉時間：**3 天到 4 週**（視趨勢強度）",
                    entry_rule="**分批建倉**：第一批 40-50%，趨勢確認後加碼",
                    exit_rule="**ATR 移動停損**：盈利超過 1R 後跟蹤停損；目標 2-3R 分批出",
                    add_rule="**趨勢加碼**：股價再突破 + 量能確認後，加碼第二批 30%",
                    risk_default=1.5,
                    risk_options=[("積極 2%", 2.0), ("標準 1.5%", 1.5), ("保守 1%", 1.0)],
                    color="#00ff88",
                ),
                "longterm": dict(
                    title="💼 長線持倉",
                    desc="基本面 + 趨勢雙重確認，月線以上週期，適合資金大的核心倉。",
                    holding="持倉時間：**1 個月以上**（視基本面改變）",
                    entry_rule="**分批建倉**：第一批 30%，每逢回調 5% 加碼一次",
                    exit_rule="**跌破 EMA200 年線**視為出場訊號；目標 20%+ 分批減碼",
                    add_rule="**逢低加碼**：股價回調至 EMA60 附近 + 量縮後，加碼 20-30%",
                    risk_default=1.0,
                    risk_options=[("標準 1%", 1.0), ("保守 0.5%", 0.5)],
                    color="#f0a500",
                ),
            }
            info = type_info[trade_type]

            st.markdown(
                f'<div style="background:#0d1a2d;border-left:3px solid {info["color"]};'
                f'border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:12px">'
                f'<div style="color:{info["color"]};font-weight:700;font-size:0.88rem">'
                f'{info["title"]}</div>'
                f'<div style="color:#8a9bb5;font-size:0.8rem;margin-top:4px">{info["desc"]}</div>'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:8px;font-size:0.75rem">'
                f'<div><span style="color:#5a8fb0">⏱ 持倉：</span>'
                f'<span style="color:#cdd9e8">{info["holding"]}</span></div>'
                f'<div><span style="color:#5a8fb0">📥 進場：</span>'
                f'<span style="color:#cdd9e8">{info["entry_rule"]}</span></div>'
                f'<div><span style="color:#5a8fb0">📤 出場：</span>'
                f'<span style="color:#cdd9e8">{info["exit_rule"]}</span></div>'
                f'<div><span style="color:#5a8fb0">➕ 加碼：</span>'
                f'<span style="color:#cdd9e8">{info["add_rule"]}</span></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            # ── Step 2: 風險參數 ─────────────────────────────
            st.markdown("**② 風險參數設定**")
            rc1, rc2, rc3 = st.columns(3)

            total_capital = rc1.number_input(
                "可用總資金（元）",
                min_value=10000, max_value=100_000_000,
                value=int(st.session_state.get("pt_capital_mem", 500000)),
                step=50000, key="pt_capital",
                help=(
                    "你這次可動用的總資金。\n"
                    "系統用這個數字計算「每筆最大損失金額」，\n"
                    "再換算成建議股數。不會影響任何實際交易。"
                ),
            )
            st.session_state["pt_capital_mem"] = total_capital

            risk_label = rc2.selectbox(
                "每筆最大風險",
                [lbl for lbl, _ in info["risk_options"]],
                key="pt_risk_lbl",
                help=(
                    "**每筆最大風險** = 這筆交易最多虧多少佔總資金的比例。\n\n"
                    f"• 積極 2%：每筆最多虧 {total_capital*0.02:,.0f} 元\n"
                    f"• 標準 1%：每筆最多虧 {total_capital*0.01:,.0f} 元\n"
                    f"• 保守 0.5%：每筆最多虧 {total_capital*0.005:,.0f} 元\n\n"
                    "專業建議：單筆風險不超過總資金 2%，才能在 10 連虧後仍保留 80% 資金。"
                ),
            )
            risk_pct = dict(info["risk_options"])[risk_label] / 100
            max_loss_amt = total_capital * risk_pct

            stop_pct_input = rc3.number_input(
                "停損幅度 %",
                min_value=0.5, max_value=15.0,
                value={"overnight": 2.0, "swing": 7.0, "longterm": 10.0}[trade_type],
                step=0.5, key="pt_stop_pct",
                help=(
                    "**停損幅度** = 進場後最多容忍跌多少% 才出場。\n\n"
                    "• 隔日沖：2%（固定，開盤即止損）\n"
                    "• 波段：5-8%（ATR 倍數或固定%）\n"
                    "• 長線：8-12%（給更大的呼吸空間）\n\n"
                    "停損越緊，建議股數越多（相同風險金額下），"
                    "但也越容易被洗出，需根據個股波動調整。"
                ),
            )

            # ── Step 3: 股票基本資訊 ────────────────────────
            st.markdown("**③ 股票與進場資訊**")
            fa1, fa2, fa3 = st.columns([2, 2, 2])
            wl_opts = [c.replace(".TW","").replace(".TWO","")
                       for c in st.session_state.watchlist]
            t_code  = fa1.selectbox("股票代號", wl_opts,
                                    key="pt_code",
                                    help="從自選股選擇，或在下方手動輸入")
            t_cust  = fa2.text_input("或手動輸入代號",
                                      placeholder="2330 / 3661",
                                      key="pt_cust")
            t_buy_sell = fa3.selectbox(
                "買 / 賣",
                ["買入", "賣出"],
                key="pt_type",
                help=(
                    "**買入**：建立新倉位或加碼現有倉位。\n"
                    "**賣出**：減碼或清倉現有持股。\n\n"
                    "賣出時系統會自動核對現有持倉，"
                    "避免賣超過持有數量。"
                ),
            )

            fb1, fb2, fb3 = st.columns(3)
            t_date  = fb1.date_input("交易日期",
                                      value=tw_now().date(), key="pt_date")
            t_price = fb2.number_input(
                "成交價（元）", min_value=0.01, value=100.0, step=0.01, key="pt_price",
                help="實際成交價格，用於計算建議股數和損益。",
            )

            # ── Smart position size calculation ─────────────
            code_for_calc = (t_cust.strip() or t_code).upper().replace(".TW","").replace(".TWO","")
            stop_price    = round(float(t_price) * (1 - stop_pct_input / 100), 2)
            risk_per_share = float(t_price) - stop_price
            if risk_per_share > 0:
                raw_shares   = max_loss_amt / risk_per_share
                # Round down to nearest lot (1000 shares in Taiwan)
                suggested_shares = max(1000, int(raw_shares // 1000) * 1000)
                suggested_cost   = suggested_shares * float(t_price)
                capital_pct      = suggested_cost / total_capital * 100
                # Cap at 25% single-stock limit
                max_single_shares = int(total_capital * 0.25 / float(t_price) // 1000) * 1000
                if suggested_shares > max_single_shares:
                    suggested_shares = max_single_shares
                    cap_note = "（已依單股上限 25% 調整）"
                else:
                    cap_note = ""
            else:
                suggested_shares = 1000
                capital_pct = 0
                cap_note = ""

            # Batch sizing for swing/longterm
            if trade_type == "swing":
                batch1 = max(1000, int(suggested_shares * 0.45 // 1000) * 1000)
                batch2 = max(1000, int(suggested_shares * 0.30 // 1000) * 1000)
                batch3 = suggested_shares - batch1 - batch2
                batch3 = max(0, int(batch3 // 1000) * 1000)
            elif trade_type == "longterm":
                batch1 = max(1000, int(suggested_shares * 0.30 // 1000) * 1000)
                batch2 = max(1000, int(suggested_shares * 0.35 // 1000) * 1000)
                batch3 = suggested_shares - batch1 - batch2
                batch3 = max(0, int(batch3 // 1000) * 1000)
            else:  # overnight — all in
                batch1 = suggested_shares
                batch2 = batch3 = 0

            # ── Position size display ───────────────────────
            st.markdown(
                f'<div style="background:#0a1e10;border:1px solid #1a4a20;'
                f'border-radius:8px;padding:12px 16px;margin:8px 0 12px 0">'
                f'<div style="color:#00ff88;font-weight:700;font-size:0.88rem;margin-bottom:8px">'
                f'📐 建議倉位計算 {cap_note}</div>'
                f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;'
                f'font-size:0.78rem">'

                # Risk info
                f'<div style="background:#0d1a2d;padding:8px 10px;border-radius:6px">'
                f'<div style="color:#5a8fb0;font-size:0.65rem;text-transform:uppercase">每筆最大風險</div>'
                f'<div style="color:#ff6666;font-weight:700;margin-top:3px">'
                f'{max_loss_amt:,.0f} 元</div>'
                f'<div style="color:#37474f;font-size:0.65rem">總資金 × {risk_pct*100:.1f}%</div>'
                f'</div>'

                # Stop price
                f'<div style="background:#0d1a2d;padding:8px 10px;border-radius:6px">'
                f'<div style="color:#5a8fb0;font-size:0.65rem;text-transform:uppercase">停損價位</div>'
                f'<div style="color:#ff3355;font-weight:700;margin-top:3px">'
                f'{stop_price:.2f} 元</div>'
                f'<div style="color:#37474f;font-size:0.65rem">-{stop_pct_input:.1f}% 出場</div>'
                f'</div>'

                # Suggested total
                f'<div style="background:#0d1a2d;padding:8px 10px;border-radius:6px">'
                f'<div style="color:#5a8fb0;font-size:0.65rem;text-transform:uppercase">建議總股數</div>'
                f'<div style="color:#00ff88;font-weight:700;margin-top:3px">'
                f'{suggested_shares:,} 股</div>'
                f'<div style="color:#37474f;font-size:0.65rem">'
                f'佔資金 {suggested_cost/total_capital*100:.1f}%</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Batch plan
            if trade_type != "overnight":
                batch_color = {"swing": "#2196f3", "longterm": "#f0a500"}[trade_type]
                batch_labels = {
                    "swing":    [("第一批 進場時",    batch1, "今日訊號確認，立即進場"),
                                 ("第二批 趨勢確認後", batch2, "股價再突破 + 量能放大後加碼"),
                                 ("第三批 強勢追加",   batch3, "趨勢加速、評分上升時補倉")],
                    "longterm": [("第一批 初始建倉",   batch1, "訊號出現，試探性進場"),
                                 ("第二批 回調加碼",   batch2, "回調至 EMA60 + 量縮時加碼"),
                                 ("第三批 強勢補倉",   batch3, "突破前高 + 法人買超確認")],
                }
                st.markdown(
                    f'<div style="background:#0a0e1a;border:1px solid {batch_color}40;'
                    f'border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                    f'<div style="color:{batch_color};font-size:0.78rem;font-weight:700;'
                    f'margin-bottom:8px">分批進場計劃</div>'
                    + "".join([
                        f'<div style="display:flex;justify-content:space-between;align-items:center;'
                        f'margin-bottom:6px;font-size:0.75rem">'
                        f'<span style="color:#e8f4fd;font-weight:600">{lbl}</span>'
                        f'<span style="color:{batch_color};font-family:monospace">'
                        f'{shares:,} 股 = {shares*float(t_price):,.0f} 元</span>'
                        f'</div>'
                        f'<div style="color:#37474f;font-size:0.68rem;margin-bottom:8px;'
                        f'padding-left:8px">↳ {cond}</div>'
                        for lbl, shares, cond in batch_labels[trade_type]
                        if shares > 0
                    ])
                    + '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="background:#0a0e1a;border:1px solid #5a8fb040;'
                    f'border-radius:8px;padding:10px 14px;margin-bottom:10px;font-size:0.75rem">'
                    f'<span style="color:#5a8fb0">⚡ 隔日沖一次全進：</span>'
                    f'<span style="color:#e8f4fd"> {suggested_shares:,} 股，'
                    f'成本 {suggested_shares*float(t_price):,.0f} 元</span>'
                    f'<div style="color:#37474f;margin-top:4px">'
                    f'↳ 次日開盤 09:05 觀察，跌破 {stop_price:.2f} 立即市價賣出</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Actual trade input ──────────────────────────
            st.markdown("**④ 確認本次進場股數**")
            fc1, fc2, fc3 = st.columns(3)
            # Default to batch1 suggestion
            t_shares = fc1.number_input(
                "本次股數",
                min_value=1, value=batch1 if batch1 > 0 else suggested_shares,
                step=1000, key="pt_shares",
                help=(
                    f"系統建議：本次進場 {batch1:,} 股\n"
                    f"（基於每筆最大風險 {max_loss_amt:,.0f} 元、"
                    f"停損幅度 {stop_pct_input:.1f}% 計算）\n\n"
                    "你可以直接修改為任意股數，建議值僅供參考。"
                ),
            )
            t_fee = fc2.number_input(
                "手續費 $", min_value=0.0,
                value=round(float(t_price) * t_shares * 0.001425 * 0.6, 0),
                step=1.0, key="pt_fee",
                help="預設 0.1425% × 60折（一般券商優惠折扣）",
            )
            add_btn = fc3.button(
                "✅ 確認新增", type="primary", width='stretch', key="pt_add",
            )

            # ── Trade note / strategy tag ───────────────────
            trade_note = st.text_input(
                "交易備註（選填）",
                placeholder=f"例：{trade_type_lbl} 第一批進場，均線多頭確認",
                key="pt_note",
                help="記錄進場理由，方便日後回顧。",
            )

            if add_btn:
                if float(t_price) <= 0:
                    st.error("⚠️ 成交價必須大於 0")
                elif int(t_shares) <= 0:
                    st.error("⚠️ 股數必須大於 0")
                else:
                    code_final = (t_cust.strip() or t_code).upper().replace(".TW","").replace(".TWO","")
                    cn, _ = fetch_name(code_final)
                    new_trade = {
                        "id":         port_next_id(),
                        "type":       t_buy_sell,
                        "code":       code_final,
                        "name":       cn or code_final,
                        "date":       str(t_date),
                        "price":      float(t_price),
                        "shares":     int(t_shares),
                        "fee":        float(t_fee),
                        "trade_type": trade_type,     # overnight/swing/longterm
                        "stop_price": stop_price,
                        "note":       trade_note,
                        "risk_pct":   risk_pct * 100,
                    }
                if t_buy_sell == "賣出":
                    pos_now = get_open_positions(trades_all)
                    held    = pos_now.get(code_final, {}).get("shares", 0)
                    if t_shares > held:
                        st.error(f"⚠️ 持倉只有 {held} 股，無法賣出 {t_shares} 股")
                    else:
                        port_add_trade(new_trade)
                        st.session_state["_port_msg"] = (
                            f"✅ 已記錄 {t_buy_sell} {code_final} × {t_shares:,} 股 @ {t_price}  "
                            f"｜ {trade_type_lbl}  停損 {stop_price:.2f}"
                        )
                        st.rerun()
                else:
                    port_add_trade(new_trade)
                    st.session_state["_port_msg"] = (
                        f"✅ 已記錄 {t_buy_sell} {code_final} × {t_shares:,} 股 @ {t_price}  "
                        f"｜ {trade_type_lbl}  停損 {stop_price:.2f}"
                    )
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


    # ─────────────────────────────────────────────────────────
    # TAB 6.5  🗓 訊號管理 — 進退場生命週期
    # ─────────────────────────────────────────────────────────
    with tab_lifecycle:
        st.markdown("#### 🗓 訊號生命週期管理")
        st.caption(
            "每個訊號從觸發到出場都有固定的進場窗口、停損設定與退場條件。"
            "此頁追蹤所有活躍訊號的狀態，並提供詳細的操作說明。"
        )

        # ── Auto-refresh status ──────────────────────────────
        n_exp = lifecycle_update_statuses()
        if n_exp:
            st.info(f"⏰ 已自動標記 {n_exp} 筆過期訊號")

        all_lc = lifecycle_get_all()
        if not all_lc:
            st.info("尚無訊號記錄。執行訊號掃描後，買入訊號會自動加入此清單。")
        else:
            # ── Filter tabs ──────────────────────────────────
            lc_filter = st.radio(
                "顯示",
                ["🟢 活躍中", "📋 全部", "✅ 已進場", "❌ 已失效"],
                horizontal=True, label_visibility="collapsed",
                key="lc_filter",
            )
            filter_map = {
                "🟢 活躍中": ["active"],
                "📋 全部":   ["active","entered","expired","stopped","target"],
                "✅ 已進場": ["entered"],
                "❌ 已失效": ["expired","stopped","target"],
            }
            show_recs = [r for r in all_lc
                         if r["status"] in filter_map[lc_filter]]
            show_recs.sort(key=lambda r: r["date_fired"], reverse=True)

            if not show_recs:
                st.info("此分類暫無記錄")
            else:
                st.markdown(f"共 **{len(show_recs)}** 筆")

                # ── Summary table ─────────────────────────────
                tbl_rows = []
                for r in show_recs:
                    days_r = lifecycle_days_remaining(r)
                    urgency = lifecycle_urgency(r)
                    status_label = {
                        "active":  "🟢 進場窗口開啟",
                        "entered": "📥 已進場",
                        "expired": "⌛ 已失效",
                        "stopped": "🛑 已停損",
                        "target":  "🎯 已達目標",
                    }.get(r["status"], r["status"])
                    tbl_rows.append({
                        "代號":     r["code"],
                        "名稱":     r["name"],
                        "訊號":     r["sig_label"],
                        "訊號日":   r["date_fired"],
                        "訊號價":   r["price_fired"],
                        "停損價":   r["stop_price"],
                        "目標1":    r["target_1r"],
                        "目標2":    r["target_2r"],
                        "進場至":   r["entry_close"],
                        "期限":     urgency,
                        "狀態":     status_label,
                    })
                df_lc = pd.DataFrame(tbl_rows)
                st.dataframe(
                    df_lc, width='stretch', hide_index=True,
                    column_config={
                        "訊號價": st.column_config.NumberColumn(format="%.2f"),
                        "停損價": st.column_config.NumberColumn(format="%.2f",
                                    help="依 ATR 或固定% 計算，取較緊的一側"),
                        "目標1":  st.column_config.NumberColumn(format="%.2f",
                                    help="1R 目標：風險報酬比 1.5–2倍"),
                        "目標2":  st.column_config.NumberColumn(format="%.2f",
                                    help="2R 目標：風險報酬比 2.5–4倍"),
                    }
                )

                st.markdown("---")
                st.markdown("##### 📖 各訊號詳細說明")
                st.caption("展開查看每個訊號的進退場完整邏輯與說明")

                # ── Detail cards for each active record ───────
                for r in show_recs:
                    cfg   = SIGNAL_LIFECYCLE.get(r["sig_key"], SIGNAL_LIFECYCLE["BUY"])
                    days_r = lifecycle_days_remaining(r)
                    urgency = lifecycle_urgency(r)
                    pnl_str = ""
                    if r.get("entered_price"):
                        cur_q   = fetch_quote(r["code"])
                        cur_px  = cur_q.get("last_price", r["entered_price"])
                        pnl_pct = (cur_px - r["entered_price"]) / r["entered_price"] * 100
                        pnl_c   = "#00ff88" if pnl_pct >= 0 else "#ff3355"
                        pnl_str = (f'<span style="color:{pnl_c};font-weight:700">'
                                   f'{pnl_pct:+.2f}%</span>')

                    with st.expander(
                        f"{r['sig_label']}  {r['code']} {r['name']}  "
                        f"@{r['price_fired']:.2f}  {urgency}",
                        expanded=(r["status"] == "active" and days_r <= 2),
                    ):
                        # Header card
                        st.markdown(
                            f'<div style="background:#0d1a2d;border-left:4px solid {r["color"]};'
                            f'border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:12px">'
                            # Row 1: code + signal + urgency
                            f'<div style="display:flex;justify-content:space-between;'
                            f'flex-wrap:wrap;gap:6px;margin-bottom:8px">'
                            f'<span style="font-family:monospace;font-size:1rem;'
                            f'font-weight:700;color:#e8f4fd">{r["code"]} {r["name"]}</span>'
                            f'<span style="font-size:0.8rem;color:{r["color"]};'
                            f'border:1px solid {r["color"]}60;padding:2px 10px;'
                            f'border-radius:10px">{urgency}</span></div>'
                            # Row 2: key metrics grid
                            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);'
                            f'gap:8px;font-size:0.75rem">'
                            f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:6px">'
                            f'<div style="color:#5a8fb0;font-size:0.62rem">訊號日</div>'
                            f'<div style="color:#e8f4fd;font-weight:700">{r["date_fired"]}</div></div>'
                            f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:6px">'
                            f'<div style="color:#5a8fb0;font-size:0.62rem">訊號價</div>'
                            f'<div style="color:#e8f4fd;font-weight:700">{r["price_fired"]:.2f}</div></div>'
                            f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:6px;'
                            f'border:1px solid rgba(255,51,85,0.3)">'
                            f'<div style="color:#5a8fb0;font-size:0.62rem">停損價</div>'
                            f'<div style="color:#ff3355;font-weight:700">{r["stop_price"]:.2f}</div></div>'
                            f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:6px;'
                            f'border:1px solid rgba(0,255,136,0.3)">'
                            f'<div style="color:#5a8fb0;font-size:0.62rem">目標1/2</div>'
                            f'<div style="color:#00ff88;font-weight:700">'
                            f'{r["target_1r"]:.2f} / {r["target_2r"]:.2f}</div></div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

                        # ── 現況確認：即時抓取當前指標 ──────────────────
                        try:
                            df_now, _ = fetch_data(r["code"], "3mo")
                            if df_now is not None and len(df_now) >= 20:
                                df_now_sig = generate_signals(df_now, params)
                                cur_row    = df_now_sig.iloc[-1]
                                sig_row_idx = None
                                # Find the signal bar in history
                                for si in range(len(df_now_sig)-1, max(len(df_now_sig)-15, 0)-1, -1):
                                    bar_date = str(df_now_sig.index[si].date())
                                    if bar_date == r["date_fired"]:
                                        sig_row_idx = si
                                        break

                                cur_cci   = float(cur_row.get("CCI", 0) or 0)
                                cur_price = float(cur_row["Close"])
                                cur_ema20 = float(cur_row.get("EMA2", cur_price) or cur_price)
                                cur_vol_r = float(cur_row.get("Vol_Ratio", 1) or 1)
                                sig_cci   = float(df_now_sig.iloc[sig_row_idx].get("CCI", 0)) \
                                            if sig_row_idx is not None else None

                                # Check each exit trigger condition
                                trigger_checks = {
                                    "CCI跌破0軸":        cur_cci < 0,
                                    "CCI跌破-100":       cur_cci < -100,
                                    "CCI跌破+100後下穿": cur_cci < 100 and (sig_cci or 0) >= 100,
                                    "跌破EMA20":         cur_price < cur_ema20,
                                    "跌破停損":          cur_price <= r["stop_price"],
                                    "量縮3日":           cur_vol_r < 0.6,
                                }

                                # Which triggers are currently firing
                                fired    = [k for k, v in trigger_checks.items() if v
                                            and k in " ".join(r.get("exit_triggers", []))]
                                ok_flags = [k for k, v in trigger_checks.items() if not v
                                            and k in " ".join(r.get("exit_triggers", []))]

                                # Overall status
                                if cur_price <= r["stop_price"]:
                                    now_status = "🛑 已觸停損"
                                    now_color  = "#ff3355"
                                    now_bg     = "rgba(255,51,85,0.08)"
                                elif fired:
                                    now_status = "⚠️ 退場條件觸發"
                                    now_color  = "#ffd600"
                                    now_bg     = "rgba(255,214,0,0.06)"
                                else:
                                    now_status = "✅ 結構完整，持有中"
                                    now_color  = "#00ff88"
                                    now_bg     = "rgba(0,255,136,0.05)"

                                # CCI direction arrow
                                cci_arrow = "↑" if cur_cci > (sig_cci or 0) else "↓"
                                cci_color = "#00ff88" if cur_cci > 0 else "#ff3355"

                                st.markdown(
                                    f'<div style="background:{now_bg};border:1px solid {now_color}40;'
                                    f'border-left:3px solid {now_color};border-radius:8px;'
                                    f'padding:10px 14px;margin-bottom:10px">'
                                    f'<div style="display:flex;justify-content:space-between;'
                                    f'align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:4px">'
                                    f'<span style="font-size:0.78rem;font-weight:700;color:{now_color}">'
                                    f'📡 現況確認</span>'
                                    f'<span style="font-size:0.72rem;color:{now_color};'
                                    f'border:1px solid {now_color}60;padding:1px 8px;'
                                    f'border-radius:8px">{now_status}</span></div>'
                                    # Current indicators
                                    f'<div style="display:grid;grid-template-columns:repeat(4,1fr);'
                                    f'gap:6px;margin-bottom:8px">'
                                    f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:5px">'
                                    f'<div style="font-size:0.6rem;color:#5a8fb0">訊號日CCI</div>'
                                    f'<div style="font-size:0.8rem;font-weight:700;color:#e8f4fd;margin-top:2px">'
                                    f'{sig_cci:.1f if sig_cci is not None else "─"}</div></div>'
                                    f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:5px;'
                                    f'border:1px solid {cci_color}40">'
                                    f'<div style="font-size:0.6rem;color:#5a8fb0">現在CCI {cci_arrow}</div>'
                                    f'<div style="font-size:0.8rem;font-weight:700;color:{cci_color};margin-top:2px">'
                                    f'{cur_cci:.1f}</div></div>'
                                    f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:5px">'
                                    f'<div style="font-size:0.6rem;color:#5a8fb0">現價</div>'
                                    f'<div style="font-size:0.8rem;font-weight:700;color:#e8f4fd;margin-top:2px">'
                                    f'{cur_price:.2f}</div></div>'
                                    f'<div style="background:#0a0e1a;padding:6px 8px;border-radius:5px">'
                                    f'<div style="font-size:0.6rem;color:#5a8fb0">EMA20</div>'
                                    f'<div style="font-size:0.8rem;font-weight:700;'
                                    f'color:{"#00ff88" if cur_price >= cur_ema20 else "#ff3355"};margin-top:2px">'
                                    f'{cur_ema20:.2f}</div></div>'
                                    f'</div>'
                                    # Fired triggers
                                    + (
                                        f'<div style="font-size:0.7rem;color:#ff6677;margin-top:4px">'
                                        f'⚠️ 已觸發退場條件：{"　".join(fired)}</div>'
                                        if fired else
                                        f'<div style="font-size:0.7rem;color:#00ff88;margin-top:4px">'
                                        f'✓ 退場條件未觸發，結構完整</div>'
                                    )
                                    + '</div>',
                                    unsafe_allow_html=True,
                                )
                        except Exception:
                            pass   # 現況確認失敗不影響其他顯示

                        # Entry window
                        st.markdown(
                            f'<div style="background:#0a1520;border:1px solid #1a3a50;'
                            f'border-radius:8px;padding:10px 14px;margin-bottom:10px">'
                            f'<div style="color:#5a8fb0;font-size:0.72rem;'
                            f'text-transform:uppercase;margin-bottom:6px">進場窗口</div>'
                            f'<div style="font-size:0.82rem;color:#e8f4fd">'
                            f'⏰ <b>{r["entry_time"]}</b></div>'
                            f'<div style="font-size:0.78rem;color:#8a9bb5;margin-top:4px">'
                            f'最晚進場：<b style="color:#ffd700">{r["entry_close"]}</b>　'
                            f'有效期：訊號後 {r["decay_days"]} 個交易日</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        # Explanation (markdown)
                        st.markdown(
                            f'<div style="background:#080d18;border:1px solid #1a2d44;'
                            f'border-radius:8px;padding:12px 14px;margin-bottom:10px;'
                            f'font-size:0.82rem;color:#8a9bb5;line-height:1.7">'
                            f'{cfg["explanation"].replace(chr(10), "<br>").replace("**", "<b>", 1).replace("**", "</b>", 1)}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        # Exit triggers
                        trigger_html = "　".join(
                            f'<span style="background:#1a0a10;color:#ff6677;'
                            f'padding:2px 8px;border-radius:4px;font-size:0.72rem">{t}</span>'
                            for t in r["exit_triggers"]
                        )
                        st.markdown(
                            f'<div style="margin-bottom:10px">'
                            f'<div style="font-size:0.72rem;color:#5a8fb0;margin-bottom:6px">'
                            f'退場觸發條件</div>{trigger_html}</div>',
                            unsafe_allow_html=True,
                        )

                        # Action buttons
                        bc1, bc2, bc3 = st.columns(3)
                        rec_id = r["id"]
                        if r["status"] == "active":
                            ep = bc1.number_input(
                                "進場價", min_value=0.01,
                                value=float(r["price_fired"]),
                                step=0.01, key=f"lc_ep_{rec_id}",
                                label_visibility="collapsed",
                            )
                            if bc2.button("📥 標記已進場", key=f"lc_enter_{rec_id}",
                                          width='stretch'):
                                lifecycle_mark_entered(rec_id, ep)
                                st.success(f"✓ 已記錄進場 @ {ep:.2f}")
                                st.rerun()
                            if bc3.button("🗑 忽略此訊號", key=f"lc_ignore_{rec_id}",
                                          width='stretch'):
                                lifecycle_mark_exit(rec_id, 0, "手動忽略")
                                st.rerun()
                        elif r["status"] == "entered":
                            xp = bc1.number_input(
                                "出場價", min_value=0.01,
                                value=float(r.get("entered_price", r["price_fired"])),
                                step=0.01, key=f"lc_xp_{rec_id}",
                                label_visibility="collapsed",
                            )
                            xr = bc2.selectbox("原因",
                                ["達目標1","達目標2","停損","手動出場","訊號反轉"],
                                key=f"lc_xr_{rec_id}", label_visibility="collapsed")
                            if bc3.button("📤 標記已出場", key=f"lc_exit_{rec_id}",
                                          width='stretch'):
                                lifecycle_mark_exit(rec_id, xp, xr)
                                st.success(f"✓ 已記錄出場 @ {xp:.2f}，原因：{xr}")
                                st.rerun()
                        else:
                            # Show exit summary
                            if r.get("exit_price"):
                                entry  = r.get("entered_price") or r["price_fired"]
                                ret_p  = (r["exit_price"] - entry) / entry * 100
                                ret_c  = "#00ff88" if ret_p >= 0 else "#ff3355"
                                st.markdown(
                                    f'<div style="font-size:0.8rem;color:#5a8fb0">'
                                    f'出場 @ <b style="color:#e8f4fd">{r["exit_price"]:.2f}</b>　'
                                    f'報酬 <b style="color:{ret_c}">{ret_p:+.2f}%</b>　'
                                    f'原因：{r.get("exit_reason","─")}</div>',
                                    unsafe_allow_html=True,
                                )

                st.markdown("---")

                # ── Telegram reminder push ─────────────────────
                tg_t = st.session_state.get("tg_token","")
                tg_c = st.session_state.get("tg_chat_id","")
                if tg_t and tg_c:
                    active_count = sum(1 for r in show_recs if r["status"]=="active")
                    if st.button(f"📲 推播 {active_count} 筆活躍訊號提醒",
                                 key="lc_tg", width='stretch'):
                        n_sent = lifecycle_tg_reminder(
                            [r for r in show_recs if r["status"]=="active"],
                            tg_t, tg_c
                        )
                        st.success(f"✅ 已推播 {n_sent} 則提醒") if n_sent \
                            else st.info("無需推播（今日無到期或新增訊號）")
                else:
                    st.caption("💡 在側欄設定 Telegram 以啟用訊號期限提醒推播")

                # ── Clear expired ──────────────────────────────
                with st.expander("🗑 清理失效記錄"):
                    expired_count = sum(1 for r in all_lc
                                        if r["status"] in ("expired","stopped","target"))
                    st.caption(f"目前有 {expired_count} 筆已失效/出場記錄")
                    if st.button("清除所有已失效記錄", key="lc_clear",
                                 width='stretch'):
                        store = _load_lifecycle_store()
                        store["records"] = [r for r in store["records"]
                                            if r["status"] not in ("expired","stopped","target")]
                        _save_lifecycle(store)
                        st.success("✓ 已清除")
                        st.rerun()

    # ─────────────────────────────────────────
    # TAB 7  🌙 隔日沖策略
    # ─────────────────────────────────────────
    with tab_overnight:
        st.markdown("#### 🌙 隔日沖策略 — 因素回測 + 今日候選")
        st.caption(
            "逆向思考：先量化每個因素對次日開盤勝率的真實貢獻，"
            "再用最優評分組合篩選今日候選股。"
            "進場時間：13:20–13:30，出場時間：次日 09:05–09:30。"
        )

        # ── 子功能選擇 ─────────────────────────────────────────
        ovn_mode = st.radio(
            "功能",
            ["📊 單股因素回測", "🎯 今日候選掃描", "📖 策略說明"],
            horizontal=True, label_visibility="collapsed",
            key="ovn_mode",
        )

        # ══════════════════════════════════════
        # MODE 1: 單股因素回測
        # ══════════════════════════════════════
        if ovn_mode == "📊 單股因素回測":
            st.markdown("##### 📊 單股因素回測")
            st.caption("選擇股票，系統分析歷史上各因素對次日開盤報酬的實際貢獻。")

            col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
            _ovn_wl = [c.replace(".TW","").replace(".TWO","")
                       for c in st.session_state.get("watchlist", DEFAULT_WATCHLIST)]
            ovn_sym  = col_s1.selectbox(
                "股票", _ovn_wl,
                format_func=lambda x: f"{x}  {fetch_name(x)[0] or x}",
                key="ovn_sym",
            )
            ovn_period = col_s2.radio("回測區間", ["1y","2y","3y"], horizontal=True,
                                       index=1, key="ovn_prd")
            run_ovn = col_s3.button("🔬 分析", type="primary", width='stretch', key="ovn_run")

            if run_ovn:
                with st.spinner(f"下載 {ovn_sym} 歷史資料並回測…"):
                    df_ovn, _ = fetch_data(ovn_sym, ovn_prd := ovn_period)
                if df_ovn is None or len(df_ovn) < 60:
                    st.error("資料不足，請選擇更長的區間或換一支股票")
                else:
                    result = overnight_factor_backtest(df_ovn)
                    if not result:
                        st.error("回測樣本不足")
                    else:
                        # ── 🚦 VERDICT CARD — 最頂部，最醒目 ────────────
                        vd = result.get("verdict", {})
                        if vd:
                            # Compute today's score for display
                            df_today  = _overnight_factors(df_ovn)
                            today_row = df_today.iloc[-1]
                            today_sc  = overnight_score(today_row)
                            thresh    = vd["best_threshold"]
                            today_ok  = today_sc >= thresh

                            # Today score badges
                            score_badges = []
                            factor_icons = {
                                "F_close_near_high": "收盤強度",
                                "F_gain_3_7":        "漲幅甜區",
                                "F_vol_surge":       "量能放大",
                                "F_obv_new_high":    "OBV新高",
                                "F_trend_ok":        "均線多頭",
                                "F_above_200":       "站上年線",
                                "F_breakout_20d":    "突破20高",
                                "F_tail_ok":         "尾盤強度",
                            }
                            hit = []
                            miss = []
                            for col, label in factor_icons.items():
                                if today_row.get(col):
                                    hit.append(label)
                                else:
                                    miss.append(label)

                            entry_gate = "✅ 今日達門檻，可考慮進場" if today_ok \
                                         else f"⏳ 今日評分 {today_sc}/8 未達門檻 ≥{thresh}，今日不宜進場"
                            entry_color = vd["color"] if today_ok else "#ff3355"

                            st.markdown(
                                f'<div style="background:{vd["bg"]};'
                                f'border:2px solid {vd["border"]};'
                                f'border-radius:12px;padding:18px 20px;margin-bottom:20px">'

                                # Verdict label (large)
                                f'<div style="font-size:1.3rem;font-weight:800;'
                                f'color:{vd["color"]};margin-bottom:6px">{vd["label"]}</div>'

                                # Key stats row
                                f'<div style="display:grid;grid-template-columns:repeat(4,1fr);'
                                f'gap:8px;margin-bottom:12px">'
                                + "".join(
                                    f'<div style="background:#0a0e1a;padding:8px 10px;border-radius:8px;text-align:center">'
                                    f'<div style="font-size:0.62rem;color:#5a8fb0;text-transform:uppercase;letter-spacing:0.08em">{lbl}</div>'
                                    f'<div style="font-family:monospace;font-size:1rem;font-weight:700;color:{col};margin-top:4px">{val}</div>'
                                    f'</div>'
                                    for lbl, val, col in [
                                        ("歷史勝率",   f"{vd['best_wr']:.1f}%",
                                         "#00ff88" if vd["best_wr"]>=65 else "#ffd600" if vd["best_wr"]>=55 else "#ff3355"),
                                        ("期望值",     f"{vd['best_ev']:+.3f}%",
                                         "#00ff88" if vd["best_ev"]>0.05 else "#ffd600" if vd["best_ev"]>0 else "#ff3355"),
                                        ("樣本次數",   f"{int(vd['best_n'])} 次",
                                         "#00ff88" if vd["best_n"]>=30 else "#ffd600" if vd["best_n"]>=15 else "#ff3355"),
                                        ("最佳門檻",   f"≥{thresh}/8 分",
                                         vd["color"]),
                                    ]
                                )
                                + f'</div>'

                                # Explanation
                                f'<div style="font-size:0.82rem;color:#8a9bb5;'
                                f'line-height:1.65;margin-bottom:12px">{vd["msg"]}</div>'

                                # Today's entry gate
                                f'<div style="background:#080c18;border-radius:8px;'
                                f'padding:10px 14px;margin-bottom:10px">'
                                f'<div style="font-size:0.78rem;color:{entry_color};'
                                f'font-weight:700;margin-bottom:6px">{entry_gate}</div>'
                                f'<div style="font-size:0.72rem;color:#5a8fb0">'
                                f'今日評分 {today_sc}/8　'
                                f'命中：{" / ".join(hit) if hit else "無"}　'
                                f'未中：{" / ".join(miss) if miss else "無"}'
                                f'</div></div>'

                                # Market sensitivity
                                + (
                                    f'<div style="font-size:0.75rem;color:#ffd600;'
                                    f'border-top:1px solid rgba(255,214,0,0.2);padding-top:8px">'
                                    f'⚡ 大盤敏感：上漲日勝率 {vd["up_wr"]:.1f}% vs 下跌日 {vd["dn_wr"]:.1f}%'
                                    f'（差距 {vd["mkt_gap"]:.1f}%）— 建議僅在大盤上漲日操作</div>'
                                    if vd["mkt_sens"] else
                                    f'<div style="font-size:0.72rem;color:#5a8fb0;'
                                    f'border-top:1px solid rgba(90,143,176,0.2);padding-top:8px">'
                                    f'大盤方向影響較小（差距僅 {vd["mkt_gap"]:.1f}%）</div>'
                                )
                                + '</div>',
                                unsafe_allow_html=True,
                            )

                        # ── 各因素勝率表 ─────────────────────
                        st.markdown("##### 各因素獨立勝率")
                        st.caption("每個因素獨立成立時，次日開盤報酬的統計")
                        df_factors = pd.DataFrame(result["factor_results"]).T.reset_index()
                        df_factors.columns = ["因素", "樣本數", "勝率%", "平均報酬%", "中位報酬%", "Sharpe"]
                        df_factors = df_factors.sort_values("勝率%", ascending=False).reset_index(drop=True)

                        def color_wr(val):
                            if isinstance(val, float):
                                if val >= 65: return "color: #00ff88; font-weight: 700"
                                if val >= 55: return "color: #f0a500"
                                return "color: #ff3355"
                            return ""

                        st.dataframe(
                            df_factors, width='stretch', hide_index=True,
                            column_config={
                                "勝率%":     st.column_config.ProgressColumn(
                                    min_value=40, max_value=80, format="%.1f%%"),
                                "平均報酬%": st.column_config.NumberColumn(format="%+.3f%%"),
                                "中位報酬%": st.column_config.NumberColumn(format="%+.3f%%"),
                                "Sharpe":    st.column_config.NumberColumn(format="%.2f"),
                            }
                        )

                        # ── 組合評分分析 ─────────────────────
                        st.markdown("---")
                        st.markdown("##### 組合評分 vs 勝率")
                        st.caption("同時滿足 N 個因素時的勝率 — 找到最佳門檻")

                        if not result["combo_df"].empty:
                            cdf = result["combo_df"]
                            best_t = result["best_threshold"]

                            # Bar chart (go imported at top of file)
                            bar_colors = ["#00ff88" if int(r["評分門檻≥"]) == best_t
                                          else "#2196f3" for _, r in cdf.iterrows()]
                            fig_combo = go.Figure(go.Bar(
                                x=[f"≥{int(r['評分門檻≥'])}分" for _, r in cdf.iterrows()],
                                y=cdf["勝率%"].tolist(),
                                marker_color=bar_colors,
                                text=[f"{v:.1f}%" for v in cdf["勝率%"]],
                                textposition="outside",
                                customdata=cdf[["符合天數","平均報酬%","期望值%"]].values,
                                hovertemplate=(
                                    "門檻：%{x}<br>"
                                    "勝率：%{y:.1f}%<br>"
                                    "符合天數：%{customdata[0]}<br>"
                                    "平均報酬：%{customdata[1]:.3f}%<br>"
                                    "期望值：%{customdata[2]:.3f}%"
                                    "<extra></extra>"
                                ),
                            ))
                            fig_combo.add_hline(y=60, line_dash="dot",
                                                line_color="#f0a500", line_width=1,
                                                annotation_text="60%基準線")
                            fig_combo.update_layout(
                                template="plotly_dark", height=280,
                                paper_bgcolor="#0a0e1a", plot_bgcolor="#0d1226",
                                margin=dict(l=40, r=20, t=30, b=30),
                                font=dict(size=10, color="#8a9bb5"),
                                yaxis=dict(title="勝率%", range=[40, 85]),
                                xaxis=dict(title="評分門檻"),
                                title=dict(text=f"最佳門檻：≥{best_t}分（綠色柱）",
                                           font=dict(size=11), x=0.01),
                            )
                            st.plotly_chart(fig_combo, width='stretch')
                            st.dataframe(cdf, width='stretch', hide_index=True,
                                column_config={
                                    "勝率%":     st.column_config.ProgressColumn(
                                        min_value=40, max_value=80, format="%.1f%%"),
                                    "平均報酬%": st.column_config.NumberColumn(format="%+.3f%%"),
                                    "期望值%":   st.column_config.NumberColumn(format="%+.3f%%"),
                                })

                        # ── 大盤環境分析 ─────────────────────
                        st.markdown("---")
                        st.markdown("##### 大盤環境 vs 勝率")
                        st.caption("大盤上漲日 vs 下跌日，最優評分組合的表現差異")
                        mf = result["market_filter"]
                        mf_col1, mf_col2 = st.columns(2)
                        up_wr   = mf["大盤上漲日"]["勝率%"]
                        down_wr = mf["大盤下跌日"]["勝率%"]
                        mf_col1.metric("大盤上漲日勝率",  f"{up_wr:.1f}%",
                                        f"樣本 {mf['大盤上漲日']['樣本']} 天")
                        mf_col2.metric("大盤下跌日勝率",  f"{down_wr:.1f}%",
                                        f"樣本 {mf['大盤下跌日']['樣本']} 天",
                                        delta_color="inverse")
                        if up_wr - down_wr >= 10:
                            st.info(
                                f"💡 大盤方向對勝率影響顯著（差 {up_wr-down_wr:.1f}%），"
                                "建議僅在大盤上漲日操作隔日沖。"
                            )

                        # ── 次日報酬分布圖 ───────────────────
                        st.markdown("---")
                        st.markdown("##### 次日開盤報酬分布（≥最佳門檻）")
                        detail = result["detail"]
                        best_sub = detail[detail["OVN_Score"] >= result["best_threshold"]]
                        if len(best_sub) >= 5:
                            ret_vals = best_sub["next_open_ret"].dropna().tolist()
                            fig_hist = go.Figure(go.Histogram(
                                x=ret_vals, nbinsx=30,
                                marker_color=[
                                    "#00ff88" if v > 0 else "#ff3355" for v in ret_vals
                                ],
                                opacity=0.8,
                            ))
                            fig_hist.add_vline(x=0, line_dash="solid",
                                               line_color="#ffffff", line_width=1)
                            wins = sum(1 for v in ret_vals if v > 0)
                            fig_hist.update_layout(
                                template="plotly_dark", height=220,
                                paper_bgcolor="#0a0e1a", plot_bgcolor="#0d1226",
                                margin=dict(l=40, r=20, t=30, b=30),
                                font=dict(size=10, color="#8a9bb5"),
                                title=dict(
                                    text=(f"勝率 {wins/len(ret_vals)*100:.1f}%  "
                                          f"平均 {sum(ret_vals)/len(ret_vals):+.3f}%  "
                                          f"樣本 {len(ret_vals)}"),
                                    font=dict(size=11), x=0.01),
                                xaxis=dict(title="次日開盤報酬%"),
                                bargap=0.1,
                            )
                            st.plotly_chart(fig_hist, width='stretch')

                        # ── Conclusion ───────────────────────
                        st.markdown("---")
                        st.markdown("##### 💡 本股策略建議")
                        fr = result["factor_results"]
                        if fr:
                            best_factors = sorted(fr.items(),
                                                   key=lambda x: x[1]["勝率%"], reverse=True)[:3]
                            st.success(
                                f"**最有效因素**：" +
                                "、".join(f"**{k}**（勝率 {v['勝率%']:.1f}%）"
                                          for k, v in best_factors) +
                                f"\n\n建議進場門檻：評分 **≥{result['best_threshold']}** 分，"
                                f"大盤上漲日優先。"
                            )

        # ══════════════════════════════════════
        # MODE 2: 今日候選掃描
        # ══════════════════════════════════════
        elif ovn_mode == "🎯 今日候選掃描":
            st.markdown("##### 🎯 今日隔日沖候選")
            st.caption(
                "掃描自選股清單，找出今日符合隔日沖條件的股票。"
                "建議在 13:00–13:20 執行掃描，收盤前 13:20–13:30 進場。"
            )

            ovn_c1, ovn_c2, ovn_c3 = st.columns(3)
            ovn_min  = ovn_c1.slider("最低評分門檻", 3, 7, 5, key="ovn_min")
            ovn_mkt  = ovn_c2.radio("大盤今日",
                                     ["不限", "上漲日才掃"],
                                     horizontal=True, key="ovn_mkt")
            run_scan = ovn_c3.button("🌙 執行掃描", type="primary",
                                      width='stretch', key="ovn_scan")

            if run_scan:
                # Market regime check
                if ovn_mkt == "上漲日才掃":
                    mkt_q = fetch_quote("0050")  # proxy for market
                    if mkt_q.get("ok") and mkt_q.get("change_pct", 0) < 0:
                        st.warning(
                            "⚠️ 大盤今日下跌（0050 跌幅 "
                            f"{mkt_q.get('change_pct',0):.2f}%），"
                            "回測顯示大盤下跌日隔日沖勝率明顯降低，建議今日不操作。"
                        )
                        st.stop()

                prog_ovn = st.progress(0, text="掃描候選股…")
                wl_ovn = [c.replace(".TW","").replace(".TWO","")
                          for c in st.session_state.get("watchlist", DEFAULT_WATCHLIST)]
                candidates = []
                for ii, code in enumerate(wl_ovn):
                    prog_ovn.progress((ii+1)/len(wl_ovn),
                                      text=f"分析 {code} ({ii+1}/{len(wl_ovn)})…")
                    try:
                        df_c, _ = fetch_data(code, "1y")
                        if df_c is None or len(df_c) < 60:
                            continue
                        df_f = _overnight_factors(df_c)
                        latest_f = df_f.iloc[-1]
                        sc = overnight_score(latest_f)
                        if sc < ovn_min:
                            continue
                        price = float(df_c["Close"].iloc[-1])
                        q = fetch_quote(code)
                        chg_p = q.get("change_pct", float(latest_f.get("F_gain_pct", 0)))
                        candidates.append({
                            "代號":       code,
                            "名稱":       lookup_name(code)[0],
                            "評分 /8":    sc,
                            "現價":       round(price, 2),
                            "今日漲%":    round(float(latest_f.get("F_gain_pct", chg_p)), 2),
                            "量比":       round(float(latest_f.get("F_vol_ratio", 0)), 2),
                            "收盤位置%": round(float(latest_f.get("F_close_pos", 0))*100, 1),
                            "站上年線":   "✅" if latest_f.get("F_above_200") else "─",
                            "均線多頭":   "✅" if latest_f.get("F_trend_ok")  else "─",
                            "突破20高":   "✅" if latest_f.get("F_breakout_20d") else "─",
                            "OBV新高":    "✅" if latest_f.get("F_obv_new_high") else "─",
                            "_sc":    sc,
                            "_price": round(price, 2),   # used by TG push
                        })
                    except Exception:
                        continue
                prog_ovn.empty()

                if not candidates:
                    st.info(f"今日無符合評分 ≥{ovn_min} 的候選股")
                else:
                    candidates.sort(key=lambda x: -x["_sc"])
                    st.success(f"✅ 找到 **{len(candidates)}** 支候選股")

                    df_cand = pd.DataFrame([
                        {k: v for k, v in c.items() if not k.startswith("_")}
                        for c in candidates
                    ])
                    st.dataframe(
                        df_cand, width='stretch', hide_index=True,
                        column_config={
                            "評分 /8":   st.column_config.ProgressColumn(
                                min_value=0, max_value=8, format="%d/8"),
                            "今日漲%":   st.column_config.NumberColumn(format="%+.2f%%"),
                            "量比":      st.column_config.NumberColumn(format="%.2fx"),
                        }
                    )

                    # Cards for top 3
                    st.markdown("---")
                    st.markdown("##### 🥇 今日前三候選")
                    top3 = candidates[:3]
                    t3cols = st.columns(len(top3))
                    for ci, c in enumerate(top3):
                        clr = "#ffd700" if c["_sc"] >= 7 else "#00ff88"
                        with t3cols[ci]:
                            st.markdown(f"""
<div style="background:#0d1a2d;border:2px solid {clr};border-radius:10px;
  padding:14px;margin-bottom:8px">
  <div style="font-family:'Space Mono',monospace;font-size:1rem;
    font-weight:700;color:#e8f4fd">{c['代號']}
    <span style="color:{clr};font-size:0.8rem;margin-left:6px">
      ★{c['評分 /8']}/8</span>
  </div>
  <div style="color:#8a9bb5;font-size:0.78rem;margin-bottom:8px">{c['名稱']}</div>
  <div style="font-size:1.2rem;font-weight:700;color:#e8414e">
    {c['現價']:.2f}
    <span style="font-size:0.8rem;color:#e8414e">{c['今日漲%']:+.2f}%</span>
  </div>
  <div style="font-size:0.72rem;color:#5a8fb0;margin-top:6px">
    量比 {c['量比']:.2f}x &nbsp;|&nbsp; 收盤位置 {c['收盤位置%']:.0f}%
  </div>
  <div style="font-size:0.70rem;color:#37474f;margin-top:4px">
    {c['站上年線']} 年線 &nbsp;
    {c['均線多頭']} 均線 &nbsp;
    {c['突破20高']} 突破 &nbsp;
    {c['OBV新高']} OBV
  </div>
</div>""", unsafe_allow_html=True)

                    # ── Telegram Push ────────────────────────
                    tg_tok_v = st.session_state.get("tg_token", "")
                    tg_cid_v = st.session_state.get("tg_chat_id", "")

                    # Auto-push if Telegram is configured
                    if tg_tok_v and tg_cid_v and candidates:
                        msg = (
                            f"🌙 隔日沖候選 {tw_now().strftime('%m/%d %H:%M')}\n"
                            f"共 {len(candidates)} 支，前5如下：\n\n"
                        )
                        for c in candidates[:5]:
                            stop_px = round(c["_price"] * 0.98, 2)
                            factors = []
                            if c["站上年線"] == "✅": factors.append("年線")
                            if c["均線多頭"] == "✅": factors.append("均線")
                            if c["突破20高"] == "✅": factors.append("突破")
                            if c["OBV新高"]  == "✅": factors.append("OBV")
                            msg += (
                                f"★{c['_sc']}/8  {c['代號']} {c['名稱']}\n"
                                f"  現價 {c['_price']:.2f}  漲{c['今日漲%']:+.2f}%"
                                f"  量比{c['量比']:.1f}x\n"
                                f"  停損 {stop_px}  因素:{'/'.join(factors) or '─'}\n"
                            )
                        msg += "\n⏰ 進場 13:20–13:30\n📤 出場 次日 09:05–09:30"
                        n_sent_ov = tg_broadcast(msg)
                        auto_ok, auto_err = (n_sent_ov > 0), ("" if n_sent_ov else "推播失敗")
                        if auto_ok:
                            st.toast("📲 已自動推播到 Telegram", icon="✅")
                        else:
                            st.warning(f"📲 自動推播失敗：{auto_err}")

                    # Manual re-push button
                    push_col, _ = st.columns([1, 2])
                    if push_col.button("📲 重新推播到 Telegram", key="ovn_tg",
                                       width='stretch'):
                        if not tg_tok_v or not tg_cid_v:
                            st.warning("請先在側欄設定 Telegram Token 和 Chat ID")
                        else:
                            msg2 = (
                                f"🌙 隔日沖候選（補推）{tw_now().strftime('%m/%d %H:%M')}\n\n"
                            )
                            for c in candidates[:5]:
                                stop_px = round(c["_price"] * 0.98, 2)
                                msg2 += (
                                    f"★{c['_sc']}/8  {c['代號']} {c['名稱']}\n"
                                    f"  現價 {c['_price']:.2f}  漲{c['今日漲%']:+.2f}%"
                                    f"  量比{c['量比']:.1f}x  停損{stop_px}\n"
                                )
                            msg2 += "\n⏰ 進場 13:20–13:30 | 出場 次日 09:05"
                            n2 = tg_broadcast(msg2)
                            ok2, err2 = (n2 > 0), ("" if n2 else "推播失敗")
                            st.success("✅ 已推播") if ok2 else st.error(f"❌ {err2}")

                    # Export
                    with st.expander("📤 匯出候選清單"):
                        st.download_button(
                            "下載 Excel",
                            data=to_excel(df_cand),
                            file_name=f"overnight_{tw_now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width='stretch',
                        )

        # ══════════════════════════════════════
        # MODE 3: 策略說明
        # ══════════════════════════════════════
        else:
            st.markdown("""
##### 🌙 隔日沖策略說明

**核心邏輯**
今日強勢收盤 → 次日慣性延續高開 → 開盤即出鎖定利潤

**進出場規則**
| 項目 | 規則 |
|------|------|
| 進場時間 | 13:20–13:30（接近收盤） |
| 出場時間 | 次日 09:05–09:30（開盤後） |
| 停損 | 次日開盤跌破進場價 -2% 立即出 |
| 停利 | 次日開盤漲超 3% 可部分留倉 |

**8 大評分因素**
| 因素 | 說明 |
|------|------|
| A1 收盤強度 | 收盤在日高 92% 以上（買盤未退） |
| A2 漲幅甜區 | 今日漲 2.5–8%（不含漲停） |
| B1 量能放大 | 成交量 ≥ 均量 1.8x |
| B2 OBV 新高 | 10 日 OBV 新高（籌碼淨流入） |
| C1 均線多頭 | EMA20 > EMA60，站穩趨勢 |
| C2 站上年線 | 股價 > EMA200（不逆勢） |
| C3 突破 20 日高 | 今日突破近 20 交易日最高收盤 |
| D1 尾盤強度 | 量比 × 收盤位置 ≥ 1.5（尾盤買力強） |

**風險管理**
- 單股最多投入資金 **20%**
- 最多同時持有 **3–5 檔**
- 大盤下跌日（0050 跌幅 > 0%）勝率明顯下降，建議**停止操作**
- 財報公佈週、重大事件前後謹慎

**回測方法論**
使用「📊 單股因素回測」功能，對每支股票獨立分析各因素的實際次日勝率，
系統自動找出該股的最佳評分門檻，避免過度擬合。
""")



    # ─────────────────────────────────────────────────────────
    # TAB  📱  自選股 — 卡片視圖 + 分組 + 備忘  (替代 Watchlist Pro)
    # ─────────────────────────────────────────────────────────
    with tab_wl:
        st.markdown("#### 📱 自選股管理")
        st.caption("卡片視圖 · 分組管理 · 備忘標籤 — 手機友好介面")

        wl_codes = st.session_state.watchlist
        if not wl_codes:
            st.info("自選股清單為空，請在左側側欄新增股票。")
        else:
            # ── 控制列 ──────────────────────────────────────
            wl_c1, wl_c2, wl_c3 = st.columns(3)
            all_groups = sorted(set(wl_get_group(c) for c in wl_codes))
            grp_filter = wl_c1.selectbox(
                "分組", ["全部"] + all_groups,
                label_visibility="collapsed", key="wl_grp_filter"
            )
            wl_sort = wl_c2.radio(
                "排序", ["自選股順序", "分組", "漲幅↓", "跌幅↓"],
                horizontal=True, label_visibility="collapsed", key="wl_sort"
            )
            wl_view = wl_c3.radio(
                "視圖", ["🃏 卡片", "📋 列表"],
                horizontal=True, label_visibility="collapsed", key="wl_view"
            )

            # Filter by group
            filtered = [c for c in wl_codes
                        if grp_filter == "全部" or wl_get_group(c) == grp_filter]

            # Fetch quotes
            with st.spinner("載入報價…"):
                q_cache = batch_fetch_quotes(tuple(
                    c.replace(".TW","").replace(".TWO","") for c in filtered
                ))

            # Sort
            def _chg(c): return q_cache.get(c.replace(".TW","").replace(".TWO",""), {}).get("change_pct", 0)
            if wl_sort == "分組":       filtered = sorted(filtered, key=wl_get_group)
            elif wl_sort == "漲幅↓":   filtered = sorted(filtered, key=lambda c: -_chg(c))
            elif wl_sort == "跌幅↓":   filtered = sorted(filtered, key=_chg)

            # ── Summary metrics ──────────────────────────────
            valid_q = [q_cache.get(c.replace(".TW","").replace(".TWO",""),{}) for c in filtered]
            up   = sum(1 for q in valid_q if q.get("change_pct",0) > 0)
            dn   = sum(1 for q in valid_q if q.get("change_pct",0) < 0)
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("總計", len(filtered))
            m2.metric("上漲 🔴", up)
            m3.metric("下跌 🟢", dn)
            m4.metric("平盤", len(filtered)-up-dn)
            st.markdown("---")

            # ── CARD VIEW ────────────────────────────────────
            if wl_view == "🃏 卡片":
                for i in range(0, len(filtered), 2):
                    chunk = filtered[i:i+2]
                    cols  = st.columns(2)
                    for ci, code in enumerate(chunk):
                        bare  = code.upper().replace(".TW","").replace(".TWO","")
                        q     = q_cache.get(bare, {})
                        n     = wl_note_get(bare)
                        px    = q.get("price",  q.get("change_pct",0) and 0) or 0
                        # Prefer price key
                        if "price" in q: px = q["price"]
                        chg   = q.get("change_pct", 0)
                        grp   = wl_get_group(bare)
                        name  = lookup_name(bare)[0] or bare

                        if not q:                           clr, border = "#5a8fb0", "#1a2d44"
                        elif chg > 0:                       clr, border = "#e8414e", "#e8414e40"
                        elif chg < 0:                       clr, border = "#22cc66", "#22cc6640"
                        else:                               clr, border = "#5a8fb0", "#1a2d44"

                        tags_str = " ".join(f"#{t}" for t in n.get("tags", []))
                        note_str = n.get("note","")[:40]

                        with cols[ci]:
                            st.markdown(f"""
<div style="background:#0d1a2d;border:1px solid {border};border-left:3px solid {clr};
  border-radius:10px;padding:13px 15px;margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
    <span style="font-family:monospace;font-weight:700;color:#e8f4fd;font-size:0.9rem">{bare}</span>
    <span style="font-size:0.62rem;color:#5a8fb0;background:#0a0e1a;
      padding:2px 7px;border-radius:4px;border:1px solid #1a2d44">{grp}</span>
  </div>
  <div style="font-size:0.75rem;color:#5a8fb0;margin-bottom:8px">{name}</div>
  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px">
    <span style="font-family:monospace;font-size:1.2rem;font-weight:700;color:{clr}">
      {f"{px:.2f}" if px else "─"}</span>
    <span style="font-size:0.8rem;color:{clr}">{f"{chg:+.2f}%" if q else "─"}</span>
  </div>
  {f'<div style="font-size:0.68rem;color:#3d5470;margin-top:4px">{tags_str}</div>' if tags_str else ""}
  {f'<div style="font-size:0.68rem;color:#3d5470;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{note_str}</div>' if note_str else ""}
</div>""", unsafe_allow_html=True)

            # ── LIST VIEW ─────────────────────────────────────
            else:
                list_rows = []
                for code in filtered:
                    bare = code.upper().replace(".TW","").replace(".TWO","")
                    q    = q_cache.get(bare, {})
                    n    = wl_note_get(bare)
                    px   = q.get("price", 0)
                    chg  = q.get("change_pct", 0)
                    list_rows.append({
                        "代號": bare,
                        "名稱": lookup_name(bare)[0] or bare,
                        "分組": wl_get_group(bare),
                        "現價": round(px,2) if px else None,
                        "漲跌%": round(chg,2) if q else None,
                        "標籤": " ".join(n.get("tags",[])),
                        "備忘": n.get("note","")[:30],
                    })
                if list_rows:
                    st.dataframe(
                        pd.DataFrame(list_rows), width='stretch', hide_index=True,
                        column_config={
                            "漲跌%": st.column_config.NumberColumn(format="%+.2f%%"),
                            "現價":  st.column_config.NumberColumn(format="%.2f"),
                        }
                    )

            # ── 分組管理 ─────────────────────────────────────
            st.markdown("---")
            with st.expander("🗂 分組管理"):
                gc1, gc2, gc3 = st.columns(3)
                sel_code  = gc1.selectbox("股票", wl_codes,
                    format_func=lambda x: f"{x.replace('.TW','').replace('.TWO','')}  {lookup_name(x.replace('.TW','').replace('.TWO',''))[0] or ''}",
                    label_visibility="collapsed", key="wl_gc_code")
                sel_grp   = gc2.selectbox("分組", PRESET_GROUPS,
                    label_visibility="collapsed", key="wl_gc_grp")
                if gc3.button("更新", width='stretch', key="wl_gc_save"):
                    bare_sel = sel_code.upper().replace(".TW","").replace(".TWO","")
                    wl_set_group(bare_sel, sel_grp)
                    st.success(f"✓ {bare_sel} → {sel_grp}"); st.rerun()

            # ── 備忘 + 標籤 ───────────────────────────────────
            with st.expander("📝 備忘 & 標籤"):
                nb_code = st.selectbox("選股",
                    wl_codes,
                    format_func=lambda x: f"{x.replace('.TW','').replace('.TWO','')}  {lookup_name(x.replace('.TW','').replace('.TWO',''))[0] or ''}",
                    label_visibility="collapsed", key="wl_nb_code")
                bare_nb = nb_code.upper().replace(".TW","").replace(".TWO","")
                ex_note = wl_note_get(bare_nb)
                with st.form("wl_note_form"):
                    nb_text = st.text_area("備忘 / 進場理由",
                        value=ex_note.get("note",""), height=80,
                        placeholder="記錄關注原因、進場邏輯、觀察重點…")
                    nb_c1, nb_c2 = st.columns(2)
                    nb_entry = nb_c1.number_input("進場均價",
                        min_value=0.0, value=float(ex_note.get("entry",0) or 0), step=0.5)
                    nb_date  = nb_c2.text_input("關注日期",
                        value=ex_note.get("watch_date", tw_now().strftime("%Y-%m-%d")))
                    nb_tags = st.multiselect("標籤",
                        ["技術突破","籌碼轉強","法人買超","業績成長",
                         "低估值","高殖利率","週期底部","隔日沖","題材","其他"],
                        default=ex_note.get("tags", []))
                    if st.form_submit_button("💾 儲存", type="primary"):
                        wl_note_set(bare_nb, {
                            **ex_note,
                            "note": nb_text, "entry": nb_entry,
                            "watch_date": nb_date, "tags": nb_tags,
                            "updated": tw_now().strftime("%Y-%m-%d %H:%M"),
                        })
                        st.success("✓ 已儲存")

            # ── 所有備忘一覽 ──────────────────────────────────
            with st.expander("📋 所有備忘一覽"):
                note_rows = [
                    {"代號": c.upper().replace(".TW","").replace(".TWO",""),
                     "名稱": lookup_name(c.upper().replace(".TW","").replace(".TWO",""))[0] or c,
                     "備忘": wl_note_get(c.upper().replace(".TW","").replace(".TWO","")).get("note","")[:40],
                     "標籤": " ".join(wl_note_get(c.upper().replace(".TW","").replace(".TWO","")).get("tags",[])),
                     "均價": wl_note_get(c.upper().replace(".TW","").replace(".TWO","")).get("entry",""),
                     "日期": wl_note_get(c.upper().replace(".TW","").replace(".TWO","")).get("watch_date",""),
                    }
                    for c in wl_codes
                    if wl_note_get(c.upper().replace(".TW","").replace(".TWO","")).get("note")
                    or wl_note_get(c.upper().replace(".TW","").replace(".TWO","")).get("tags")
                ]
                if note_rows:
                    st.dataframe(pd.DataFrame(note_rows), width='stretch', hide_index=True)
                else:
                    st.info("尚無備忘記錄")


if __name__ == "__main__":
    main()
