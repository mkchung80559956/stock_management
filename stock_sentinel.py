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
    """
    Returns df copy with Signal, Signal_Detail, CCI, RSI, MACD*, Vol_MA, ATR columns.
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

    # ── Volume conditions ──
    vol_ratio            = df["Volume"] / (df["Vol_MA"] + 1e-8)
    df["Vol_High"]       = vol_ratio >= p["vol_multiplier"]
    df["Vol_Strong"]     = vol_ratio >= p["vol_strong_multiplier"]
    df["Vol_Shrink"]     = vol_ratio < 0.8

    # ── CCI crossovers ──
    cci_prev = df["CCI"].shift(1)
    df["CCI_X_neg100_UP"]  = (cci_prev < -100) & (df["CCI"] >= -100)
    df["CCI_X_zero_UP"]    = (cci_prev <    0) & (df["CCI"] >=    0)
    df["CCI_X_pos100_UP"]  = (cci_prev <  100) & (df["CCI"] >=  100)
    df["CCI_X_pos100_DN"]  = (cci_prev >= 100) & (df["CCI"] <   100)

    # ── Price action ──
    df["LowerShadow"]  = has_long_lower_shadow(df["Open"], df["Close"], df["Low"])
    df["BullEngulf"]   = is_bullish_engulf(df["Open"], df["Close"])
    df["UpperShadow"]  = has_long_upper_shadow(df["Open"], df["Close"], df["High"])
    df["PriceUp"]      = df["Close"] > df["Close"].shift(1)
    df["PriceUp_VolDN"]= df["PriceUp"] & (df["Volume"] < df["Volume"].shift(1))
    df["BlackCandle"]  = df["Close"] < df["Open"]

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

    # 1. 強勢追漲：CCI突破+100 + 強放量 → 噴發段
    m1 = df["CCI_X_pos100_UP"] & df["Vol_Strong"]
    sig[m1]    = "BREAKOUT_BUY"
    detail[m1] = "噴發段：CCI突破+100 + 強放量（倍量追強）"

    # 2. 假突破：CCI突破+100 but 縮量 → 誘多
    m2 = df["CCI_X_pos100_UP"] & ~df["Vol_High"]
    sig[m2]    = "FAKE_BREAKOUT"
    detail[m2] = "誘多警告：CCI突破+100 but 量不配合"

    # 3. 強買：CCI突破-100 + 放量 + 止跌K線
    m3 = df["CCI_X_neg100_UP"] & df["Vol_High"] & (df["LowerShadow"] | df["BullEngulf"])
    sig[m3 & (sig == "NEUTRAL")] = "STRONG_BUY"
    detail[m3 & (sig == "STRONG_BUY")] = "強買：CCI突破-100 + 放量 + 止跌K（轉折確立）"

    # 4. 底背離買入
    m4 = df["BullDiv"] & df["Vol_High"]
    sig[m4 & (sig == "NEUTRAL")] = "DIV_BUY"
    detail[m4 & (sig == "DIV_BUY")] = "底背離：股價創低但CCI底部抬高 + 放量確認"

    # 5. 一般買入：CCI突破0軸 + 放量
    m5 = df["CCI_X_zero_UP"] & df["Vol_High"]
    sig[m5 & (sig == "NEUTRAL")] = "BUY"
    detail[m5 & (sig == "BUY")] = "買入：CCI突破0軸 + 放量確認（動能轉正）"

    # 6. 觀望：CCI突破-100 但縮量（弱勢反彈）
    m6 = df["CCI_X_neg100_UP"] & ~df["Vol_High"]
    sig[m6 & (sig == "NEUTRAL")] = "WATCH"
    detail[m6 & (sig == "WATCH")] = "觀望：CCI突破-100 but 量縮（弱反彈，容易再跌）"

    # 7. 強賣：CCI跌破+100 + 量縮 or 爆量黑K
    m7 = df["CCI_X_pos100_DN"] & (df["Vol_Shrink"] | (df["Vol_High"] & df["BlackCandle"]))
    sig[m7 & (sig == "NEUTRAL")] = "STRONG_SELL"
    detail[m7 & (sig == "STRONG_SELL")] = "強賣：CCI跌破+100 + 買盤竭盡（高檔撤退訊號）"

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
    df["Vol_Ratio"]     = vol_ratio.round(2)

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

def _resolve_symbol(code: str) -> str:
    """
    Resolve a bare Taiwan stock code to its Yahoo Finance symbol.
    If already has suffix (.TW / .TWO), return as-is.
    Otherwise try .TW first; if that returns empty data try .TWO (OTC/櫃買).
    """
    if code.upper().endswith((".TW", ".TWO")):
        return code
    return code  # will be resolved with fallback in fetch_data


@st.cache_data(ttl=60)
def fetch_name(code: str) -> tuple[str, str]:
    """Return (chinese_name, market_label) for a code.
    market_label: '上市' | '上櫃' | ''
    """
    for suffix, label in [(".TW", "上市"), (".TWO", "上櫃")]:
        sym = code if code.upper().endswith((".TW", ".TWO")) else code + suffix
        try:
            info = yf.Ticker(sym).fast_info
            # fast_info doesn't have name; fall to .info for name
            ticker_info = yf.Ticker(sym).info
            name = (ticker_info.get("longName") or
                    ticker_info.get("shortName") or "")
            # Clean up common suffixes from yfinance
            for strip in [" Co., Ltd.", " Co.,Ltd.", " Corporation",
                           " Inc.", " Ltd.", "股份有限公司", "有限公司"]:
                name = name.replace(strip, "")
            if name:
                return name.strip(), label
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

    # ── Panel 1: K線 + EMA + BB ──
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price",
        increasing_fillcolor="#e8414e", increasing_line_color="#e8414e",
        decreasing_fillcolor="#22cc66", decreasing_line_color="#22cc66",
    ), row=1, col=1)

    for col_name, color, width, dash in [
        ("EMA1",     "#f0a500", 1.3, "solid"),
        ("EMA2",     "#2196f3", 1.3, "solid"),
        ("BB_Upper", "#607d8b", 0.8, "dot"),
        ("BB_Lower", "#607d8b", 0.8, "dot"),
        ("BB_Mid",   "#546e7a", 0.7, "dash"),
    ]:
        if col_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col_name], name=col_name,
                line=dict(color=color, width=width, dash=dash),
                showlegend=False,
            ), row=1, col=1)

    # BB fill
    if "BB_Upper" in df.columns and "BB_Lower" in df.columns:
        fig.add_trace(go.Scatter(
            x=pd.concat([pd.Series(df.index), pd.Series(df.index[::-1])]),
            y=pd.concat([df["BB_Upper"], df["BB_Lower"][::-1]]),
            fill="toself", fillcolor="rgba(100,140,180,0.06)",
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

    # ── Panel 2: CCI ──
    cci_colors = ["#e8414e" if v > 100 else "#22cc66" if v < -100 else "#455a64"
                  for v in df["CCI"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df.index, y=df["CCI"], marker_color=cci_colors, name="CCI", showlegend=False,
    ), row=2, col=1)
    for level, col in [(100, "rgba(232,65,78,0.35)"), (-100, "rgba(34,204,102,0.35)"), (0, "#37474f")]:
        fig.add_hline(y=level, line_dash="dot", line_color=col, line_width=1, row=2, col=1)

    # ── Panel 3: RSI ──
    fig.add_trace(go.Scatter(
        x=df.index, y=df["RSI"], name="RSI",
        line=dict(color="#e040fb", width=1.5), showlegend=False,
    ), row=3, col=1)
    for level, col in [(70, "rgba(232,65,78,0.35)"), (30, "rgba(34,204,102,0.35)"), (50, "#37474f")]:
        fig.add_hline(y=level, line_dash="dot", line_color=col, line_width=1, row=3, col=1)

    # ── Panel 4: MACD ──
    hist_colors = ["#e8414e" if v >= 0 else "#22cc66" for v in df["MACD_Hist"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df.index, y=df["MACD_Hist"], marker_color=hist_colors, name="Hist", showlegend=False,
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD"], name="MACD",
        line=dict(color="#2196f3", width=1.3), showlegend=False,
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD_Sig"], name="Signal",
        line=dict(color="#f0a500", width=1.3), showlegend=False,
    ), row=4, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=820,
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0d1226",
        xaxis_rangeslider_visible=False,
        margin=dict(l=55, r=20, t=20, b=10),
        font=dict(family="Space Mono, monospace", size=11, color="#8a9bb5"),
    )
    for i in range(1, 5):
        fig.update_yaxes(
            gridcolor="#1a2a3a", zeroline=False,
            tickfont=dict(size=10), row=i, col=1,
        )
    fig.update_xaxes(showgrid=False, rangeslider_visible=False)

    # Panel labels
    annotations = [
        dict(x=0.01, y=1.0,  xref="paper", yref="paper", text=f"<b>{symbol}</b> · K線 / EMA / BB",  showarrow=False, font=dict(color="#8a9bb5", size=11)),
        dict(x=0.01, y=0.53, xref="paper", yref="paper", text=f"CCI({p['cci_period']})",            showarrow=False, font=dict(color="#8a9bb5", size=11)),
        dict(x=0.01, y=0.33, xref="paper", yref="paper", text=f"RSI({p['rsi_period']})",            showarrow=False, font=dict(color="#8a9bb5", size=11)),
        dict(x=0.01, y=0.15, xref="paper", yref="paper", text="MACD",                               showarrow=False, font=dict(color="#8a9bb5", size=11)),
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
    # 上市 (TSE)
    "2330","2317","2454","2382","3711",
    "2308","2303","6505","2886","2891",
    # 上櫃 (OTC/TWO) — add .TWO suffix so auto-detect works instantly
    "6531.TWO","3105.TWO","5439.TWO","6510.TWO","3034.TWO",
]


def main():
    # ── Header ──────────────────────────────────
    st.markdown("""
    <div class="sentinel-header">
      <div class="sentinel-title">🛡️ Sentinel Pro v2.0</div>
      <div class="sentinel-sub">台股多股掃描器 ｜ CCI × 成交量 × 價格行為 ｜ 量價策略訊號系統</div>
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
        run_scan = c_btn.button("🔄 掃描 + 更新報價", type="primary", width='stretch')

        if run_scan or not st.session_state.scan_rows:
            rows     = []
            prog     = st.progress(0, text="初始化...")
            total_n  = len(st.session_state.watchlist)

            for i, code in enumerate(st.session_state.watchlist):
                prog.progress((i + 1) / total_n, text=f"分析 {code} ({i+1}/{total_n})…")
                df_raw, err = fetch_data(code, data_period)
                if df_raw is None or len(df_raw) < 60:
                    continue

                df_sig = generate_signals(df_raw, params)
                bt     = backtest(df_sig, holding_days, profit_target, stop_loss)
                quote  = fetch_quote(code)
                cn_name, mkt_label = fetch_name(code)

                latest = df_sig.iloc[-1]
                prev   = df_sig.iloc[-2]
                price  = quote.get("price") or round(latest["Close"], 2)
                chg_p  = quote.get("change_pct") or ((latest["Close"] - prev["Close"]) / prev["Close"] * 100)

                # Latest signal (past 3 bars)
                recent_sig, recent_detail = "NEUTRAL", ""
                for j in range(min(3, len(df_sig))):
                    s = df_sig.iloc[-(j + 1)]["Signal"]
                    if s != "NEUTRAL":
                        recent_sig    = s
                        recent_detail = df_sig.iloc[-(j + 1)]["Signal_Detail"]
                        break

                # ATR-based stop
                atr_stop = round(price - latest["ATR"] * 1.5, 2) if pd.notna(latest["ATR"]) else "-"

                bare = code.upper().replace(".TW", "").replace(".TWO", "")
                rows.append({
                    "代號":     bare,
                    "名稱":     cn_name,
                    "市場":     mkt_label,
                    "最新價":   price,
                    "漲跌%":    round(chg_p, 2),
                    f"CCI({cci_period})": round(latest["CCI"], 1) if pd.notna(latest["CCI"]) else "-",
                    f"RSI({rsi_period})": round(latest["RSI"], 1) if pd.notna(latest["RSI"]) else "-",
                    "量/均量":  round(latest["Vol_Ratio"], 2) if pd.notna(latest["Vol_Ratio"]) else "-",
                    "訊號":     SIGNAL_LABEL.get(recent_sig, recent_sig),
                    "說明":     recent_detail,
                    "止損參考": atr_stop,
                    "勝率%":    bt["win_rate"],
                    "交易數":   bt["total"],
                    "平均報酬%": bt["avg_return"],
                    "_sig_key": recent_sig,
                })

            prog.empty()
            st.session_state.scan_rows = rows

        rows = st.session_state.scan_rows
        if rows:
            # Sort by signal priority
            rows_sorted = sorted(rows, key=lambda r: SIGNAL_ORDER.get(r["_sig_key"], 9))
            df_display  = pd.DataFrame(rows_sorted)

            # Drop internal key
            show_cols = [c for c in df_display.columns if c != "_sig_key"]
            df_display = df_display[show_cols]

            st.dataframe(
                df_display,
                width='stretch',
                height=520,
                column_config={
                    "漲跌%":    st.column_config.NumberColumn(format="%.2f%%"),
                    "勝率%":    st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
                    "平均報酬%": st.column_config.NumberColumn(format="%.2f%%"),
                },
                hide_index=True,
            )

            # Signal legend
            st.markdown("""
            <div class="signal-legend">
            🟠 <b>噴發買</b>：CCI突破+100 + 強放量（追強訊號）　
            🟢 <b>強買</b>：CCI突破-100 + 放量 + 止跌K　
            🔵 <b>買入</b>：CCI突破0軸 + 放量　
            🟢 <b>底背離</b>：股價創低但CCI抬高 + 放量　
            ⚪ <b>觀望</b>：CCI突破-100 but 縮量（弱反彈）　
            🔴 <b>強賣</b>：CCI跌破+100 + 量縮/黑K　
            🟡 <b>賣出</b>：RSI超買+價漲量縮+上影線　
            🟣 <b>誘多</b>：CCI突破+100 but 量不配合
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
        else:
            st.info("按下「掃描 + 更新報價」開始分析自選股")

    # ─────────────────────────────────────────
    # TAB 2  個股分析
    # ─────────────────────────────────────────
    with tab_drill:
        st.markdown("#### 🔬 個股深度分析（130 根 K 線）")
        c1, c2, c3 = st.columns([3, 2, 1])
        sel_from_wl = c1.selectbox(
            "從自選股選擇", st.session_state.watchlist,
            format_func=lambda x: x if x.upper().endswith((".TW", ".TWO"))
                                     else f"{x}.TW",
        )
        custom_code = c2.text_input("或直接輸入代號", placeholder="e.g. 0050 / 6531.TWO")
        load_btn    = c3.button("📊 載入", type="primary", width='stretch')

        target = custom_code.strip() or sel_from_wl

        if load_btn:
            with st.spinner(f"載入 {target} …"):
                df_raw, err = fetch_data(target, data_period)
            if df_raw is None:
                st.error(f"無法取得資料：{err}")
            else:
                df_sig = generate_signals(df_raw, params)
                latest = df_sig.iloc[-1]
                prev   = df_sig.iloc[-2]
                quote  = fetch_quote(target)
                cn_name, mkt_label = fetch_name(target)

                price   = quote.get("price")    or round(latest["Close"], 2)
                chg     = quote.get("change")   or (latest["Close"] - prev["Close"])
                chg_pct = quote.get("change_pct") or (chg / prev["Close"] * 100)

                # Name / market banner
                bare_t = target.upper().replace(".TW", "").replace(".TWO", "")
                mkt_color = "#22cc66" if mkt_label == "上櫃" else "#00aaff"
                st.markdown(
                    f'<span style="font-size:1.1rem;font-weight:700;color:#e8f4fd">'
                    f'{bare_t}</span> '
                    f'<span style="background:{mkt_color};color:#000;padding:2px 8px;'
                    f'border-radius:4px;font-size:0.75rem;font-weight:700">{mkt_label}</span> '
                    f'<span style="color:#8a9bb5;font-size:0.95rem">{cn_name}</span>',
                    unsafe_allow_html=True,
                )

                # Metrics row
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("最新價", f"{price:.2f}",
                          f"{chg:+.2f}  ({chg_pct:+.2f}%)")
                m2.metric(f"CCI({cci_period})",
                          f"{latest['CCI']:.1f}" if pd.notna(latest["CCI"]) else "-")
                m3.metric(f"RSI({rsi_period})",
                          f"{latest['RSI']:.1f}" if pd.notna(latest["RSI"]) else "-")
                m4.metric("量/均量",
                          f"{latest['Vol_Ratio']:.2f}x" if pd.notna(latest["Vol_Ratio"]) else "-")
                m5.metric("訊號", SIGNAL_LABEL.get(latest["Signal"], "─"))
                atr_val = latest["ATR"]
                atr_stop = price - atr_val * 1.5 if pd.notna(atr_val) else None
                m6.metric("ATR停損參考",
                          f"{atr_stop:.2f}" if atr_stop else "-")

                # Chart
                fig = build_chart(df_sig, target, params)
                st.plotly_chart(fig, width='stretch')

                # Recent signal log
                sig_hist = df_sig[df_sig["Signal"] != "NEUTRAL"][
                    ["Close", "Volume", "CCI", "RSI", "Vol_Ratio", "Signal", "Signal_Detail"]
                ].tail(20)
                if not sig_hist.empty:
                    st.markdown("##### 📋 近期訊號記錄（最新 20 筆）")
                    sig_hist = sig_hist.copy()
                    sig_hist["Signal"] = sig_hist["Signal"].map(
                        lambda x: SIGNAL_LABEL.get(x, x)
                    )
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
        bt_cust = c2.text_input("或直接輸入代號", placeholder="e.g. 0050 / 6531.TWO", key="bt_custom")
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
