"""
Watchlist Pro — 台股自選股管理工具
A companion tool to Sentinel Pro.
Shared watchlist via /tmp/shared_watchlist.json
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import pytz
import urllib.request as _urllib_req
import urllib.parse  as _urllib_parse
import re as _re
import io as _io
from datetime import datetime, date

# ── App config ───────────────────────────────────────────
st.set_page_config(
    page_title="Watchlist Pro",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "1.0"
APP_UPDATED = "2026-04-14"

# ── Shared file paths (same /tmp as Sentinel Pro) ────────
WATCHLIST_FILE = "/tmp/watchlist_pro_codes.json"  # independent from Sentinel Pro
NOTES_FILE     = "/tmp/watchlist_notes.json"    # {code: {note, target, stop, reason, group}}

TZ_TW = pytz.timezone("Asia/Taipei")

def tw_now():
    return datetime.now(TZ_TW)

# ── Telegram helpers ──────────────────────────────────────
ALERT_SENT_FILE = "/tmp/watchlist_alerts_sent.json"  # {code+type: last_sent_date}

def _tg_send(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """Send Telegram message. Returns (ok, error)."""
    if not token or not chat_id:
        return False, "Token 或 Chat ID 未設定"
    clean = _re.sub(r'<[^>]+>', '', text)
    try:
        url  = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
        data = _urllib_parse.urlencode({
            "chat_id": str(chat_id).strip(),
            "text":    clean,
        }).encode()
        req = _urllib_req.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with _urllib_req.urlopen(req, timeout=10) as r:
            return (True, "") if r.status == 200 else (False, f"HTTP {r.status}")
    except Exception as e:
        err = str(e)
        if hasattr(e, 'read'):
            try: err += " | " + e.read().decode()[:200]
            except Exception: pass
        return False, err


def _alert_sent_today(code: str, alert_type: str) -> bool:
    """Returns True if we already sent this alert today."""
    try:
        if os.path.exists(ALERT_SENT_FILE):
            with open(ALERT_SENT_FILE) as f:
                sent = json.load(f)
        else:
            sent = {}
        key  = f"{code}_{alert_type}"
        today = tw_now().strftime("%Y-%m-%d")
        return sent.get(key) == today
    except Exception:
        return False


def _mark_alert_sent(code: str, alert_type: str) -> None:
    try:
        sent = {}
        if os.path.exists(ALERT_SENT_FILE):
            with open(ALERT_SENT_FILE) as f:
                sent = json.load(f)
        sent[f"{code}_{alert_type}"] = tw_now().strftime("%Y-%m-%d")
        tmp = ALERT_SENT_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(sent, f)
        os.replace(tmp, ALERT_SENT_FILE)
    except Exception:
        pass



# ── Google Sheets helpers ─────────────────────────────────
_GS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"

def gs_write_portfolio(sheet_id: str, token: str, trades: list) -> tuple[bool, str]:
    """Write portfolio trades to Sheet named 'Portfolio' in standard format."""
    if not sheet_id or not token:
        return False, "Sheet ID 或 Token 未設定"
    headers = [["商品","交易日","交易別","股數","成交價","價金","手續費","交易稅","備註"]]
    rows = headers + [[
        t.get("商品",""), t.get("交易日",""), t.get("交易別","現買"),
        t.get("股數",0), t.get("成交價",0), t.get("價金",0),
        t.get("手續費",0), t.get("交易稅",0), t.get("備註",""),
    ] for t in trades]
    try:
        # Clear
        url = f"{_GS_BASE}/{sheet_id}/values/Portfolio!A1:I10000:clear"
        req = _urllib_req.Request(url, data=b"{}", method="POST")
        req.add_header("Authorization", f"Bearer {token.strip()}")
        req.add_header("Content-Type", "application/json")
        with _urllib_req.urlopen(req, timeout=10): pass
        # Write
        url2 = f"{_GS_BASE}/{sheet_id}/values/Portfolio!A1?valueInputOption=USER_ENTERED"
        body = json.dumps({"values": rows}).encode()
        req2 = _urllib_req.Request(url2, data=body, method="PUT")
        req2.add_header("Authorization", f"Bearer {token.strip()}")
        req2.add_header("Content-Type", "application/json")
        with _urllib_req.urlopen(req2, timeout=10) as r:
            return (True, "") if r.status == 200 else (False, f"HTTP {r.status}")
    except Exception as e:
        err = str(e)
        if hasattr(e, 'read'):
            try: err += " | " + e.read().decode()[:200]
            except Exception: pass
        return False, err


# ── Portfolio persistence ─────────────────────────────────
PORTFOLIO_FILE = "/tmp/watchlist_portfolio.json"

@st.cache_resource
def _get_portfolio_store():
    store = {"trades": []}
    try:
        if os.path.exists(PORTFOLIO_FILE):
            with open(PORTFOLIO_FILE) as f:
                store = json.load(f)
    except Exception:
        pass
    return store

def _save_portfolio(store):
    try:
        tmp = PORTFOLIO_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(store, f, ensure_ascii=False)
        os.replace(tmp, PORTFOLIO_FILE)
    except Exception:
        pass

def port_get():
    return _get_portfolio_store().get("trades", [])

def port_save(trades: list):
    store = _get_portfolio_store()
    store["trades"] = trades
    _save_portfolio(store)


# ── Strategy evaluation engine ────────────────────────────
def evaluate_position(code: str, trades: list, cur_price: float) -> dict:
    """
    FIFO cost analysis + 5-path strategy decision.
    Returns full evaluation dict.
    """
    buys = [t for t in trades if t.get("交易別") in ("現買","買進","買") and t.get("商品","").startswith(code)]
    sells= [t for t in trades if t.get("交易別") in ("現賣","賣出","賣") and t.get("商品","").startswith(code)]

    total_shares = sum(t.get("股數",0) for t in buys) - sum(t.get("股數",0) for t in sells)
    if total_shares <= 0:
        return {"status": "no_position"}

    total_cost = sum(t.get("價金",0) + t.get("手續費",0) for t in buys)
    sell_proceeds = sum(t.get("價金",0) - t.get("手續費",0) - t.get("交易稅",0) for t in sells)
    net_cost = total_cost - sell_proceeds
    avg_cost = net_cost / total_shares if total_shares > 0 else 0
    avg_price_per_share = avg_cost / 1   # 價金 already = 股數×成交價

    # Recalculate avg cost per share from raw data
    total_qty_cost = sum(t.get("股數",0) * t.get("成交價",0) + t.get("手續費",0) for t in buys)
    sold_qty = sum(t.get("股數",0) for t in sells)
    bought_qty = sum(t.get("股數",0) for t in buys)
    if bought_qty > 0:
        avg_px_per_share = total_qty_cost / bought_qty
    else:
        avg_px_per_share = 0

    mkt_val  = cur_price * total_shares
    cost_val = avg_px_per_share * total_shares
    unreal   = mkt_val - cost_val
    unreal_p = unreal / cost_val * 100 if cost_val > 0 else 0

    # ATR-based stop (simple: avg_cost × 0.93 = -7%)
    atr_stop  = round(avg_px_per_share * 0.93, 1)
    stop_hit  = cur_price <= atr_stop

    # Buy dates for holding period
    dates = sorted([t.get("交易日","") for t in buys])
    first_buy = dates[0] if dates else ""
    last_buy  = dates[-1] if dates else ""

    # ── Strategy decision (5 paths) ─────────────────────
    if stop_hit and unreal_p < -10:
        action = "🚨 立即停損"
        color  = "#ff0033"
        reason = f"現價 {cur_price} 已跌破停損位 {atr_stop}，虧損 {unreal_p:.1f}%，建議清倉 {total_shares} 股"
        urgency = "立即"
    elif unreal_p < -15:
        action = "🔴 考慮停損"
        color  = "#ff3355"
        reason = f"深度虧損 {unreal_p:.1f}%，已超過 -15% 警戒線，建議先減碼 50%（賣 {total_shares//2} 股）"
        urgency = "本週"
    elif unreal_p < -7:
        action = "🟡 攤平評估"
        color  = "#f0a500"
        reason = f"虧損 {unreal_p:.1f}%，已有 {len(buys)} 筆買入，評估是否底部加買或設停損"
        urgency = "觀察"
    elif unreal_p >= 20:
        action = "🟡 分批獲利"
        color  = "#f0a500"
        reason = f"獲利 {unreal_p:.1f}%，建議分批出場，先賣 {total_shares//2} 股鎖定利潤"
        urgency = "本週"
    elif unreal_p >= 10:
        action = "🟢 續抱觀察"
        color  = "#00cc66"
        reason = f"獲利 {unreal_p:.1f}%，趨勢未反轉前繼續持有，設移動停損 {round(cur_price*0.95,1)}"
        urgency = "觀察"
    else:
        # Check if price near multi-buy average → potential bottom accumulation zone
        buy_prices = [t.get("成交價",0) for t in buys]
        min_bp = min(buy_prices) if buy_prices else cur_price
        if cur_price <= min_bp * 1.03 and len(buys) < 15:
            action = "🔵 底部觀察"
            color  = "#00aaff"
            reason = f"現價 {cur_price} 接近最低買入成本 {min_bp}，若技術訊號確認可考慮少量加碼"
            urgency = "觀察"
        else:
            action = "⚪ 持有觀察"
            color  = "#5a8fb0"
            reason = f"損益 {unreal_p:+.1f}%，無明顯操作訊號，等待技術面確認方向"
            urgency = "觀察"

    # DCA analysis
    buy_prices_list = sorted([t.get("成交價",0) for t in buys])
    dca_summary = f"共 {len(buys)} 次買入，最低 {min(buy_prices_list):.1f}，最高 {max(buy_prices_list):.1f}，均 {avg_px_per_share:.1f}" if buy_prices_list else ""

    return {
        "code":         code,
        "total_shares": total_shares,
        "avg_cost":     round(avg_px_per_share, 2),
        "cur_price":    cur_price,
        "cost_val":     round(cost_val, 0),
        "mkt_val":      round(mkt_val, 0),
        "unreal":       round(unreal, 0),
        "unreal_p":     round(unreal_p, 2),
        "atr_stop":     atr_stop,
        "stop_hit":     stop_hit,
        "action":       action,
        "color":        color,
        "reason":       reason,
        "urgency":      urgency,
        "dca_summary":  dca_summary,
        "first_buy":    first_buy,
        "last_buy":     last_buy,
        "n_buys":       len(buys),
        "status":       "active",
    }


def check_and_send_alerts(token, chat_id, codes, quotes):
    """
    Check all stocks against their target/stop prices.
    Send Telegram alert if triggered and not yet sent today.
    Returns list of alert messages sent.
    """
    if not token or not chat_id:
        return []
    sent_msgs = []
    for code in codes:
        n  = notes_get(code)
        q  = quotes.get(code, {})
        px = q.get("price", 0)
        if not px:
            continue
        tgt = n.get("target")
        stp = n.get("stop")
        name = cn_name(code)
        chg  = q.get("chg_pct", 0)

        # Target hit
        if tgt and px >= tgt and not _alert_sent_today(code, "target"):
            msg = (
                f"🎯 目標價達標！\n"
                f"{code} {name}\n"
                f"現價 {px:.2f}  目標 {tgt}\n"
                f"漲跌 {chg:+.2f}%\n"
                f"時間 {tw_now().strftime('%Y-%m-%d %H:%M')}"
            )
            ok, _ = _tg_send(token, chat_id, msg)
            if ok:
                _mark_alert_sent(code, "target")
                sent_msgs.append(f"🎯 {code} 達標 {px:.2f}")

        # Stop hit
        if stp and px <= stp and not _alert_sent_today(code, "stop"):
            msg = (
                f"🛑 停損價觸發！\n"
                f"{code} {name}\n"
                f"現價 {px:.2f}  停損 {stp}\n"
                f"漲跌 {chg:+.2f}%\n"
                f"時間 {tw_now().strftime('%Y-%m-%d %H:%M')}"
            )
            ok, _ = _tg_send(token, chat_id, msg)
            if ok:
                _mark_alert_sent(code, "stop")
                sent_msgs.append(f"🛑 {code} 觸停損 {px:.2f}")

        # Near target (within 2%)
        if tgt and px < tgt and (tgt - px) / tgt * 100 <= 2 and not _alert_sent_today(code, "near_target"):
            msg = (
                f"⚠️ 接近目標價\n"
                f"{code} {name}\n"
                f"現價 {px:.2f}  目標 {tgt}  距離 {(tgt-px)/tgt*100:.1f}%\n"
                f"時間 {tw_now().strftime('%H:%M')}"
            )
            ok, _ = _tg_send(token, chat_id, msg)
            if ok:
                _mark_alert_sent(code, "near_target")
                sent_msgs.append(f"⚠️ {code} 接近目標")

    return sent_msgs

# ── Dark theme CSS ────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
body, .stApp { background:#0a0e1a; color:#e8f4fd; }
.wl-header { background:linear-gradient(135deg,#0d1f35,#0a1628);
  border:1px solid #1a3a5c; border-radius:14px; padding:20px 24px;
  margin-bottom:20px; }
.wl-title { font-family:'Space Mono',monospace; font-size:1.6rem;
  font-weight:700; color:#e8f4fd; }
.wl-sub { color:#5a8fb0; font-size:0.82rem; margin-top:4px; }
.stock-card { background:#0d1a2d; border:1.5px solid #1a2a3a;
  border-radius:10px; padding:14px 16px; margin-bottom:10px;
  transition:border-color 0.2s; }
.stock-card:hover { border-color:#00d4ff; }
.up   { color:#e8414e; }
.down { color:#22cc66; }
.neutral { color:#8a9bb5; }
div[data-testid="stMetricValue"] { font-size:1.1rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Persistence ───────────────────────────────────────────
@st.cache_resource
def _get_wl_store():
    store = {"codes": [], "groups": {}}  # groups: {code: group_name}
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE) as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                store["codes"] = loaded          # old format
            elif isinstance(loaded, dict):
                store = loaded
    except Exception:
        pass
    return store

@st.cache_resource
def _get_notes_store():
    store = {}
    try:
        if os.path.exists(NOTES_FILE):
            with open(NOTES_FILE) as f:
                store = json.load(f)
    except Exception:
        pass
    return store

def _save_wl(store):
    try:
        tmp = WATCHLIST_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(store, f, ensure_ascii=False)
        os.replace(tmp, WATCHLIST_FILE)
    except Exception:
        pass

def _save_notes(store):
    try:
        tmp = NOTES_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(store, f, ensure_ascii=False)
        os.replace(tmp, NOTES_FILE)
    except Exception:
        pass

def wl_get():
    return _get_wl_store()["codes"]

def wl_add(code):
    store = _get_wl_store()
    code = code.upper().strip()
    if code not in store["codes"]:
        store["codes"].append(code)
        _save_wl(store)
        return True
    return False

def wl_remove(code):
    store = _get_wl_store()
    if code in store["codes"]:
        store["codes"].remove(code)
        _save_wl(store)
        return True
    return False

def wl_set_group(code, group):
    store = _get_wl_store()
    store.setdefault("groups", {})[code] = group
    _save_wl(store)

def wl_get_group(code):
    return _get_wl_store().get("groups", {}).get(code, "未分組")

def notes_get(code):
    return _get_notes_store().get(code, {})

def notes_set(code, data):
    store = _get_notes_store()
    store[code] = data
    _save_notes(store)

# ── Data fetching ─────────────────────────────────────────
_TW_NAMES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2881": "富邦金",
    "2308": "台達電", "2882": "國泰金", "2303": "聯電", "2886": "兆豐金",
    "2412": "中華電", "2382": "廣達", "2891": "中信金", "3008": "大立光",
    "2603": "長榮", "1301": "台塑", "1303": "南亞", "2892": "第一金",
    "2002": "中鋼", "5880": "合庫金", "2207": "和泰車", "2395": "研華",
    "2357": "華碩", "2887": "台新金", "2327": "國巨", "2885": "元大金",
    "2884": "玉山金", "6415": "矽力-KY", "5871": "中租-KY", "4938": "臻鼎-KY",
    "2633": "台灣高鐵", "6213": "聯茂", "2379": "瑞昱", "3034": "聯詠",
    "3711": "日月光投控", "2301": "光寶科", "2912": "統一超", "1216": "統一",
    "0050": "元大台灣50", "00878": "國泰永續高息", "00919": "群益精選高息",
    "2880": "華南金", "2883": "開發金", "2890": "永豐金", "2347": "聯強",
    "2474": "可成", "2707": "晶華", "1513": "中興電", "6182": "合晶",
    "4958": "臻鼎-KY", "3045": "台灣大", "2104": "中橡", "2105": "正新",
    "2542": "興富發", "9921": "巨大", "9951": "皇田",
}

def cn_name(code):
    bare = code.upper().replace(".TW","").replace(".TWO","")
    return _TW_NAMES.get(bare, bare)

@st.cache_data(ttl=60)
def fetch_quote(symbol):
    bare = symbol.upper().replace(".TW","").replace(".TWO","")
    for sym in [bare+".TW", bare+".TWO", symbol]:
        try:
            fi   = yf.Ticker(sym).fast_info
            last = getattr(fi, "last_price",     None) or 0
            prev = getattr(fi, "previous_close", None) or last
            high = getattr(fi, "day_high",        None) or 0
            low  = getattr(fi, "day_low",         None) or 0
            vol  = getattr(fi, "last_volume",     None) or 0
            if last == 0: continue
            chg_p = (last-prev)/prev*100 if prev else 0
            return {"price":last, "prev":prev, "chg_pct":chg_p,
                    "high":high, "low":low, "volume":vol, "ok":True}
        except Exception:
            pass
    return {"ok": False, "price": 0, "chg_pct": 0}

@st.cache_data(ttl=300)
def fetch_hist(symbol, period="1mo"):
    bare = symbol.upper().replace(".TW","").replace(".TWO","")
    for sym in [bare+".TW", bare+".TWO"]:
        try:
            df = yf.Ticker(sym).history(period=period)
            if not df.empty:
                return df
        except Exception:
            pass
    return pd.DataFrame()

# ── Preset groups ─────────────────────────────────────────
PRESET_GROUPS = ["未分組","半導體","金融","電子","傳產","ETF","自定義"]

# ═════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════
st.markdown(f"""
<div class="wl-header">
  <div class="wl-title">📋 Watchlist Pro <span style="color:#00d4ff;font-size:0.85em">v{APP_VERSION}</span></div>
  <div class="wl-sub">台股自選股管理 · 目標價警報 · 備忘錄 · 即時報價 · 更新於 {APP_UPDATED}</div>
</div>
""", unsafe_allow_html=True)

codes = wl_get()

# ─────────────────────────────────────────────────────────
# SIDEBAR — Add / Remove / Import
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ➕ 新增股票")
    new_code = st.text_input("輸入代號", placeholder="2330 / 6415.TWO",
                              key="add_code")
    new_group = st.selectbox("分組", PRESET_GROUPS, key="add_group")
    if st.button("新增", type="primary", width="stretch"):
        c = new_code.strip().upper().replace(".TW","").replace(".TWO","")
        if c:
            if wl_add(c):
                wl_set_group(c, new_group)
                st.success(f"已新增 {c}")
                st.rerun()
            else:
                st.warning(f"{c} 已在清單中")

    st.divider()
    st.markdown("### 🗑 刪除股票")
    all_codes_del = wl_get()
    if all_codes_del:
        del_code = st.selectbox("選擇要刪除的股票", all_codes_del,
                                 format_func=lambda x: f"{x} {cn_name(x)}",
                                 key="del_code")
        if st.button("🗑 從清單移除", width="stretch", key="del_btn"):
            if wl_remove(del_code):
                st.success(f"已移除 {del_code}")
                st.rerun()

    st.divider()
    st.markdown("### 🗂 管理分組")
    all_codes = wl_get()
    if all_codes:
        move_code  = st.selectbox("選擇股票", all_codes,
                                   format_func=lambda x: f"{x} {cn_name(x)}",
                                   key="move_code")
        move_group = st.selectbox("設定分組", PRESET_GROUPS, key="move_group")
        if st.button("更新分組", width="stretch"):
            wl_set_group(move_code, move_group)
            st.success("已更新")
            st.rerun()

    st.divider()
    st.markdown("### 📤 匯出 / 📥 匯入")
    if all_codes:
        import io as _io, openpyxl as _xl
        export_df = pd.DataFrame({
            "代號": all_codes,
            "名稱": [cn_name(c) for c in all_codes],
            "分組": [wl_get_group(c) for c in all_codes],
        })
        buf = _io.BytesIO()
        wb = _xl.Workbook()
        ws = wb.active
        ws.title = "自選股"
        ws.append(["代號","名稱","分組"])
        for _, row in export_df.iterrows():
            ws.append([row["代號"], row["名稱"], row["分組"]])
        wb.save(buf)
        buf.seek(0)
        st.download_button("📤 匯出 Excel", data=buf,
                           file_name=f"watchlist_{tw_now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           width="stretch")

    up_file = st.file_uploader("📥 匯入 Excel", type=["xlsx"])
    if up_file:
        try:
            df_imp = pd.read_excel(up_file)
            added = 0
            for _, row in df_imp.iterrows():
                c = str(row.get("代號","")).strip().upper()
                g = str(row.get("分組","未分組")).strip()
                if c and wl_add(c):
                    wl_set_group(c, g)
                    added += 1
            st.success(f"已匯入 {added} 支")
            st.rerun()
        except Exception as e:
            st.error(f"匯入失敗：{e}")

    st.divider()
    st.markdown("### 📲 Telegram 到價提醒")
    # Read from st.secrets if available
    _tg_sec = {}
    try: _tg_sec = st.secrets.get("telegram", {})
    except Exception: pass

    tg_token   = st.text_input("Bot Token",
        value=_tg_sec.get("token", ""),
        type="password", key="wl_tg_token",
        help="從 @BotFather 取得。可存入 Streamlit Secrets [telegram] token='...'")
    tg_chat_id = st.text_input("Chat ID",
        value=_tg_sec.get("chat_id", ""),
        key="wl_tg_chat",
        help="傳訊息給 Bot 後，用 api.telegram.org/bot<TOKEN>/getUpdates 查詢")
    if tg_token and len(tg_token) > 20:
        st.markdown(
            f"[🔍 查詢 Chat ID](https://api.telegram.org/bot{tg_token}/getUpdates)"
            " ← 先傳任意訊息給 Bot"
        )
    tg_near = st.checkbox("⚠️ 接近目標價也通知（距離 ≤2%）",
                           value=True, key="wl_tg_near")
    if st.button("🧪 測試推播", key="wl_tg_test", width="stretch"):
        ok, err = _tg_send(tg_token, tg_chat_id,
            f"✅ Watchlist Pro 推播測試\n設定正確，到價提醒已啟用\n"
            f"時間 {tw_now().strftime('%Y-%m-%d %H:%M')}")
        st.success("✅ 測試成功！") if ok else st.error(f"❌ {err}")

    st.divider()
    st.markdown("### ⏱ 自動更新")
    auto_ref = st.toggle("啟用自動更新", value=False, key="auto_ref")
    if auto_ref:
        ref_interval = st.selectbox("更新間隔", ["30秒", "1分鐘", "5分鐘"], index=1)
        interval_s = {"30秒": 30, "1分鐘": 60, "5分鐘": 300}[ref_interval]
        st.caption(f"每 {ref_interval} 自動刷新報價")
        st.markdown(f'<meta http-equiv="refresh" content="{interval_s}">',
                    unsafe_allow_html=True)
    if st.button("🔄 立即重新整理", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────────────────
# MAIN — Tabs
# ─────────────────────────────────────────────────────────
if not codes:
    st.info("👈 從左側側欄新增股票代號開始使用")
    st.stop()

tab_overview, tab_cards, tab_monitor, tab_notes, tab_alerts, tab_port = st.tabs([
    "📊 總覽表格", "🃏 卡片視圖", "📈 每日監控",
    "📝 備忘錄", "🎯 目標價警報", "💼 持倉分析",
])

# ─── Fetch all quotes ──────────────────────────────────────
@st.cache_data(ttl=60)
def bulk_quotes(code_tuple):
    return {c: fetch_quote(c) for c in code_tuple}

with st.spinner("載入報價…"):
    quotes = bulk_quotes(tuple(codes))

# ── Auto-check price alerts after every quote refresh ────
_tg_tok = st.session_state.get("wl_tg_token", "")
_tg_cid = st.session_state.get("wl_tg_chat", "")
if _tg_tok and _tg_cid:
    _alerts_sent = check_and_send_alerts(_tg_tok, _tg_cid, codes, quotes)
    if _alerts_sent:
        for _a in _alerts_sent:
            st.toast(f"📲 已推播：{_a}", icon="✅")

# ═════════════════════════════════════════════════════════
# TAB 1 — 總覽表格
# ═════════════════════════════════════════════════════════
with tab_overview:
    st.markdown("#### 📊 自選股總覽")

    # Group filter
    all_groups = sorted(set(wl_get_group(c) for c in codes))
    sel_group  = st.selectbox("篩選分組", ["全部"] + all_groups, key="ov_group")

    rows = []
    for code in codes:
        if sel_group != "全部" and wl_get_group(code) != sel_group:
            continue
        q = quotes.get(code, {})
        n = notes_get(code)
        price  = q.get("price", 0)
        chg    = q.get("chg_pct", 0)
        target = n.get("target")
        stop   = n.get("stop")
        upside = round((target/price - 1)*100, 1) if target and price else None

        rows.append({
            "代號":   code,
            "名稱":   cn_name(code),
            "分組":   wl_get_group(code),
            "現價":   round(price, 2) if price else None,
            "漲跌%":  round(chg, 2) if q.get("ok") else None,
            "目標價": float(target) if target else None,
            "停損價": float(stop) if stop else None,
            "上漲空間%": upside,
            "備忘":   (n.get("note","")[:20] + "…") if len(n.get("note","")) > 20
                       else n.get("note",""),
        })

    if rows:
        df_ov = pd.DataFrame(rows)
        st.dataframe(
            df_ov, width="stretch", hide_index=True,
            column_config={
                "漲跌%":     st.column_config.NumberColumn(format="%+.2f%%"),
                "上漲空間%": st.column_config.NumberColumn(format="%+.1f%%"),
            },
        )

        # Summary metrics
        valid = [r for r in rows if isinstance(r["漲跌%"], float)]
        if valid:
            up   = sum(1 for r in valid if r["漲跌%"] > 0)
            down = sum(1 for r in valid if r["漲跌%"] < 0)
            flat = len(valid) - up - down
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("總支數", len(codes))
            m2.metric("🔴 上漲", up)
            m3.metric("🟢 下跌", down)
            m4.metric("⚪ 平盤", flat)

# ═════════════════════════════════════════════════════════
# TAB 2 — 卡片視圖
# ═════════════════════════════════════════════════════════
with tab_cards:
    st.markdown("#### 🃏 個股卡片")

    sort_by = st.radio("排序", ["預設","漲跌幅↓","漲跌幅↑","分組"],
                        horizontal=True)

    card_codes = list(codes)
    if sort_by == "漲跌幅↓":
        card_codes.sort(key=lambda c: -quotes.get(c,{}).get("chg_pct",0))
    elif sort_by == "漲跌幅↑":
        card_codes.sort(key=lambda c: quotes.get(c,{}).get("chg_pct",0))
    elif sort_by == "分組":
        card_codes.sort(key=lambda c: wl_get_group(c))

    cols_n = 3
    for i in range(0, len(card_codes), cols_n):
        chunk = card_codes[i:i+cols_n]
        cols  = st.columns(cols_n)
        for ci, code in enumerate(chunk):
            q = quotes.get(code, {})
            n = notes_get(code)
            price  = q.get("price", 0)
            chg    = q.get("chg_pct", 0)
            high   = q.get("high", 0)
            low    = q.get("low", 0)
            target = n.get("target")
            stop   = n.get("stop")

            # Colour by change
            if not q.get("ok"):
                clr, chg_txt = "#5a8fb0", "─"
            elif chg > 0:
                clr, chg_txt = "#e8414e", f"+{chg:.2f}%"
            elif chg < 0:
                clr, chg_txt = "#22cc66", f"{chg:.2f}%"
            else:
                clr, chg_txt = "#8a9bb5", "0.00%"

            # Target / stop badges
            badge = ""
            if target and price and price >= target:
                badge += '<span style="background:#ffd700;color:#000;padding:1px 6px;border-radius:3px;font-size:0.68rem;margin-left:4px">🎯達標</span>'
            if stop and price and price <= stop:
                badge += '<span style="background:#ff3355;color:#fff;padding:1px 6px;border-radius:3px;font-size:0.68rem;margin-left:4px">🛑停損</span>'

            # Pre-compute display strings (can't use :.2f inside f-string conditional)
            price_txt = f"{price:.2f}" if price else "─"
            high_txt  = f"{high:.2f}"  if high  else "─"
            low_txt   = f"{low:.2f}"   if low   else "─"

            with cols[ci]:
                st.markdown(f"""
                <div class="stock-card" style="border-color:{clr}20">
                  <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <span style="font-weight:700;color:#e8f4fd;font-family:'Space Mono',monospace">
                      {code} {badge}</span>
                    <span style="font-size:0.75rem;background:#1a2a3a;color:#8a9bb5;
                      padding:1px 8px;border-radius:4px">{wl_get_group(code)}</span>
                  </div>
                  <div style="color:#8a9bb5;font-size:0.8rem;margin-bottom:8px">{cn_name(code)}</div>
                  <div style="font-size:1.4rem;font-weight:700;color:{clr};margin-bottom:4px">
                    {price_txt}
                    <span style="font-size:0.85rem">{chg_txt}</span>
                  </div>
                  <div style="display:flex;gap:10px;font-size:0.72rem;color:#37474f">
                    <span>H {high_txt}</span>
                    <span>L {low_txt}</span>
                    {"<span>🎯 " + str(target) + "</span>" if target else ""}
                    {"<span>🛑 " + str(stop) + "</span>" if stop else ""}
                  </div>
                  {"<div style='font-size:0.68rem;color:#37474f;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>" + n.get('note','')[:40] + "</div>" if n.get('note') else ""}
                </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════
# TAB 3 — 每日監控
# ═════════════════════════════════════════════════════════
with tab_monitor:
    st.markdown("#### 📈 每日價格監控")
    st.caption("即時漲跌幅排行 + 5日迷你走勢圖 + 成交量異常偵測")

    # Sort by change
    mon_rows = []
    for code in codes:
        q = quotes.get(code, {})
        if not q.get("ok"):
            continue
        px  = q.get("price", 0)
        chg = q.get("chg_pct", 0)
        vol = q.get("volume", 0)
        mon_rows.append({"code": code, "price": px, "chg": chg, "vol": vol})

    mon_rows.sort(key=lambda r: -r["chg"])

    # Top movers
    if mon_rows:
        gainers = [r for r in mon_rows if r["chg"] > 0][:3]
        losers  = [r for r in mon_rows if r["chg"] < 0][-3:][::-1]

        ga_col, lo_col = st.columns(2)
        with ga_col:
            st.markdown("##### 🔴 今日漲幅前3")
            for r in gainers:
                st.markdown(
                    f'<div style="background:#1a0a0a;border-left:3px solid #e8414e;'
                    f'padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:6px">'
                    f'<span style="font-weight:700;color:#e8f4fd">{r["code"]}</span>'
                    f'<span style="color:#8a9bb5;font-size:0.82rem;margin-left:8px">{cn_name(r["code"])}</span>'
                    f'<span style="float:right;color:#e8414e;font-weight:700">'
                    f'+{r["chg"]:.2f}%  {r["price"]:.2f}</span></div>',
                    unsafe_allow_html=True,
                )
        with lo_col:
            st.markdown("##### 🟢 今日跌幅前3")
            for r in losers:
                st.markdown(
                    f'<div style="background:#0a1a0a;border-left:3px solid #22cc66;'
                    f'padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:6px">'
                    f'<span style="font-weight:700;color:#e8f4fd">{r["code"]}</span>'
                    f'<span style="color:#8a9bb5;font-size:0.82rem;margin-left:8px">{cn_name(r["code"])}</span>'
                    f'<span style="float:right;color:#22cc66;font-weight:700">'
                    f'{r["chg"]:.2f}%  {r["price"]:.2f}</span></div>',
                    unsafe_allow_html=True,
                )

    st.divider()
    st.markdown("##### 📉 近30日走勢 & 成交量")
    chart_code = st.selectbox("選擇股票", codes,
                               format_func=lambda x: f"{x}  {cn_name(x)}",
                               key="mon_code")

    with st.spinner("載入歷史資料…"):
        df_h = fetch_hist(chart_code, "1mo")

    if not df_h.empty:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3], vertical_spacing=0.05,
                            specs=[[{"secondary_y": False}],[{"secondary_y": False}]])

        close = df_h["Close"]
        colors = ["#e8414e" if close.iloc[i] >= close.iloc[i-1] else "#22cc66"
                  for i in range(len(close))]
        colors[0] = "#8a9bb5"

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df_h.index, open=df_h["Open"], high=df_h["High"],
            low=df_h["Low"], close=df_h["Close"],
            increasing_fillcolor="#e8414e", increasing_line_color="#e8414e",
            decreasing_fillcolor="#22cc66", decreasing_line_color="#22cc66",
            name="K線", showlegend=False,
        ), row=1, col=1)

        # Target/stop lines
        n = notes_get(chart_code)
        if n.get("target"):
            fig.add_hline(y=n["target"], line_dash="dash", line_color="#ffd700",
                          line_width=1.5, annotation_text=f"🎯{n['target']}",
                          annotation_position="right", row=1, col=1)
        if n.get("stop"):
            fig.add_hline(y=n["stop"], line_dash="dash", line_color="#ff3355",
                          line_width=1.5, annotation_text=f"🛑{n['stop']}",
                          annotation_position="right", row=1, col=1)

        # Volume
        vol_colors = ["#e8414e" if df_h["Close"].iloc[i] >= df_h["Open"].iloc[i]
                      else "#22cc66" for i in range(len(df_h))]
        fig.add_trace(go.Bar(
            x=df_h.index, y=df_h["Volume"],
            marker_color=vol_colors, name="成交量", showlegend=False,
        ), row=2, col=1)

        # Detect volume spike (> 2× average)
        vol_avg = df_h["Volume"].mean()
        vol_spike = df_h[df_h["Volume"] > vol_avg * 2]
        if not vol_spike.empty:
            fig.add_trace(go.Scatter(
                x=vol_spike.index,
                y=vol_spike["Volume"],
                mode="markers",
                marker=dict(color="#ffd700", size=8, symbol="star"),
                name="成交量異常", showlegend=True,
            ), row=2, col=1)

        fig.update_layout(
            template="plotly_dark", height=420,
            paper_bgcolor="#0a0e1a", plot_bgcolor="#0d1226",
            margin=dict(l=50, r=80, t=20, b=20),
            font=dict(size=10, color="#8a9bb5"),
            hovermode="x unified",
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.05, x=0),
        )
        fig.update_yaxes(gridcolor="#1a2a3a")
        st.plotly_chart(fig, width="stretch")

        # Volume anomaly alert
        last_vol = df_h["Volume"].iloc[-1]
        if last_vol > vol_avg * 2:
            st.warning(f"⚠️ 今日成交量 {last_vol:,.0f} 為近30日均量的 {last_vol/vol_avg:.1f} 倍 — 異常放量")
    else:
        st.info("無法取得歷史資料")


# ═════════════════════════════════════════════════════════
# TAB 3 — 備忘錄
# ═════════════════════════════════════════════════════════
with tab_notes:
    st.markdown("#### 📝 個股備忘錄 & 進場理由")

    sel_code = st.selectbox("選擇股票", codes,
                             format_func=lambda x: f"{x}  {cn_name(x)}",
                             key="note_code")
    existing = notes_get(sel_code)

    with st.form("note_form"):
        note_txt = st.text_area("備忘 / 進場理由", value=existing.get("note",""),
                                 height=100, placeholder="記錄你關注這支股票的原因…")
        col1, col2 = st.columns(2)
        entry_px   = col1.number_input("進場均價記錄", min_value=0.0,
                                        value=float(existing.get("entry",0) or 0), step=0.5)
        watch_date = col2.text_input("開始關注日期",
                                      value=existing.get("watch_date",
                                            tw_now().strftime("%Y-%m-%d")))
        reason_tags = st.multiselect("關注原因標籤",
            ["技術突破","籌碼面轉強","法人買超","產業利多","業績成長",
             "低估值","高殖利率","週期底部","主題題材","其他"],
            default=existing.get("tags", []))
        saved = st.form_submit_button("💾 儲存備忘", type="primary")
        if saved:
            data = existing.copy()
            data.update({"note": note_txt, "entry": entry_px,
                          "watch_date": watch_date, "tags": reason_tags,
                          "updated": tw_now().strftime("%Y-%m-%d %H:%M")})
            notes_set(sel_code, data)
            st.success(f"✅ {sel_code} 備忘已儲存")

    # Show all notes summary
    st.divider()
    st.markdown("##### 📋 所有備忘摘要")
    note_rows = []
    for c in codes:
        n = notes_get(c)
        if n.get("note") or n.get("tags"):
            note_rows.append({
                "代號":       c,
                "名稱":       cn_name(c),
                "備忘":       n.get("note","")[:40],
                "標籤":       "、".join(n.get("tags",[])),
                "進場均價":   n.get("entry","─"),
                "關注日期":   n.get("watch_date",""),
                "更新時間":   n.get("updated",""),
            })
    if note_rows:
        st.dataframe(pd.DataFrame(note_rows), width="stretch", hide_index=True)
    else:
        st.info("尚無備忘記錄")

# ═════════════════════════════════════════════════════════
# TAB 4 — 目標價警報
# ═════════════════════════════════════════════════════════
with tab_alerts:
    st.markdown("#### 🎯 目標價 & 停損設定")

    # Telegram status banner
    _tok = st.session_state.get("wl_tg_token","")
    _cid = st.session_state.get("wl_tg_chat","")
    if _tok and _cid:
        st.success("📲 Telegram 推播已啟用 — 到價時自動發送通知（每次刷新自動檢查）")
    else:
        st.warning("📲 Telegram 未設定 — 在左側「📲 Telegram 到價提醒」填入 Token 和 Chat ID 即可啟用自動推播")

    st.caption("設定每支股票的目標價和停損價，達到時卡片會顯示警報標籤並自動推播")

    # Edit targets
    with st.expander("✏️ 編輯目標價 / 停損價", expanded=True):
        alert_code = st.selectbox("選擇股票", codes,
                                   format_func=lambda x: f"{x}  {cn_name(x)}",
                                   key="alert_code")
        existing_a = notes_get(alert_code)
        q_now      = quotes.get(alert_code, {})
        cur_px     = q_now.get("price", 0)

        ca, cb, cc = st.columns(3)
        target_px = ca.number_input("🎯 目標價",
            min_value=0.0, step=0.5,
            value=float(existing_a.get("target", 0) or 0),
            help="達到目標價時顯示 🎯達標 標籤")
        stop_px = cb.number_input("🛑 停損價",
            min_value=0.0, step=0.5,
            value=float(existing_a.get("stop", 0) or 0),
            help="跌破停損價時顯示 🛑停損 標籤")
        if cur_px and target_px:
            upside = (target_px/cur_px - 1)*100
            cc.metric("上漲空間", f"{upside:+.1f}%",
                       "🟢" if upside > 10 else "🟡")
        if st.button("💾 儲存設定", type="primary", key="save_alert"):
            data = existing_a.copy()
            data.update({"target": target_px or None, "stop": stop_px or None})
            notes_set(alert_code, data)
            st.success(f"✅ 已儲存 {alert_code} 的目標價設定")
            st.rerun()

    # Alert status overview
    st.divider()
    st.markdown("##### 🚨 警報狀態總覽")
    alert_rows = []
    for c in codes:
        n = notes_get(c)
        q = quotes.get(c, {})
        px = q.get("price", 0)
        tgt = n.get("target")
        stp = n.get("stop")
        if not (tgt or stp):
            continue
        upside = round((tgt/px-1)*100, 1) if tgt and px else None
        status = []
        if tgt and px and px >= tgt:   status.append("🎯 已達目標")
        if stp and px and px <= stp:   status.append("🛑 跌破停損")
        if tgt and px and upside and 0 < upside <= 5: status.append("⚠️ 接近目標")
        if stp and px and px and stp and (px-stp)/px*100 <= 3: status.append("⚠️ 接近停損")
        if not status: status.append("✅ 正常")

        alert_rows.append({
            "代號":     c,
            "名稱":     cn_name(c),
            "現價":     round(px, 2) if px else None,
            "目標價":   float(tgt) if tgt else None,
            "停損價":   float(stp) if stp else None,
            "上漲空間": f"{upside:+.1f}%" if upside is not None else None,
            "狀態":     " ".join(status),
        })

    if alert_rows:
        st.dataframe(pd.DataFrame(alert_rows), width="stretch", hide_index=True)
    else:
        st.info("尚未設定任何目標價或停損價")

    # Triggered alerts banner
    triggered = [r for r in alert_rows if "已達目標" in r["狀態"] or "跌破停損" in r["狀態"]]
    if triggered:
        st.markdown("---")
        st.markdown("##### 🔔 觸發警報")
        for r in triggered:
            clr = "#ffd700" if "目標" in r["狀態"] else "#ff3355"
            st.markdown(
                f'<div style="background:#0a1220;border:2px solid {clr};'
                f'border-radius:8px;padding:10px 14px;margin-bottom:8px">'
                f'<b style="color:{clr}">{r["狀態"]}</b>&nbsp;&nbsp;'
                f'<span style="color:#e8f4fd">{r["代號"]} {r["名稱"]}</span>&nbsp;&nbsp;'
                f'<span style="color:#8a9bb5">現價 {r["現價"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ═════════════════════════════════════════════════════════
# TAB 6 — 💼 持倉分析（買賣記錄匯入 + 策略建議 + GS同步）
# ═════════════════════════════════════════════════════════
with tab_port:
    st.markdown("#### 💼 持倉分析 — 買賣記錄匯入 & 策略評估")
    st.caption("匯入券商的買賣明細 → 自動計算均成本與損益 → 策略建議 → 同步 Google Sheets → Telegram 通知")

    trades_all = port_get()

    # ── SECTION A: 匯入買賣記錄 ──────────────────────────
    with st.expander("📥 匯入買賣記錄", expanded=not trades_all):
        st.markdown("""
        **支援格式（Excel 欄位）：**
        `商品 | 交易日 | 交易別 | 股數 | 成交價 | 價金 | 手續費 | 交易稅 | 備註`

        直接從券商 App 截圖的「未實現損益明細」或「成交明細」匯出 Excel 貼上即可。
        """)

        imp_file = st.file_uploader("選擇 Excel 檔案", type=["xlsx","xls"], key="port_imp")
        if imp_file:
            try:
                df_imp = pd.read_excel(imp_file)
                # Flexible column mapping
                col_map = {
                    "商品": ["商品","股票","代號","名稱"],
                    "交易日": ["交易日","日期","成交日"],
                    "交易別": ["交易別","買賣","方向"],
                    "股數":   ["股數","數量","張數"],
                    "成交價": ["成交價","價格","單價"],
                    "價金":   ["價金","金額","成交金額"],
                    "手續費": ["手續費","費用"],
                    "交易稅": ["交易稅","稅"],
                }
                result_cols = {}
                for target, candidates in col_map.items():
                    for c in candidates:
                        matched = [col for col in df_imp.columns if c in col]
                        if matched:
                            result_cols[target] = matched[0]
                            break
                if "商品" not in result_cols or "交易日" not in result_cols:
                    st.error("找不到必要欄位（商品、交易日）。請確認 Excel 格式。")
                else:
                    df_mapped = pd.DataFrame()
                    for target, src_col in result_cols.items():
                        df_mapped[target] = df_imp[src_col]
                    for col in ["商品","交易日","交易別","股數","成交價","價金","手續費","交易稅","備註"]:
                        if col not in df_mapped:
                            df_mapped[col] = 0 if col in ["股數","成交價","價金","手續費","交易稅"] else ""

                    # Convert types
                    for num_col in ["股數","成交價","價金","手續費","交易稅"]:
                        df_mapped[num_col] = pd.to_numeric(df_mapped[num_col], errors="coerce").fillna(0)

                    st.success(f"✅ 預覽 {len(df_mapped)} 筆記錄")
                    st.dataframe(df_mapped.head(5), hide_index=True)
                    if st.button("✅ 確認匯入", type="primary", key="port_confirm"):
                        port_save(df_mapped.to_dict("records"))
                        st.success(f"已匯入 {len(df_mapped)} 筆記錄")
                        st.rerun()
            except Exception as e:
                st.error(f"匯入失敗：{e}")

        # Manual entry
        st.divider()
        st.markdown("**或手動新增一筆**")
        with st.form("add_trade_form"):
            mc1, mc2, mc3 = st.columns(3)
            t_code  = mc1.text_input("商品代號", placeholder="3019亞光")
            t_date  = mc2.date_input("交易日", value=date.today())
            t_type  = mc3.selectbox("交易別", ["現買","現賣"])
            mc4, mc5, mc6, mc7 = st.columns(4)
            t_qty   = mc4.number_input("股數", min_value=1, value=50, step=1)
            t_price = mc5.number_input("成交價", min_value=0.1, value=100.0, step=0.5)
            t_fee   = mc6.number_input("手續費", min_value=0, value=int(t_qty*t_price*0.001425*0.6), step=1)
            t_tax   = mc7.number_input("交易稅", min_value=0,
                                        value=int(t_qty*t_price*0.003) if t_type=="現賣" else 0, step=1)
            submitted = st.form_submit_button("新增", type="primary")
            if submitted:
                new_t = {
                    "商品": t_code, "交易日": str(t_date), "交易別": t_type,
                    "股數": int(t_qty), "成交價": float(t_price),
                    "價金": int(t_qty * t_price), "手續費": int(t_fee),
                    "交易稅": int(t_tax), "備註": "",
                }
                existing = port_get()
                existing.append(new_t)
                port_save(existing)
                st.success("已新增")
                st.rerun()

    if not trades_all:
        st.info("請先匯入買賣記錄")
        st.stop()

    # ── SECTION B: 損益分析 & 策略建議 ───────────────────
    st.markdown("---")
    st.markdown("#### 📊 持倉損益分析 & 策略建議")

    # Get unique stock codes from trades
    all_trade_codes = sorted(set(
        str(t.get("商品",""))[:4] for t in trades_all
        if t.get("商品") and str(t.get("商品","")).strip()
    ))

    evals = []
    for code in all_trade_codes:
        code_trades = [t for t in trades_all if str(t.get("商品","")).startswith(code)]
        q = fetch_quote(code)
        cur_px = q.get("price", 0)
        if cur_px == 0:
            # Try with .TW suffix
            q = fetch_quote(code + ".TW")
            cur_px = q.get("price", 0)
        ev = evaluate_position(code, code_trades, cur_px)
        if ev.get("status") == "active":
            evals.append(ev)

    if not evals:
        st.warning("無有效持倉（可能全部已賣出，或代號格式不符）")
    else:
        # Summary metrics
        total_cost = sum(e["cost_val"] for e in evals)
        total_mkt  = sum(e["mkt_val"]  for e in evals)
        total_unrl = total_mkt - total_cost
        total_p    = total_unrl / total_cost * 100 if total_cost else 0

        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("持倉支數", len(evals))
        sm2.metric("總投入成本", f"{total_cost/1e4:.1f} 萬")
        sm3.metric("目前市值",   f"{total_mkt/1e4:.1f} 萬")
        sm4.metric("未實現損益", f"{total_unrl/1e4:+.2f} 萬", f"{total_p:+.1f}%")

        # Summary table
        tbl = pd.DataFrame([{
            "代號":      e["code"],
            "名稱":      cn_name(e["code"]),
            "持股":      e["total_shares"],
            "均成本":    e["avg_cost"],
            "現價":      e["cur_price"],
            "市值":      e["mkt_val"],
            "損益":      e["unreal"],
            "損益%":     e["unreal_p"],
            "建議":      e["action"],
            "緊急程度":  e["urgency"],
        } for e in evals])

        st.dataframe(tbl, width="stretch", hide_index=True,
            column_config={
                "損益%":   st.column_config.NumberColumn(format="%+.2f%%"),
                "損益":    st.column_config.NumberColumn(format="$%+,.0f"),
                "市值":    st.column_config.NumberColumn(format="$%,.0f"),
            })

        # Strategy cards (sorted by urgency)
        urgency_order = {"立即": 0, "本週": 1, "觀察": 2}
        evals_sorted  = sorted(evals, key=lambda e: urgency_order.get(e["urgency"], 3))

        st.markdown("##### 🎯 個股策略建議")
        for ev in evals_sorted:
            clr = ev["color"]
            urg_clrs = {"立即":"#ff0033","本週":"#ff6600","觀察":"#5a8fb0"}
            uc = urg_clrs.get(ev["urgency"], "#5a8fb0")
            pnl_c = "#00cc66" if ev["unreal_p"] >= 0 else "#ff3355"

            st.markdown(
                f'<div style="background:#0a1220;border:2px solid {clr};'
                f'border-radius:12px;padding:14px 16px;margin-bottom:12px">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;flex-wrap:wrap;margin-bottom:8px">'
                f'<span style="font-size:1.1rem;font-weight:700;color:#e8f4fd;'
                f'font-family:Space Mono,monospace">{ev["code"]} {cn_name(ev["code"])}</span>'
                f'<span style="color:{uc};border:1px solid {uc};padding:1px 8px;'
                f'border-radius:4px;font-size:0.72rem">⏰ {ev["urgency"]}</span>'
                f'<span style="font-weight:700;color:{clr};font-size:1rem">{ev["action"]}</span>'
                f'</div>'
                f'<div style="color:#8a9bb5;font-size:0.8rem;border-left:3px solid {clr};'
                f'padding-left:8px;margin-bottom:8px">{ev["reason"]}</div>'
                f'<div style="display:flex;gap:14px;font-size:0.75rem;flex-wrap:wrap">'
                f'<span>持股 <b style="color:#e8f4fd">{ev["total_shares"]:,}</b></span>'
                f'<span>均成本 <b style="color:#8a9bb5">{ev["avg_cost"]:.2f}</b></span>'
                f'<span>現價 <b style="color:#e8f4fd">{ev["cur_price"]:.2f}</b></span>'
                f'<span>損益 <b style="color:{pnl_c}">{ev["unreal_p"]:+.1f}%</b>'
                f' (<b style="color:{pnl_c}">{ev["unreal"]:+,.0f}</b>)</span>'
                f'<span>停損位 <b style="color:#ff6666">{ev["atr_stop"]:.1f}</b></span>'
                f'</div>'
                f'<div style="font-size:0.7rem;color:#37474f;margin-top:6px">'
                f'{ev["dca_summary"]}　首買 {ev["first_buy"]}　最近買 {ev["last_buy"]}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        # ── SECTION C: Telegram push ──────────────────────
        st.divider()
        st.markdown("#### 📲 推播策略建議到 Telegram")
        _tok = st.session_state.get("wl_tg_token","")
        _cid = st.session_state.get("wl_tg_chat","")
        if st.button("📲 推播所有持倉建議", type="primary", key="port_tg",
                     width="stretch"):
            if not _tok or not _cid:
                st.warning("請先在側欄設定 Telegram Token 和 Chat ID")
            else:
                sent = 0
                for ev in evals_sorted:
                    msg = (
                        f"{ev['action']}  {ev['code']} {cn_name(ev['code'])}\n"
                        f"現價 {ev['cur_price']:.2f}  均成本 {ev['avg_cost']:.2f}\n"
                        f"損益 {ev['unreal_p']:+.1f}% ({ev['unreal']:+,.0f}元)\n"
                        f"持股 {ev['total_shares']:,} 股\n"
                        f"策略：{ev['reason'][:80]}\n"
                        f"停損位：{ev['atr_stop']:.1f}\n"
                        f"⏰ {ev['urgency']} — {tw_now().strftime('%m/%d %H:%M')}"
                    )
                    ok, _ = _tg_send(_tok, _cid, msg)
                    if ok:
                        sent += 1
                st.success(f"✅ 已推播 {sent}/{len(evals)} 支持倉建議")

        # ── SECTION D: Google Sheets sync ────────────────
        st.divider()
        st.markdown("#### 📊 同步到 Google Sheets")
        st.caption("格式與系統一致：商品|交易日|交易別|股數|成交價|價金|手續費|交易稅|備註")

        gs_col1, gs_col2 = st.columns(2)
        gs_sheet = gs_col1.text_input("Sheet ID", key="port_gs_id",
            placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms")
        gs_token = gs_col2.text_input("OAuth Bearer Token", type="password",
            key="port_gs_token", placeholder="ya29.xxx")

        if st.button("⬆️ 上傳買賣記錄到 Google Sheets", key="port_gs_push",
                     width="stretch"):
            with st.spinner("上傳中…"):
                ok, err = gs_write_portfolio(gs_sheet, gs_token, trades_all)
            if ok:
                st.success("✅ 已上傳到 Portfolio 工作表")
            else:
                st.error(f"❌ {err}")
                st.caption("需要 OAuth Bearer Token (ya29.xxx)，可從 Google OAuth Playground 取得")

        # ── SECTION E: Export & Delete ───────────────────
        st.divider()
        with st.expander("📤 匯出 / 🗑 清除記錄"):
            df_export = pd.DataFrame(trades_all)
            buf = _io.BytesIO()
            import openpyxl as _xl
            wb = _xl.Workbook(); ws = wb.active; ws.title = "買賣記錄"
            cols = ["商品","交易日","交易別","股數","成交價","價金","手續費","交易稅","備註"]
            ws.append(cols)
            for t in trades_all:
                ws.append([t.get(c,"") for c in cols])
            wb.save(buf); buf.seek(0)
            st.download_button("📤 匯出 Excel", data=buf,
                file_name=f"portfolio_{tw_now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch")
            if st.button("🗑 清除所有記錄", key="port_clear"):
                port_save([])
                st.rerun()


# ── Footer ────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"📋 Watchlist Pro v{APP_VERSION} · {len(codes)} 支股票 · "
    f"最後更新 {tw_now().strftime('%H:%M:%S')} · "
    f"與 Sentinel Pro 獨立自選股清單"
)
