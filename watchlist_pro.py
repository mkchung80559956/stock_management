"""
Watchlist Pro v3.0  —  台股自選股管理系統
Clean rebuild: mobile-first, no emoji conflicts, works on Streamlit 1.56
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import json, os, pytz, io, openpyxl
import urllib.request as _req
import urllib.parse as _parse
import re as _re
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime, date

# ──────────────────────────────────────
# CONFIG
# ──────────────────────────────────────
st.set_page_config(
    page_title="自選股 PRO",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="auto",
)

APP_VERSION = "3.0"
APP_UPDATED = "2026-04-15"
TZ = pytz.timezone("Asia/Taipei")
def now_tw(): return datetime.now(TZ)
def today_str(): return now_tw().strftime("%Y-%m-%d")

_WL_FILE    = "/tmp/wlpro_watchlist.json"
_NOTE_FILE  = "/tmp/wlpro_notes.json"
_PORT_FILE  = "/tmp/wlpro_portfolio.json"
_ALERT_FILE = "/tmp/wlpro_alerts_sent.json"

# ──────────────────────────────────────
# DESIGN SYSTEM  (one place, no conflicts)
# ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

:root {
  --c-bg:      #050a14;
  --c-surface: #0a1220;
  --c-raised:  #0f1a2e;
  --c-border:  #182640;
  --c-line:    #1e3050;
  --c-text:    #d0dcea;
  --c-muted:   #4a6480;
  --c-dim:     #1e3050;
  --c-accent:  #0ea5e9;
  --c-green:   #10b981;
  --c-red:     #ef4444;
  --c-gold:    #f59e0b;
  --c-orange:  #f97316;
  --f-ui:      'Noto Sans TC', sans-serif;
  --f-num:     'JetBrains Mono', monospace;
}

/* Base */
html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMain"] > div {
  background: var(--c-bg) !important;
  color: var(--c-text) !important;
  font-family: var(--f-ui) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background: var(--c-surface) !important;
  border-right: 1px solid var(--c-border) !important;
}
section[data-testid="stSidebar"] * { color: var(--c-text) !important; }
section[data-testid="stSidebar"] > div { padding-top: 0.75rem !important; }


/* ── Sidebar toggle button — always visible, large tap target on mobile ── */
[data-testid="collapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  position: fixed !important;
  top: 8px !important;
  left: 8px !important;
  z-index: 9999 !important;
  background: var(--c-surface) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: 8px !important;
  width: 40px !important;
  height: 40px !important;
  align-items: center !important;
  justify-content: center !important;
  cursor: pointer !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4) !important;
}
[data-testid="collapsedControl"]:hover {
  border-color: var(--c-accent) !important;
  background: rgba(14,165,233,0.1) !important;
}
[data-testid="collapsedControl"] svg {
  fill: var(--c-text) !important;
  width: 18px !important;
  height: 18px !important;
}

/* Hide Streamlit chrome — keep header and collapsedControl for sidebar toggle */
#MainMenu, footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

/* Layout */
.block-container {
  padding: 0.8rem 1rem 2rem !important;
  max-width: 1100px !important;
}
@media (max-width: 640px) {
  .block-container {
    padding: 0.6rem 0.6rem 1.5rem 56px !important;
  }
}

/* Tabs — text only, no emoji to avoid overlap */
.stTabs [data-baseweb="tab-list"] {
  background: var(--c-surface) !important;
  border-bottom: 1px solid var(--c-border) !important;
  gap: 0; padding: 0 4px;
}
.stTabs [data-baseweb="tab"] {
  font-family: var(--f-ui) !important;
  font-size: 0.8rem !important;
  font-weight: 500 !important;
  color: var(--c-muted) !important;
  padding: 10px 14px !important;
  border-bottom: 2px solid transparent !important;
  background: transparent !important;
  white-space: nowrap;
  transition: color 0.15s;
}
.stTabs [aria-selected="true"] {
  color: var(--c-accent) !important;
  border-bottom-color: var(--c-accent) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 16px !important; }

/* Metrics */
div[data-testid="stMetric"] {
  background: var(--c-surface) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: 8px !important;
  padding: 12px 14px !important;
}
div[data-testid="stMetricLabel"] {
  font-size: 0.68rem !important;
  color: var(--c-muted) !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
div[data-testid="stMetricValue"] {
  font-family: var(--f-num) !important;
  font-size: 1.2rem !important;
  color: var(--c-text) !important;
}

/* Buttons */
.stButton > button {
  font-family: var(--f-ui) !important;
  font-size: 0.82rem !important;
  background: var(--c-raised) !important;
  border: 1px solid var(--c-line) !important;
  color: var(--c-text) !important;
  border-radius: 8px !important;
  min-height: 42px !important;
  transition: all 0.15s !important;
}
.stButton > button:hover {
  border-color: var(--c-accent) !important;
  color: var(--c-accent) !important;
}
.stButton > button[kind="primary"] {
  background: rgba(14,165,233,0.12) !important;
  border-color: var(--c-accent) !important;
  color: var(--c-accent) !important;
  font-weight: 600 !important;
  min-height: 46px !important;
}

/* Inputs */
.stTextInput input, .stNumberInput input {
  background: var(--c-raised) !important;
  border: 1px solid var(--c-line) !important;
  border-radius: 8px !important;
  color: var(--c-text) !important;
  font-family: var(--f-num) !important;
  font-size: 0.9rem !important;
  min-height: 44px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
  border-color: var(--c-accent) !important;
  box-shadow: 0 0 0 2px rgba(14,165,233,0.15) !important;
}
.stTextArea textarea {
  background: var(--c-raised) !important;
  border: 1px solid var(--c-line) !important;
  border-radius: 8px !important;
  color: var(--c-text) !important;
  font-size: 0.88rem !important;
}
.stSelectbox label, .stTextInput label,
.stNumberInput label, .stTextArea label,
.stMultiSelect label, .stFileUploader label {
  font-size: 0.75rem !important;
  color: var(--c-muted) !important;
  font-weight: 500 !important;
}
[data-baseweb="select"] > div {
  background: var(--c-raised) !important;
  border: 1px solid var(--c-line) !important;
  border-radius: 8px !important;
  min-height: 44px !important;
  color: var(--c-text) !important;
}
[data-baseweb="select"] > div:focus-within {
  border-color: var(--c-accent) !important;
}
[data-baseweb="popover"] li {
  background: var(--c-raised) !important;
  color: var(--c-text) !important;
}
[data-baseweb="popover"] li:hover {
  background: var(--c-raised) !important;
  color: var(--c-accent) !important;
}

/* Expanders — NO emoji in titles to avoid overlap with arrow */
details > summary {
  background: var(--c-surface) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: 8px !important;
  color: var(--c-text) !important;
  font-size: 0.84rem !important;
  font-weight: 500 !important;
  padding: 10px 14px !important;
  list-style: none !important;
}
.streamlit-expanderHeader {
  background: var(--c-surface) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: 8px !important;
  color: var(--c-text) !important;
  font-size: 0.84rem !important;
}
.streamlit-expanderContent {
  background: var(--c-bg) !important;
  border: 1px solid var(--c-border) !important;
  border-top: none !important;
  border-radius: 0 0 8px 8px !important;
}

/* File uploader — fix "uploadload" overlap */
[data-testid="stFileUploader"] {
  background: var(--c-raised) !important;
  border: 1px dashed var(--c-line) !important;
  border-radius: 8px !important;
  padding: 12px !important;
}
[data-testid="stFileUploader"] button {
  background: var(--c-raised) !important;
  border: 1px solid var(--c-line) !important;
  color: var(--c-accent) !important;
  border-radius: 6px !important;
  font-size: 0.8rem !important;
  min-height: 36px !important;
}
[data-testid="stFileUploader"] small { color: var(--c-muted) !important; font-size: 0.72rem !important; }

/* DataFrames */
.stDataFrame [data-testid="stDataFrameResizable"] {
  border: 1px solid var(--c-border) !important;
  border-radius: 8px !important;
}

/* Alerts */
.stSuccess { background: rgba(16,185,129,0.08) !important; border-left: 3px solid var(--c-green) !important; border-radius: 8px !important; color: var(--c-text) !important; }
.stInfo    { background: rgba(14,165,233,0.08) !important; border-left: 3px solid var(--c-accent) !important; border-radius: 8px !important; color: var(--c-text) !important; }
.stWarning { background: rgba(249,115,22,0.08) !important; border-left: 3px solid var(--c-orange) !important; border-radius: 8px !important; color: var(--c-text) !important; }
.stError   { background: rgba(239,68,68,0.08) !important; border-left: 3px solid var(--c-red) !important; border-radius: 8px !important; color: var(--c-text) !important; }

/* Divider */
hr { border-color: var(--c-border) !important; margin: 16px 0 !important; }

/* Card component */
.wl-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
}
.wl-card.rise { border-left: 3px solid var(--c-red); }
.wl-card.fall { border-left: 3px solid var(--c-green); }
.wl-card.flat { border-left: 3px solid var(--c-muted); }
.wl-card.hit  { border-left: 3px solid var(--c-gold); background: rgba(245,158,11,0.04); }
.wl-card.stop { border-left: 3px solid var(--c-red);  background: rgba(239,68,68,0.06); }

/* Section header */
.sec-hdr {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--c-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--c-border);
  margin-bottom: 14px;
}

/* Strategy card */
.strat-box {
  background: var(--c-surface);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 12px;
  border: 1px solid var(--c-border);
}
.kv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 6px;
  margin-top: 10px;
}
.kv-cell {
  background: var(--c-bg);
  border: 1px solid var(--c-dim);
  border-radius: 6px;
  padding: 6px 8px;
  text-align: center;
}
.kv-label { font-size: 0.58rem; color: var(--c-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.kv-value { font-family: var(--f-num); font-size: 0.8rem; font-weight: 700; color: var(--c-text); margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────
# PERSISTENCE
# ──────────────────────────────────────
def _atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)

# ── Persistence: always reads fresh from disk ──
# Do NOT use @st.cache_resource for mutable JSON stores —
# it returns a stale cached dict and group/note changes are lost on rerun.

def _load_wl():
    try:
        if os.path.exists(_WL_FILE):
            d = json.load(open(_WL_FILE))
            return d if isinstance(d, dict) else {"codes": d, "groups": {}}
    except: pass
    return {"codes": [], "groups": {}}

def _load_notes():
    try: return json.load(open(_NOTE_FILE)) if os.path.exists(_NOTE_FILE) else {}
    except: return {}

def _load_port():
    try: return json.load(open(_PORT_FILE)) if os.path.exists(_PORT_FILE) else {"trades": []}
    except: return {"trades": []}

def _is_tw_code(raw):
    bare = _re.sub(r'[^\x00-\x7F\d]', '', str(raw).upper().replace(".TW","").replace(".TWO","")).strip()
    return bool(_re.fullmatch(r'\d{4,6}', bare))

def wl_get():
    d = _load_wl()
    raw = d["codes"]
    valid = [c for c in raw if _is_tw_code(c)]
    if len(valid) != len(raw):          # auto-purge garbage codes
        d["codes"] = valid
        try: _atomic(_WL_FILE, d)
        except: pass
    return valid

def wl_group(c):
    return _load_wl().get("groups", {}).get(c, "未分組")

def wl_add(c):
    d = _load_wl(); c = c.upper()
    if c not in d["codes"]:
        d["codes"].append(c); _atomic(_WL_FILE, d); return True
    return False

def wl_remove(c):
    d = _load_wl()
    if c in d["codes"]:
        d["codes"].remove(c); _atomic(_WL_FILE, d); return True
    return False

def wl_set_group(c, g):
    d = _load_wl()
    d.setdefault("groups", {})[c] = g
    _atomic(_WL_FILE, d)

def note_get(c): return _load_notes().get(c, {})
def note_set(c, nd):
    d = _load_notes(); d[c] = nd; _atomic(_NOTE_FILE, d)

def port_get(): return _load_port().get("trades", [])
def port_save(t):
    d = _load_port(); d["trades"] = t; _atomic(_PORT_FILE, d)

# ──────────────────────────────────────
# NAMES
# ──────────────────────────────────────
_CN = {
    "2330":"台積電","2317":"鴻海","2454":"聯發科","2881":"富邦金",
    "2308":"台達電","2882":"國泰金","2303":"聯電","2886":"兆豐金",
    "2412":"中華電","2382":"廣達","2891":"中信金","3008":"大立光",
    "2603":"長榮","1301":"台塑","1303":"南亞","2892":"第一金",
    "2002":"中鋼","5880":"合庫金","2207":"和泰車","2395":"研華",
    "2357":"華碩","2887":"台新金","2327":"國巨","2885":"元大金",
    "2884":"玉山金","6415":"矽力-KY","5871":"中租-KY","0050":"元大台灣50",
    "00878":"國泰永續高息","00919":"群益精選高息","2880":"華南金",
    "2883":"開發金","2890":"永豐金","3019":"亞光","2379":"瑞昱",
    "3034":"聯詠","3711":"日月光","9921":"巨大","9951":"皇田",
    "2347":"聯強","2474":"可成","3045":"台灣大","2912":"統一超","1216":"統一",
}
def cn(c): return _CN.get(c.upper().replace(".TW","").replace(".TWO",""), c)

# ──────────────────────────────────────
# DATA
# ──────────────────────────────────────
@st.cache_data(ttl=60)
def qget(sym):
    bare = sym.upper().replace(".TW","").replace(".TWO","")
    for s in [bare+".TW", bare+".TWO"]:
        try:
            fi = yf.Ticker(s).fast_info
            px = getattr(fi,"last_price",0) or 0
            if not px: continue
            pv = getattr(fi,"previous_close",px) or px
            return {"px":round(px,2),"chg":round((px-pv)/pv*100,2) if pv else 0,
                    "hi":getattr(fi,"day_high",0) or 0,"lo":getattr(fi,"day_low",0) or 0,
                    "vol":getattr(fi,"last_volume",0) or 0,"ok":True}
        except: pass
    return {"ok":False,"px":0,"chg":0,"hi":0,"lo":0,"vol":0}

@st.cache_data(ttl=60)
def bulk_q(codes_t): return {c: qget(c) for c in codes_t}

@st.cache_data(ttl=300)
def hget(sym, prd="1mo"):
    bare = sym.upper().replace(".TW","").replace(".TWO","")
    for s in [bare+".TW", bare+".TWO"]:
        try:
            df = yf.Ticker(s).history(period=prd)
            if not df.empty: return df
        except: pass
    return pd.DataFrame()

# ──────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────
def tg_send(tok, cid, txt):
    if not tok or not cid: return False, "未設定"
    try:
        data = _parse.urlencode({"chat_id":str(cid).strip(),
                                  "text":_re.sub(r'<[^>]+>','',txt)}).encode()
        r = _req.Request(f"https://api.telegram.org/bot{tok.strip()}/sendMessage",
                         data=data, method="POST")
        r.add_header("Content-Type","application/x-www-form-urlencoded")
        with _req.urlopen(r, timeout=10) as resp:
            return (True,"") if resp.status==200 else (False,f"HTTP {resp.status}")
    except Exception as e:
        err=str(e)
        if hasattr(e,'read'):
            try: err+=" | "+e.read().decode()[:150]
            except: pass
        return False, err

def _alert_today(code, typ):
    try:
        d = json.load(open(_ALERT_FILE)) if os.path.exists(_ALERT_FILE) else {}
        return d.get(f"{code}_{typ}") == today_str()
    except: return False

def _mark_alert(code, typ):
    try:
        d = json.load(open(_ALERT_FILE)) if os.path.exists(_ALERT_FILE) else {}
        d[f"{code}_{typ}"] = today_str()
        _atomic(_ALERT_FILE, d)
    except: pass

def check_alerts(tok, cid, codes, Q):
    sent = []
    for c in codes:
        n=note_get(c); q=Q.get(c,{}); px=q.get("px",0)
        if not px: continue
        tgt=n.get("target"); stp=n.get("stop"); chg=q.get("chg",0)
        def push(typ, msg):
            if not _alert_today(c,typ):
                ok,_=tg_send(tok,cid,msg)
                if ok: _mark_alert(c,typ); sent.append(f"{c} {msg.split(chr(10))[0]}")
        if tgt and px>=tgt: push("tgt",f"🎯 {c} {cn(c)} 達標\n現價{px:.2f} 目標{tgt}\n{chg:+.2f}%")
        if stp and px<=stp: push("stp",f"🛑 {c} {cn(c)} 停損\n現價{px:.2f} 停損{stp}\n{chg:+.2f}%")
        if tgt and px<tgt and (tgt-px)/tgt*100<=2:
            push("near",f"⚠️ {c} 接近目標\n現價{px:.2f} 目標{tgt}")
    return sent

# ──────────────────────────────────────
# STRATEGY ENGINE
# ──────────────────────────────────────
def evaluate(code, trades, px):
    buys=[t for t in trades if t.get("交易別","") in("現買","買進","買") and str(t.get("商品","")).startswith(code)]
    sells=[t for t in trades if t.get("交易別","") in("現賣","賣出","賣") and str(t.get("商品","")).startswith(code)]
    held=sum(t.get("股數",0) for t in buys)-sum(t.get("股數",0) for t in sells)
    if held<=0 or not px: return None
    bq=sum(t.get("股數",0) for t in buys)
    avg=sum(t.get("股數",0)*t.get("成交價",0)+t.get("手續費",0) for t in buys)/bq if bq else 0
    unrl_p=(px-avg)/avg*100 if avg else 0
    stop7=round(avg*0.93,1)
    prices=[t.get("成交價",0) for t in buys]
    dca=f"{len(buys)}筆 均{avg:.1f} 低{min(prices):.1f} 高{max(prices):.1f}" if prices else ""
    if px<=stop7 and unrl_p<-10: act,clr,urg="立即停損","#ef4444","立即"
    elif unrl_p<-15:              act,clr,urg="深度虧損","#ef4444","本週"
    elif unrl_p<-7:               act,clr,urg="審視停損","#f97316","觀察"
    elif unrl_p>=25:              act,clr,urg="分批獲利","#f97316","本週"
    elif unrl_p>=12:              act,clr,urg="續抱觀察","#10b981","觀察"
    elif prices and px<=min(prices)*1.02 and len(buys)<12: act,clr,urg="底部評估","#0ea5e9","觀察"
    else:                         act,clr,urg="持有觀察","#4a6480","觀察"
    if unrl_p<-10: reason=f"虧損{unrl_p:.1f}%，停損位{stop7}，建議控制損失"
    elif unrl_p<0: reason=f"虧損{unrl_p:.1f}%，持續觀察技術面訊號"
    elif unrl_p>=20: reason=f"獲利{unrl_p:.1f}%，可考慮分批獲利了結"
    else: reason=f"損益{unrl_p:+.1f}%，等待明確方向訊號"
    return {"code":code,"name":cn(code),"held":held,"avg":round(avg,2),
            "px":px,"unrl_p":round(unrl_p,2),"unrl":round((px-avg)*held),
            "stop7":stop7,"act":act,"clr":clr,"urg":urg,"reason":reason,"dca":dca,
            "first":min(t.get("交易日","") for t in buys) if buys else ""}

# ──────────────────────────────────────
# GS
# ──────────────────────────────────────
_GS="https://sheets.googleapis.com/v4/spreadsheets"
def gs_push(sid,tok,trades):
    if not sid or not tok: return False,"未設定"
    hdr=[["商品","交易日","交易別","股數","成交價","價金","手續費","交易稅","備註"]]
    rows=hdr+[[t.get(k,"") for k in["商品","交易日","交易別","股數","成交價","價金","手續費","交易稅","備註"]] for t in trades]
    try:
        for url,body,method in [
            (f"{_GS}/{sid}/values/Portfolio!A1:I10000:clear",b"{}","POST"),
            (f"{_GS}/{sid}/values/Portfolio!A1?valueInputOption=USER_ENTERED",
             json.dumps({"values":rows}).encode(),"PUT"),
        ]:
            r=_req.Request(url,data=body,method=method)
            r.add_header("Authorization",f"Bearer {tok.strip()}")
            r.add_header("Content-Type","application/json")
            with _req.urlopen(r,timeout=10): pass
        return True,""
    except Exception as e:
        err=str(e)
        if hasattr(e,'read'):
            try: err+=" | "+e.read().decode()[:200]
            except: pass
        return False,err

GROUPS=["未分組","半導體","金融","電子","傳產","ETF","觀察中"]

# ──────────────────────────────────────
# HEADER
# ──────────────────────────────────────
st.markdown(f"""
<div style="padding-bottom:12px;border-bottom:1px solid var(--c-border);margin-bottom:18px">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
    <div style="font-family:var(--f-num);font-size:1.2rem;font-weight:700;color:var(--c-text)">
      自選股 <span style="color:var(--c-accent)">PRO</span>
      <span style="font-size:0.65rem;color:var(--c-muted);font-weight:400;
        margin-left:10px;letter-spacing:0.06em">v{APP_VERSION}</span>
    </div>
    <div style="font-family:var(--f-num);font-size:0.72rem;color:var(--c-muted)">
      {now_tw().strftime("%m/%d  %H:%M")}
    </div>
  </div>
  <div style="font-size:0.72rem;color:var(--c-muted);margin-top:3px">台股自選股管理系統</div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sec-hdr">自選股管理</div>', unsafe_allow_html=True)

    with st.expander("新增股票"):
        nc = st.text_input("代號", placeholder="2330 / 3019 / 0050", label_visibility="collapsed", key="sb_nc")
        ng = st.selectbox("分組", GROUPS, label_visibility="collapsed", key="sb_ng")
        if st.button("新增", type="primary", width='stretch', key="sb_add"):
            bare = nc.strip().upper().replace(".TW","").replace(".TWO","")
            if bare and _is_tw_code(bare):
                if wl_add(bare): wl_set_group(bare, ng); st.success(f"已新增 {bare}"); st.rerun()
                else: st.warning("已在清單中")
            elif bare: st.error("格式不正確（需4-6位數字）")

    codes = wl_get()
    if codes:
        with st.expander("移除股票"):
            dc = st.selectbox("選擇", codes, format_func=lambda x:f"{x} {cn(x)}", label_visibility="collapsed", key="sb_dc")
            if st.button("移除", width='stretch', key="sb_del"):
                wl_remove(dc); st.success(f"已移除 {dc}"); st.rerun()

        with st.expander("調整分組"):
            mc = st.selectbox("股票", codes, format_func=lambda x:f"{x} {cn(x)}", label_visibility="collapsed", key="sb_mc")
            mg = st.selectbox("分組", GROUPS, label_visibility="collapsed", key="sb_mg")
            if st.button("更新", width='stretch', key="sb_mg_btn"):
                wl_set_group(mc, mg); st.success("已更新"); st.rerun()

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">推播通知</div>', unsafe_allow_html=True)

    with st.expander("Telegram 設定"):
        _ts={}
        try: _ts=st.secrets.get("telegram",{})
        except: pass
        tg_tok = st.text_input("Bot Token", value=_ts.get("token",""), type="password", key="tg_tok")
        tg_cid = st.text_input("Chat ID", value=_ts.get("chat_id",""), key="tg_cid")
        if tg_tok:
            st.markdown(f'<a href="https://api.telegram.org/bot{tg_tok}/getUpdates" target="_blank" '
                        f'style="font-size:0.75rem;color:var(--c-accent)">查詢 Chat ID</a>',
                        unsafe_allow_html=True)
        if st.button("測試推播", width='stretch', key="tg_test"):
            ok,e = tg_send(tg_tok, tg_cid, f"自選股 PRO 測試 {now_tw().strftime('%H:%M')}")
            st.success("成功") if ok else st.error(e)

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">資料</div>', unsafe_allow_html=True)

    with st.expander("匯入 / 匯出自選股"):
        if wl_get():
            buf = io.BytesIO()
            wb2 = openpyxl.Workbook(); ws2 = wb2.active; ws2.title="自選股"
            ws2.append(["代號","名稱","分組"])
            for c in wl_get(): ws2.append([c, cn(c), wl_group(c)])
            wb2.save(buf); buf.seek(0)
            st.download_button("匯出 Excel", data=buf,
                file_name=f"watchlist_{today_str()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch')
        uf = st.file_uploader("從 Excel 匯入自選股", type=["xlsx"])
        if uf:
            try:
                df_i = pd.read_excel(uf, sheet_name=0)
                added=0
                for _,r in df_i.iterrows():
                    c=str(r.get("代號",r.get("code",""))).strip().upper()
                    g=str(r.get("分組","未分組")).strip()
                    if c and _is_tw_code(c) and wl_add(c): wl_set_group(c,g); added+=1
                st.success(f"匯入 {added} 支"); st.rerun()
            except Exception as e: st.error(str(e))

    with st.expander("自動更新"):
        auto=st.toggle("啟用", value=False, key="auto_ref")
        if auto:
            ivl=st.select_slider("間隔",["30秒","1分","5分"],value="1分")
            secs={"30秒":30,"1分":60,"5分":300}[ivl]
            st.markdown(f'<meta http-equiv="refresh" content="{secs}">', unsafe_allow_html=True)
            st.caption(f"每 {ivl} 刷新")
    if st.button("立即刷新報價", width='stretch'):
        st.cache_data.clear(); st.rerun()

    st.markdown('<hr>', unsafe_allow_html=True)
    with st.expander("緊急重置"):
        st.caption("App 卡住時使用")
        if st.button("清除所有暫存", width='stretch', key="er_all"):
            for f in [_WL_FILE,_NOTE_FILE,_PORT_FILE,_ALERT_FILE]:
                try: os.remove(f)
                except: pass
            st.cache_data.clear(); st.rerun()
        if st.button("只清自選股清單", width='stretch', key="er_wl"):
            try: os.remove(_WL_FILE)
            except: pass
            st.rerun()

# ──────────────────────────────────────
# EMPTY STATE — inline form
# ──────────────────────────────────────
codes = wl_get()
if not codes:
    st.markdown("""
<div style="text-align:center;padding:40px 0 24px">
  <div style="font-size:2.5rem">📋</div>
  <div style="font-size:1rem;font-weight:600;color:var(--c-text);margin-top:12px">清單為空</div>
  <div style="font-size:0.82rem;color:var(--c-muted);margin-top:4px">輸入股票代號開始使用</div>
</div>""", unsafe_allow_html=True)
    ec = st.text_input("代號", placeholder="2330 / 3019 / 0050", label_visibility="collapsed", key="em_c")
    eg = st.selectbox("分組", GROUPS, label_visibility="collapsed", key="em_g")
    if st.button("新增到自選股", type="primary", width='stretch', key="em_add"):
        bare = ec.strip().upper().replace(".TW","").replace(".TWO","")
        if bare and _is_tw_code(bare):
            wl_add(bare); wl_set_group(bare, eg); st.rerun()
        elif bare: st.error("需4-6位數字代號")
    st.caption("常用：2330 台積電 ／ 2317 鴻海 ／ 0050 元大台灣50")
    st.stop()

# ──────────────────────────────────────
# FETCH QUOTES + ALERTS
# ──────────────────────────────────────
with st.spinner("載入中…"):
    Q = bulk_q(tuple(codes))

tok_v = st.session_state.get("tg_tok","")
cid_v = st.session_state.get("tg_cid","")
if tok_v and cid_v:
    for a in check_alerts(tok_v, cid_v, codes, Q):
        st.toast(a, icon="📲")

# ──────────────────────────────────────
# TABS — short labels only, no leading emoji (prevents overlap)
# ──────────────────────────────────────
t1,t2,t3,t4,t5,t6 = st.tabs(["總覽","卡片","監控","備忘","警報","持倉"])

# ═══ TAB 1 OVERVIEW ═══
with t1:
    grps = sorted(set(wl_group(c) for c in codes))
    fg = st.selectbox("分組", ["全部"]+grps, label_visibility="collapsed", key="t1_grp")
    rows=[]
    for c in codes:
        if fg!="全部" and wl_group(c)!=fg: continue
        q=Q.get(c,{}); n=note_get(c)
        px=q.get("px",0); chg=q.get("chg",0)
        tgt=n.get("target"); stp=n.get("stop")
        up=round((tgt/px-1)*100,1) if tgt and px else None
        st_txt=("🎯達標" if tgt and px and px>=tgt else
                "🛑停損" if stp and px and px<=stp else
                "⚠️接近" if tgt and px and up and 0<up<=3 else "─")
        rows.append({"代號":c,"名稱":cn(c),"分組":wl_group(c),
                     "現價":px or None,"漲跌%":chg if q.get("ok") else None,
                     "目標":float(tgt) if tgt else None,
                     "停損":float(stp) if stp else None,
                     "上漲空間":up,"狀態":st_txt})
    if rows:
        valid=[r for r in rows if r["漲跌%"] is not None]
        c1,c2=st.columns(2); c3,c4=st.columns(2)
        c1.metric("持倉",len(codes))
        c2.metric("警報",sum(1 for r in rows if r["狀態"]!="─"))
        c3.metric("上漲",sum(1 for r in valid if (r["漲跌%"] or 0)>0))
        c4.metric("下跌",sum(1 for r in valid if (r["漲跌%"] or 0)<0))
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True,
            column_config={
                "漲跌%":st.column_config.NumberColumn(format="%+.2f%%"),
                "上漲空間":st.column_config.NumberColumn(format="%+.1f%%"),
                "現價":st.column_config.NumberColumn(format="%.2f"),
            })

# ═══ TAB 2 CARDS ═══
with t2:
    srt=st.radio("排序",["預設","漲幅","跌幅","分組"],horizontal=True,label_visibility="collapsed",key="t2_sort")
    sc=list(codes)
    if srt=="漲幅": sc.sort(key=lambda x:-Q.get(x,{}).get("chg",0))
    elif srt=="跌幅": sc.sort(key=lambda x:Q.get(x,{}).get("chg",0))
    elif srt=="分組": sc.sort(key=wl_group)
    for i in range(0,len(sc),2):
        chunk=sc[i:i+2]; cols=st.columns(2)
        for ci,c in enumerate(chunk):
            q=Q.get(c,{}); n=note_get(c)
            px=q.get("px",0); chg=q.get("chg",0)
            tgt=n.get("target"); stp=n.get("stop")
            hi=q.get("hi",0); lo=q.get("lo",0)
            if not q.get("ok"):  clr="var(--c-muted)"; cls="flat"
            elif chg>0:          clr="var(--c-red)";   cls="rise"
            elif chg<0:          clr="var(--c-green)"; cls="fall"
            else:                clr="var(--c-muted)"; cls="flat"
            if tgt and px and px>=tgt: cls="hit"; clr="var(--c-gold)"
            if stp and px and px<=stp: cls="stop"; clr="var(--c-red)"
            px_s   = f"{px:.2f}" if px else "—"
            chg_s  = f"{chg:+.2f}%" if q.get("ok") else "—"
            hi_s   = f"{hi:.2f}" if hi else "—"
            lo_s   = f"{lo:.2f}" if lo else "—"
            with cols[ci]:
                st.markdown(f"""
<div class="wl-card {cls}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
    <span style="font-family:var(--f-num);font-weight:700;color:var(--c-text);font-size:0.9rem">{c}</span>
    <span style="font-size:0.62rem;background:var(--c-raised);color:var(--c-muted);
      padding:2px 7px;border-radius:4px;border:1px solid var(--c-dim)">{wl_group(c)}</span>
  </div>
  <div style="font-size:0.75rem;color:var(--c-muted);margin-bottom:8px">{cn(c)}</div>
  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px">
    <span style="font-family:var(--f-num);font-size:1.3rem;font-weight:700;color:{clr}">{px_s}</span>
    <span style="font-size:0.8rem;font-weight:600;color:{clr}">{chg_s}</span>
  </div>
  <div style="font-size:0.68rem;color:var(--c-dim);display:flex;gap:10px;flex-wrap:wrap;font-family:var(--f-num)">
    <span>H {hi_s}</span><span>L {lo_s}</span>
    {"<span style='color:var(--c-gold)'>目标"+str(tgt)+"</span>" if tgt else ""}
    {"<span style='color:var(--c-red)'>停损"+str(stp)+"</span>" if stp else ""}
  </div>
  {("<div style='font-size:0.68rem;color:var(--c-dim);margin-top:6px;border-top:1px solid var(--c-dim);padding-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>"+n.get("note","")[:40]+"</div>") if n.get("note") else ""}
</div>""", unsafe_allow_html=True)

# ═══ TAB 3 MONITOR ═══
with t3:
    valid_c=[c for c in codes if Q.get(c,{}).get("ok")]
    if valid_c:
        sv=sorted(valid_c,key=lambda x:-Q[x]["chg"])
        g1,g2=st.columns(2)
        for col,title,lst,clr in [(g1,"漲幅前3",sv[:3],"var(--c-red)"),(g2,"跌幅前3",sv[-3:][::-1],"var(--c-green)")]:
            with col:
                st.markdown(f'<div class="sec-hdr">{title}</div>',unsafe_allow_html=True)
                for c in lst:
                    q=Q[c]; chg=q["chg"]; px=q["px"]
                    st.markdown(f"""
<div style="background:var(--c-surface);border-left:2px solid {clr};
  border:1px solid var(--c-border);border-left:3px solid {clr};
  padding:9px 12px;border-radius:0 8px 8px 0;margin-bottom:6px;
  display:flex;justify-content:space-between;align-items:center">
  <span style="font-weight:600;color:var(--c-text);font-size:0.85rem">{c}
    <span style="font-weight:400;color:var(--c-muted);font-size:0.75rem;margin-left:6px">{cn(c)}</span>
  </span>
  <span style="font-family:var(--f-num);font-weight:700;color:{clr};font-size:0.85rem">{chg:+.2f}%
    <span style="color:var(--c-text);margin-left:8px">{px:.2f}</span>
  </span>
</div>""", unsafe_allow_html=True)
    st.markdown('<hr>', unsafe_allow_html=True)
    chart_c=st.selectbox("股票",codes,format_func=lambda x:f"{x} {cn(x)}",label_visibility="collapsed",key="t3_c")
    prd=st.radio("區間",["1mo","3mo","6mo","1y"],horizontal=True,label_visibility="collapsed",key="t3_prd")
    with st.spinner(""):
        dfh=hget(chart_c,prd)
    if not dfh.empty:
        nm=note_get(chart_c)
        va=dfh["Volume"].mean()
        fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.72,0.28],
                          vertical_spacing=0.04,specs=[[{"secondary_y":False}],[{"secondary_y":False}]])
        fig.add_trace(go.Candlestick(x=dfh.index,open=dfh["Open"],high=dfh["High"],
            low=dfh["Low"],close=dfh["Close"],
            increasing_fillcolor="#ef4444",increasing_line_color="#ef4444",
            decreasing_fillcolor="#10b981",decreasing_line_color="#10b981",
            showlegend=False),row=1,col=1)
        if nm.get("target"):
            fig.add_hline(y=nm["target"],line_dash="dot",line_color="#f59e0b",line_width=1.5,
                annotation_text=f"目標 {nm['target']}",annotation_font_color="#f59e0b",row=1,col=1)
        if nm.get("stop"):
            fig.add_hline(y=nm["stop"],line_dash="dot",line_color="#ef4444",line_width=1.5,
                annotation_text=f"停損 {nm['stop']}",annotation_font_color="#ef4444",row=1,col=1)
        vc=["#ef4444" if dfh["Close"].iloc[i]>=dfh["Open"].iloc[i] else "#10b981" for i in range(len(dfh))]
        fig.add_trace(go.Bar(x=dfh.index,y=dfh["Volume"],marker_color=vc,showlegend=False),row=2,col=1)
        sp=dfh[dfh["Volume"]>va*2]
        if not sp.empty:
            fig.add_trace(go.Scatter(x=sp.index,y=sp["Volume"],mode="markers",
                marker=dict(color="#f59e0b",size=7,symbol="diamond"),name="量異常"),row=2,col=1)
        fig.update_layout(template="plotly_dark",height=380,
            paper_bgcolor="rgba(5,10,20,1)",plot_bgcolor="rgba(10,18,32,1)",
            margin=dict(l=45,r=75,t=8,b=8),
            font=dict(family="JetBrains Mono",size=10,color="#4a6480"),
            hovermode="x unified",xaxis_rangeslider_visible=False)
        fig.update_yaxes(gridcolor="#182640");fig.update_xaxes(gridcolor="#182640",showgrid=False)
        st.plotly_chart(fig, width='stretch')
        last_vol=dfh["Volume"].iloc[-1]
        if last_vol>va*2: st.warning(f"成交量異常放量 {last_vol/va:.1f}x 均量")
    else: st.info("無歷史資料")

# ═══ TAB 4 NOTES ═══
with t4:
    ns=st.selectbox("股票",codes,format_func=lambda x:f"{x} {cn(x)}",label_visibility="collapsed",key="t4_s")
    ex=note_get(ns)
    with st.form("nf"):
        nt=st.text_area("備忘 / 進場理由",value=ex.get("note",""),height=90,placeholder="記錄關注原因、進場邏輯…")
        nc1,nc2=st.columns(2)
        ep=nc1.number_input("進場均價",min_value=0.0,value=float(ex.get("entry",0) or 0),step=0.5)
        wd=nc2.text_input("關注日期",value=ex.get("watch_date",today_str()))
        tgs=st.multiselect("標籤",["技術突破","籌碼轉強","法人買超","業績成長","低估值","高殖利率","週期底部","題材","其他"],default=ex.get("tags",[]))
        if st.form_submit_button("儲存",type="primary"):
            note_set(ns,{**ex,"note":nt,"entry":ep,"watch_date":wd,"tags":tgs,
                          "updated":now_tw().strftime("%Y-%m-%d %H:%M")})
            st.success("已儲存")
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">所有備忘</div>', unsafe_allow_html=True)
    nr=[{"代號":c,"名稱":cn(c),"備忘":note_get(c).get("note","")[:40],"標籤":"、".join(note_get(c).get("tags",[])),
         "均價":note_get(c).get("entry",""),"日期":note_get(c).get("watch_date","")}
        for c in codes if note_get(c).get("note") or note_get(c).get("tags")]
    if nr: st.dataframe(pd.DataFrame(nr), width='stretch', hide_index=True)
    else: st.info("尚無備忘")

# ═══ TAB 5 ALERTS ═══
with t5:
    if tok_v and cid_v: st.success("Telegram 推播已啟用")
    else: st.info("在側欄設定 Telegram 以啟用自動推播")
    with st.expander("設定目標價 / 停損價", expanded=True):
        ac=st.selectbox("股票",codes,format_func=lambda x:f"{x} {cn(x)}",label_visibility="collapsed",key="t5_c")
        ea=note_get(ac); qa=Q.get(ac,{})
        cpx=qa.get("px",0)
        ac1,ac2=st.columns(2)
        tp=ac1.number_input("目標價",min_value=0.0,step=0.5,value=float(ea.get("target",0) or 0))
        sp2=ac2.number_input("停損價",min_value=0.0,step=0.5,value=float(ea.get("stop",0) or 0))
        if cpx and tp:
            up2=(tp/cpx-1)*100
            st.caption(f"上漲空間：{up2:+.1f}%")
        if st.button("儲存設定",type="primary",key="t5_save",width='stretch'):
            note_set(ac,{**ea,"target":tp or None,"stop":sp2 or None})
            st.success(f"已設定 {ac}"); st.rerun()
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">警報狀態</div>', unsafe_allow_html=True)
    ar=[]
    for c in codes:
        n=note_get(c); q=Q.get(c,{}); px=q.get("px",0)
        t_=n.get("target"); s_=n.get("stop")
        if not(t_ or s_): continue
        up3=round((t_/px-1)*100,1) if t_ and px else None
        sl=[]
        if t_ and px and px>=t_:            sl.append("🎯 達標")
        if s_ and px and px<=s_:            sl.append("🛑 停損")
        if t_ and px and up3 and 0<up3<=3:  sl.append("⚠️ 接近目標")
        if not sl: sl.append("✅ 正常")
        ar.append({"代號":c,"名稱":cn(c),"現價":round(px,2) if px else None,
                   "目標":float(t_) if t_ else None,"停損":float(s_) if s_ else None,
                   "上漲空間":f"{up3:+.1f}%" if up3 is not None else None,
                   "狀態":" ".join(sl)})
    if ar:
        st.dataframe(pd.DataFrame(ar), width='stretch', hide_index=True,
                     column_config={"現價":st.column_config.NumberColumn(format="%.2f")})
        for r in ar:
            if "達標" in r["狀態"] or "停損" in r["狀態"]:
                clr="#f59e0b" if "達標" in r["狀態"] else "#ef4444"
                st.markdown(f"""
<div style="border:1px solid {clr};border-radius:8px;padding:10px 14px;margin-bottom:8px;
  background:rgba({'245,158,11' if '達標' in r['狀態'] else '239,68,68'},0.08)">
  <b style="color:{clr}">{r['狀態']}</b>&emsp;
  <span style="color:var(--c-text)">{r['代號']} {r['名稱']}</span>&emsp;
  <span style="font-family:var(--f-num);color:var(--c-muted)">{r['現價']}</span>
</div>""", unsafe_allow_html=True)
    else: st.info("尚未設定目標價或停損價")

# ═══ TAB 6 PORTFOLIO ═══
with t6:
    trades=port_get()
    with st.expander("匯入買賣記錄", expanded=not trades):
        st.markdown("""<div style="font-size:0.8rem;color:var(--c-muted);margin-bottom:12px;line-height:1.7">
支援格式：<span style="font-family:var(--f-num);color:var(--c-accent)">商品｜交易日｜交易別｜股數｜成交價｜價金｜手續費｜交易稅</span><br>
從券商 App 匯出 Excel，或上傳截圖請 Claude 轉換。</div>""", unsafe_allow_html=True)

        imp=st.file_uploader("選擇 Excel 檔案 (.xlsx)", type=["xlsx","xls"])
        if imp:
            try:
                df_im=None
                for hr in [0,1,2]:
                    try:
                        imp.seek(0); dft=pd.read_excel(imp,header=hr,sheet_name=0)
                        if any(k in " ".join(str(c) for c in dft.columns) for k in ["商品","交易日","代號"]):
                            df_im=dft; break
                    except: pass
                if df_im is None: imp.seek(0); df_im=pd.read_excel(imp,sheet_name=0)
                cm={"商品":["商品","股票","代號"],"交易日":["交易日","日期"],"交易別":["交易別","買賣"],
                    "股數":["股數","數量"],"成交價":["成交價","價格"],"價金":["價金","金額"],
                    "手續費":["手續費","費用"],"交易稅":["交易稅","稅"]}
                rc={}
                for tgt,cands in cm.items():
                    for cand in cands:
                        m=[c for c in df_im.columns if cand in str(c)]
                        if m: rc[tgt]=m[0]; break
                if "商品" not in rc: st.error("找不到「商品」欄位")
                else:
                    df_m=pd.DataFrame()
                    for tgt,src in rc.items(): df_m[tgt]=df_im[src]
                    for col in ["商品","交易日","交易別","股數","成交價","價金","手續費","交易稅","備註"]:
                        if col not in df_m: df_m[col]=0 if col in["股數","成交價","價金","手續費","交易稅"] else ""
                    for nc in["股數","成交價","價金","手續費","交易稅"]:
                        df_m[nc]=pd.to_numeric(df_m[nc],errors="coerce").fillna(0)
                    st.dataframe(df_m.head(6), width='stretch', hide_index=True)
                    if st.button("確認匯入",type="primary",width='stretch'):
                        port_save(df_m.to_dict("records")); st.success(f"匯入 {len(df_m)} 筆"); st.rerun()
            except Exception as e: st.error(str(e))
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.78rem;color:var(--c-muted);margin-bottom:8px">手動新增</div>', unsafe_allow_html=True)
        with st.form("atf"):
            fc1,fc2,fc3=st.columns(3)
            tc=fc1.text_input("商品",placeholder="3019亞光")
            td=fc2.date_input("交易日",value=date.today())
            tt=fc3.selectbox("交易別",["現買","現賣"])
            fc4,fc5=st.columns(2); fc6,fc7=st.columns(2)
            tq=fc4.number_input("股數",min_value=1,value=50)
            tp2=fc5.number_input("成交價",min_value=0.1,value=100.0,step=0.5)
            tf=fc6.number_input("手續費",min_value=0,value=int(tq*tp2*0.001425*0.6))
            tx=fc7.number_input("交易稅",min_value=0,value=int(tq*tp2*0.003) if tt=="現賣" else 0)
            if st.form_submit_button("新增",type="primary"):
                et=port_get(); et.append({"商品":tc,"交易日":str(td),"交易別":tt,
                    "股數":int(tq),"成交價":float(tp2),"價金":int(tq*tp2),"手續費":int(tf),"交易稅":int(tx),"備註":""})
                port_save(et); st.success("已新增"); st.rerun()

    if not trades:
        st.info("請先匯入買賣記錄"); st.stop()

    # Analysis
    st.markdown('<div class="sec-hdr">持倉損益</div>', unsafe_allow_html=True)
    all_p=sorted(set(
        c for c in (_re.match(r'^\d{4,6}',str(t.get("商品",""))).group() if _re.match(r'^\d{4,6}',str(t.get("商品",""))) else None
                    for t in trades) if c))
    evs=[]
    for code in all_p:
        q2=qget(code); px2=q2.get("px",0)
        if not px2: q2=qget(code+".TW"); px2=q2.get("px",0)
        ev=evaluate(code,trades,px2)
        if ev: evs.append(ev)

    if evs:
        tc_=sum(e["avg"]*e["held"] for e in evs)
        tm_=sum(e["px"]*e["held"] for e in evs)
        tu_=tm_-tc_; tp_=tu_/tc_*100 if tc_ else 0
        m1,m2=st.columns(2); m3,m4=st.columns(2)
        m1.metric("持倉",len(evs)); m2.metric("投入",f"{tc_/1e4:.1f}萬")
        m3.metric("市值",f"{tm_/1e4:.1f}萬"); m4.metric("損益",f"{tu_/1e4:+.1f}萬",f"{tp_:+.1f}%")
        st.dataframe(pd.DataFrame([{"代號":e["code"],"名稱":e["name"],"持股":e["held"],
            "均成本":e["avg"],"現價":e["px"],"損益%":e["unrl_p"],"損益元":e["unrl"],"建議":e["act"]}
            for e in evs]), width='stretch', hide_index=True,
            column_config={"損益%":st.column_config.NumberColumn(format="%+.2f%%"),
                           "損益元":st.column_config.NumberColumn(format="$%+,.0f")})

        st.markdown('<div class="sec-hdr" style="margin-top:20px">策略建議</div>', unsafe_allow_html=True)
        uo={"立即":0,"本週":1,"觀察":2}
        for ev in sorted(evs,key=lambda e:uo.get(e["urg"],3)):
            pnl_c="var(--c-green)" if ev["unrl_p"]>=0 else "var(--c-red)"
            ul_map={"立即":"🔴 立即處理","本週":"🟠 本週處理","觀察":"⚪ 持續觀察"}
            ul=ul_map.get(ev["urg"],"")
            st.markdown(f"""
<div class="strat-box" style="border-left:3px solid {ev['clr']}">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px">
    <div>
      <span style="font-family:var(--f-num);font-weight:700;font-size:0.9rem;color:var(--c-text)">{ev['code']}</span>
      <span style="font-size:0.8rem;color:var(--c-muted);margin-left:8px">{ev['name']}</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <span style="font-size:0.7rem;color:{ev['clr']};border:1px solid {ev['clr']};
        padding:2px 8px;border-radius:10px">{ul}</span>
      <span style="font-weight:700;color:{ev['clr']};font-size:0.9rem">{ev['act']}</span>
    </div>
  </div>
  <div style="font-size:0.82rem;color:var(--c-muted);padding:8px 10px;background:var(--c-bg);
    border-radius:6px;margin-bottom:10px;border-left:2px solid {ev['clr']}">{ev['reason']}</div>
  <div class="kv-grid">
    {"".join(f'<div class="kv-cell"><div class="kv-label">{lbl}</div><div class="kv-value" style="color:{col}">{val}</div></div>'
             for lbl,val,col in [("持股",f"{ev['held']:,}","var(--c-text)"),("均成本",f"{ev['avg']:.2f}","var(--c-text)"),
               ("現價",f"{ev['px']:.2f}","var(--c-text)"),("損益",f"{ev['unrl_p']:+.1f}%",pnl_c),("停損",str(ev['stop7']),"var(--c-red)")])}
  </div>
  <div style="font-size:0.65rem;color:var(--c-dim);margin-top:8px;padding-top:6px;
    border-top:1px solid var(--c-border)">{ev['dca']}  首買 {ev['first']}</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">同步與匯出</div>', unsafe_allow_html=True)

    _gs_s={}
    try: _gs_s=st.secrets.get("gsheets",{})
    except: pass
    gs1,gs2=st.columns(2)
    gsid=gs1.text_input("Google Sheet ID",value=_gs_s.get("sheet_id",""),key="gsid",
        help="URL 中 /d/【這段】/edit")
    gstok=gs2.text_input("OAuth Token",value=_gs_s.get("token",""),type="password",key="gstok",
        help="ya29.xxx — 從 OAuth Playground 取得")

    with st.expander("設定教學"):
        st.markdown("""
**Streamlit Cloud Secrets 設定（最安全）**
App → `⋮` → Settings → Secrets：
```toml
[telegram]
token   = "..."
chat_id = "..."

[gsheets]
sheet_id = "..."
token    = "ya29.xxx"
```
**取得 OAuth Token**：[Google OAuth Playground](https://developers.google.com/oauthplayground)
→ Google Sheets API v4 → spreadsheets → Authorize → Exchange → 複製 Access token
""")

    b1,b2,b3=st.columns(3)
    if b1.button("同步到 Google Sheets",width='stretch',type="primary"):
        with st.spinner("上傳中…"):
            ok,err=gs_push(gsid,gstok,trades)
        st.success("已同步") if ok else st.error(err)

    if b2.button("推播策略到 Telegram",width='stretch'):
        if not tok_v or not cid_v: st.warning("請先設定 Telegram")
        else:
            ns_=0
            for ev in (evs if evs else []):
                ok2,_=tg_send(tok_v,cid_v,
                    f"{ev['act']} {ev['code']} {ev['name']}\n"
                    f"現價{ev['px']:.2f} 均{ev['avg']:.2f} 損益{ev['unrl_p']:+.1f}%\n{ev['reason']}")
                if ok2: ns_+=1
            st.success(f"已推播 {ns_} 支")

    buf3=io.BytesIO()
    wb3=openpyxl.Workbook(); ws3=wb3.active; ws3.title="買賣記錄"
    cs_=["商品","交易日","交易別","股數","成交價","價金","手續費","交易稅","備註"]
    ws3.append(cs_)
    for t in trades: ws3.append([t.get(c,"") for c in cs_])
    wb3.save(buf3); buf3.seek(0)
    b3.download_button("下載 Excel",data=buf3,
        file_name=f"portfolio_{today_str()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width='stretch')

    if st.button("清除所有交易記錄",key="clr_port",width='stretch'):
        port_save([]); st.rerun()

# ──────────────────────────────────────
# FOOTER
# ──────────────────────────────────────
st.markdown(f"""
<div style="border-top:1px solid var(--c-border);margin-top:20px;padding-top:10px;
  display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px">
  <span style="font-family:var(--f-num);font-size:0.65rem;color:var(--c-dim)">
    自選股 PRO v{APP_VERSION} · {len(codes)} 支 · {now_tw().strftime("%H:%M:%S")}
  </span>
  <span style="font-size:0.65rem;color:var(--c-dim)">哨兵系統配套工具</span>
</div>
""", unsafe_allow_html=True)
