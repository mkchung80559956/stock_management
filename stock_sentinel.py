import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from curl_cffi import requests as cffi_requests
import time
import io
from datetime import datetime, date

# ── 股票名稱對照表 ───────────────────────────────────────────────────────────
COMPANY_NAMES = {
    "2317.TW":  "鴻海精密",    "2330.TW":  "台灣積電",    "5347.TWO": "世界先進",
    "3483.TWO": "力致科技",    "3019.TW":  "亞光電子",    "2882.TW":  "國泰金控",
    "2354.TW":  "鴻準精密",    "4566.TW":  "智邦科技",    "2329.TW":  "華泰電子",
    "6271.TW":  "同欣電子",    "3479.TW":  "安勤科技",    "2359.TW":  "所羅門",
    "2458.TW":  "義隆電子",    "6756.TW":  "威鋒電子",    "2206.TW":  "三陽工業",
    "3707.TWO": "漢磊科技",    "2881.TW":  "富邦金控",    "6245.TW":  "立端科技",
    "3231.TW":  "緯創資通",    "6148.TWO": "長興材料",    "3289.TWO": "聯陽半導體",
    "2351.TW":  "順德工業",    "2363.TW":  "矽統科技",    "3714.TW":  "富采投控",
    "3596.TW":  "智易科技",    "5443.TWO": "均豪精密",    "8112.TW":  "至上電子",
    "3702.TW":  "大聯大控股",  "1785.TWO": "光洋科技",    "3105.TW":  "穩懋半導體",
    "3037.TW":  "欣興電子",    "2382.TW":  "廣達電腦",    "3234.TWO": "光環新網",
}

DEFAULT_TICKERS = list(COMPANY_NAMES.keys())


class SentinelEngine:
    def __init__(self):
        self.session = cffi_requests.Session(impersonate="chrome")

    def get_display_name(self, ticker: str) -> str:
        return COMPANY_NAMES.get(ticker.upper(), ticker)

    # ── Indicator Engine ─────────────────────────────────────────────────────
    def calculate_indicators(self, df: pd.DataFrame, vol_period: int = 20) -> pd.DataFrame:
        """計算所有技術指標：CCI / EMA / ATR / 量能"""
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).upper() for c in df.columns]

        # CCI(39) 手動計算，與亞洲圖表平台一致
        tp = (df['HIGH'] + df['LOW'] + df['CLOSE']) / 3
        tp_sma = tp.rolling(window=39).mean()
        tp_mad = tp.rolling(window=39).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        df['CCI_39'] = (tp - tp_sma) / (0.015 * tp_mad)

        # EMA(10) 趨勢線
        df['EMA_10'] = df['CLOSE'].ewm(span=10, adjust=False).mean()

        # ATR(14) 動態止損
        hl  = df['HIGH'] - df['LOW']
        hcp = np.abs(df['HIGH'] - df['CLOSE'].shift())
        lcp = np.abs(df['LOW']  - df['CLOSE'].shift())
        tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        df['ATR_14']      = tr.rolling(window=14).mean()
        df['SUGGESTED_SL'] = df['CLOSE'] - (df['ATR_14'] * 1.5)

        # ── 量價指標 ──────────────────────────────────────────────────────
        df['VOL_MA']    = df['VOLUME'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = (df['VOLUME'] / df['VOL_MA']).round(2)

        price_chg = df['CLOSE'].pct_change()
        vol_chg   = df['VOLUME'].pct_change()
        THRESHOLD = 0.08  # 量變超過 8% 視為顯著

        df['PV_TAG'] = np.select(
            [
                (price_chg >  0) & (vol_chg >  THRESHOLD),   # 價漲量增 ✅
                (price_chg >  0) & (vol_chg < -THRESHOLD),   # 價漲量縮 ⚠️
                (price_chg <  0) & (vol_chg > THRESHOLD),    # 價跌量增 ❌
                (price_chg <  0) & (vol_chg < -THRESHOLD),   # 價跌量縮 🔵
            ],
            ["🟢 價漲量增", "⚠️ 價漲量縮", "🔴 價跌量增", "🔵 價跌量縮"],
            default="⚪ 量平"
        )
        return df

    # ── Data Fetcher ─────────────────────────────────────────────────────────
    def fetch_data(self, ticker: str, period: str, vol_period: int = 20) -> pd.DataFrame | None:
        try:
            df = yf.download(
                ticker, period=period, interval="1d",
                session=self.session, auto_adjust=True, progress=False
            )
            if df is None or df.empty or len(df) < 50:
                if ".TW" in ticker and not ticker.endswith(".TWO"):
                    return self.fetch_data(ticker.replace(".TW", ".TWO"), period, vol_period)
                return None
            return self.calculate_indicators(df, vol_period)
        except Exception:
            return None

    # ── Signal Evaluator ─────────────────────────────────────────────────────
    def evaluate_signal(
        self, df: pd.DataFrame,
        vol_min_ratio: float = 0.8,
        require_vol: bool = False,
        pv_mode: str = "全部顯示"
    ) -> tuple[str, str, float, str]:
        curr, prev = df.iloc[-1], df.iloc[-2]
        cci       = curr['CCI_39']
        p_cci     = prev['CCI_39']
        vol_ratio = curr['VOL_RATIO']
        pv_tag    = curr['PV_TAG']

        # 基本 CCI 訊號
        if   cci < -100 and cci > p_cci:  base = "BUY"
        elif cci >  100 and cci < p_cci:  base = "SELL"
        else:                              base = "NEUTRAL"

        vol_ok = (vol_ratio >= vol_min_ratio) if require_vol else True

        # 量價過濾
        pv_filter_pass = True
        if pv_mode == "僅量增確認":
            pv_filter_pass = vol_ratio >= vol_min_ratio
        elif pv_mode == "排除量縮":
            pv_filter_pass = "量縮" not in pv_tag

        if base == "BUY":
            if vol_ok and pv_filter_pass: status = "🟢 買進 (上鉤)"
            else:                         status = "🔶 觀察 (買訊/量不足)"
        elif base == "SELL":
            if vol_ok and pv_filter_pass: status = "🔴 賣出 (反轉)"
            else:                         status = "🔶 觀察 (賣訊/量不足)"
        else:
            status = "⚖️ 中性"

        return status, base, float(vol_ratio), str(pv_tag)

    # ── Chart ─────────────────────────────────────────────────────────────────
    def plot_dashboard(self, ticker: str, df: pd.DataFrame, show_volume: bool = True):
        """三面板（含量能）或雙面板技術圖"""
        rows        = 3 if show_volume else 2
        row_heights = [0.55, 0.20, 0.25] if show_volume else [0.60, 0.40]
        cci_row     = 3 if show_volume else 2

        fig = make_subplots(
            rows=rows, cols=1, shared_xaxes=True,
            vertical_spacing=0.04, row_heights=row_heights,
            subplot_titles=("K線 / EMA10 / 止損", "成交量 / 均量" if show_volume else "", "CCI (39)")
        )

        # ── 上圖：K線 ──────────────────────────────────────────────────
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['OPEN'], high=df['HIGH'],
            low=df['LOW'], close=df['CLOSE'], name="K線",
            increasing_line_color='#ff4444', decreasing_line_color='#26a69a'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index, y=df['EMA_10'],
            line=dict(color='#00d4ff', width=1.5), name="EMA10"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index, y=df['SUGGESTED_SL'],
            line=dict(color='rgba(255,82,82,0.7)', width=1.5, dash='dash'),
            name="止損線"
        ), row=1, col=1)

        # ── 中圖：量能 ─────────────────────────────────────────────────
        if show_volume:
            bar_colors = [
                '#ff4444' if c >= o else '#26a69a'
                for c, o in zip(df['CLOSE'], df['OPEN'])
            ]
            fig.add_trace(go.Bar(
                x=df.index, y=df['VOLUME'], name="成交量",
                marker_color=bar_colors, opacity=0.65
            ), row=2, col=1)

            fig.add_trace(go.Scatter(
                x=df.index, y=df['VOL_MA'],
                line=dict(color='#ffcc00', width=1.2, dash='dot'), name="均量"
            ), row=2, col=1)

        # ── 下圖：CCI ──────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=df.index, y=df['CCI_39'],
            line=dict(color='#ff9900', width=2), name="CCI(39)"
        ), row=cci_row, col=1)

        fig.add_hline(y= 100, line_dash="dot", line_color="rgba(255,0,0,0.35)",   row=cci_row, col=1)
        fig.add_hline(y=-100, line_dash="dot", line_color="rgba(38,166,154,0.35)", row=cci_row, col=1)
        fig.add_hline(y=   0, line_color="rgba(255,255,255,0.08)",                 row=cci_row, col=1)

        # Colour bands
        fig.add_hrect(y0=100, y1=300, fillcolor="rgba(255,0,0,0.04)",
                      line_width=0, row=cci_row, col=1)
        fig.add_hrect(y0=-300, y1=-100, fillcolor="rgba(38,166,154,0.04)",
                      line_width=0, row=cci_row, col=1)

        fig.update_layout(
            height=560, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(t=30, b=10, l=60, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Main Entry Point ──────────────────────────────────────────────────────
    def run(self):
        st.set_page_config(page_title="哨兵 Sentinel Pro", layout="wide", page_icon="🛡️")
        st.title("🛡️ 哨兵 Sentinel Pro：策略分析引擎")

        # Sidebar – shared across tabs
        self._render_sidebar()

        tab1, tab2 = st.tabs(["📡 掃描器", "📋 交易紀錄 & 損益"])
        with tab1:
            self._render_scanner_tab()
        with tab2:
            self._render_journal_tab()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _render_sidebar(self):
        st.sidebar.header("⚙️ 掃描設定")

        ticker_raw = st.sidebar.text_area(
            "📌 自選股清單（每行一檔）",
            value="\n".join(DEFAULT_TICKERS), height=160
        )
        st.session_state["tickers"] = [
            t.strip().upper() for t in ticker_raw.splitlines() if t.strip()
        ]

        st.session_state["time_period"] = st.sidebar.selectbox(
            "📅 資料區間",
            options=["3mo", "6mo", "1y", "2y", "5y"],
            index=2,
        )

        st.sidebar.divider()
        st.sidebar.subheader("📊 量價控制")

        st.session_state["vol_period"] = st.sidebar.slider(
            "均量週期（日）", 5, 60, 20, 5,
            help="計算量比的基準均量天數"
        )
        st.session_state["require_vol"] = st.sidebar.toggle(
            "啟用量能確認", value=False,
            help="開啟後，買賣訊號須量比達標才視為有效"
        )
        vol_disabled = not st.session_state.get("require_vol", False)
        st.session_state["vol_min_ratio"] = st.sidebar.slider(
            "最低量比閾值", 0.3, 3.0, 0.8, 0.1,
            help="今日量 ÷ 均量，低於此值標記為量不足",
            disabled=vol_disabled
        )
        st.session_state["pv_mode"] = st.sidebar.selectbox(
            "量價過濾模式",
            options=["全部顯示", "僅量增確認", "排除量縮"],
            index=0,
            help="控制量價訊號的嚴格程度"
        )
        st.session_state["show_volume"] = st.sidebar.toggle("顯示成交量子圖", value=True)

        st.sidebar.divider()
        st.session_state["signal_filter"] = st.sidebar.multiselect(
            "顯示訊號類型",
            options=["買進", "賣出", "觀察", "中性"],
            default=["買進", "賣出", "觀察"],
        )

    # ── Scanner Tab ───────────────────────────────────────────────────────────
    def _render_scanner_tab(self):
        with st.expander("📝 策略說明", expanded=False):
            st.markdown("""
            | 參數 | 說明 |
            |---|---|
            | **CCI(39)** | 商品通道指數，39日週期，符合亞洲主流圖表平台 |
            | **買進訊號** | CCI < −100（超賣）且今日值 > 昨日值（上鉤反彈）|
            | **賣出訊號** | CCI > +100（超買）且今日值 < 昨日值（反轉下跌）|
            | **止損線** | 當前收盤價 − 1.5 × ATR(14) |
            | **量比** | 今日成交量 ÷ N日均量；> 1 代表放量，< 1 代表縮量 |
            | **量價背離** | 價漲量縮 / 價跌量增，可能預示趨勢轉弱 |
            """)

        tickers      = st.session_state.get("tickers", DEFAULT_TICKERS)
        time_period  = st.session_state.get("time_period", "1y")
        vol_period   = st.session_state.get("vol_period", 20)
        require_vol  = st.session_state.get("require_vol", False)
        vol_min      = st.session_state.get("vol_min_ratio", 0.8)
        pv_mode      = st.session_state.get("pv_mode", "全部顯示")
        show_vol     = st.session_state.get("show_volume", True)
        sig_filter   = st.session_state.get("signal_filter", ["買進", "賣出", "觀察"])

        if st.button("🚀 執行掃描", type="primary", use_container_width=True):
            results = []
            bar = st.progress(0, text="⏳ 初始化...")
            for idx, t in enumerate(tickers):
                bar.progress((idx + 1) / len(tickers), text=f"⏳ 分析中：{t}  {self.get_display_name(t)}")
                df = self.fetch_data(t, time_period, vol_period)
                if df is not None:
                    status, base, vol_ratio, pv_tag = self.evaluate_signal(df, vol_min, require_vol, pv_mode)
                    curr, prev = df.iloc[-1], df.iloc[-2]
                    results.append({
                        "ticker":    t,
                        "name":      self.get_display_name(t),
                        "df":        df,
                        "status":    status,
                        "base":      base,
                        "price":     float(curr['CLOSE']),
                        "sl":        float(curr['SUGGESTED_SL']),
                        "cci":       float(curr['CCI_39']),
                        "cci_delta": float(curr['CCI_39'] - prev['CCI_39']),
                        "vol_ratio": vol_ratio,
                        "pv_tag":    pv_tag,
                        "volume":    int(curr['VOLUME']),
                    })
                time.sleep(0.04)
            bar.empty()
            st.session_state["results"] = results

        # ── 結果 ───────────────────────────────────────────────────────
        if "results" not in st.session_state:
            return

        results = st.session_state["results"]

        # Summary metrics
        buy_n   = sum(1 for r in results if "買進" in r['status'])
        sell_n  = sum(1 for r in results if "賣出" in r['status'])
        watch_n = sum(1 for r in results if "觀察" in r['status'])

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("📋 掃描總數",  len(results))
        mc2.metric("🟢 買進訊號",  buy_n)
        mc3.metric("🔴 賣出訊號",  sell_n)
        mc4.metric("🔶 觀察訊號",  watch_n)

        st.divider()

        def sig_cat(s):
            if "買進" in s: return "買進"
            if "賣出" in s: return "賣出"
            if "觀察" in s: return "觀察"
            return "中性"

        filtered = [r for r in results if sig_cat(r['status']) in sig_filter] if sig_filter else results

        for res in filtered:
            with st.container(border=True):
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.2, 1.2, 1.6, 1, 1, 1, 1.2, 0.9])

                c1.subheader(res['ticker'])
                c1.caption(res['name'])

                c2.metric("現價 (元)", f"{res['price']:.2f}")

                c3.markdown(f"**{res['status']}**")
                c3.caption(res['pv_tag'])

                c4.metric("CCI(39)", f"{res['cci']:.1f}", delta=f"{res['cci_delta']:+.1f}")
                c5.metric("止損價",  f"{res['sl']:.2f}", delta_color="inverse")

                # Volume ratio bar
                ratio = res['vol_ratio']
                ratio_color = "🔴" if ratio < 0.5 else "🟡" if ratio < 1.0 else "🟢"
                c6.metric("量比", f"{ratio_color} {ratio:.2f}×")

                c7.caption(f"成交量\n{res['volume']:,}")

                # Add trade button → prefills journal form
                if c8.button("➕ 記錄", key=f"btn_{res['ticker']}",
                             help="快速記錄此股交易", use_container_width=True):
                    st.session_state["quick_add"]   = res['ticker']
                    st.session_state["quick_name"]  = res['name']
                    st.session_state["quick_price"] = res['price']
                    st.session_state["quick_dir"]   = "買進 🟢" if res['base'] == "BUY" else "賣出 🔴"
                    st.toast(f"✅ 已預填 {res['name']}，請切換至【交易紀錄】標籤完成記錄", icon="📋")

                self.plot_dashboard(res['ticker'], res['df'], show_volume=show_vol)

    # ── Journal Tab ──────────────────────────────────────────────────────────
    def _render_journal_tab(self):
        st.header("📋 交易紀錄 & 損益分析")

        # Initialise journal
        if "journal" not in st.session_state:
            st.session_state["journal"] = pd.DataFrame(columns=[
                "代號", "名稱", "方向", "日期", "成交價", "股數", "手續費", "備註"
            ])

        # ── I/O Row ───────────────────────────────────────────────────────
        io1, io2 = st.columns(2)

        with io1:
            uploaded = st.file_uploader("📂 載入紀錄 (Excel .xlsx)", type=["xlsx"])
            if uploaded:
                try:
                    loaded = pd.read_excel(uploaded, sheet_name="交易紀錄")
                    # coerce types
                    for col in ["成交價", "手續費"]:
                        if col in loaded.columns:
                            loaded[col] = pd.to_numeric(loaded[col], errors="coerce").fillna(0)
                    for col in ["股數"]:
                        if col in loaded.columns:
                            loaded[col] = pd.to_numeric(loaded[col], errors="coerce").fillna(0).astype(int)
                    st.session_state["journal"] = loaded
                    st.success(f"✅ 成功載入 {len(loaded)} 筆交易紀錄")
                except Exception as e:
                    st.error(f"❌ 載入失敗：{e}")

        with io2:
            st.write("")
            st.write("")
            if st.button("💾 匯出 Excel", type="primary", use_container_width=True):
                data = self._export_to_excel(st.session_state["journal"])
                fname = f"哨兵交易紀錄_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.download_button(
                    "⬇️ 下載 Excel",
                    data=data, file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        st.divider()

        # ── Add Trade Form ─────────────────────────────────────────────
        quick_ticker = st.session_state.get("quick_add", "")
        expanded     = bool(quick_ticker)

        with st.expander("➕ 新增交易記錄", expanded=expanded):
            f1, f2, f3 = st.columns(3)

            with f1:
                t_ticker = st.text_input(
                    "股票代號", value=quick_ticker,
                    placeholder="例：2330.TW"
                ).upper()
                t_name = st.text_input(
                    "名稱",
                    value=st.session_state.get("quick_name", COMPANY_NAMES.get(quick_ticker, ""))
                )

            with f2:
                direction_opts = ["買進 🟢", "賣出 🔴"]
                pref_dir = st.session_state.get("quick_dir", "買進 🟢")
                pref_idx = direction_opts.index(pref_dir) if pref_dir in direction_opts else 0
                t_dir    = st.selectbox("方向", direction_opts, index=pref_idx)
                t_date   = st.date_input("日期", value=date.today())

            with f3:
                t_price  = st.number_input(
                    "成交價格 (元)", min_value=0.0,
                    value=float(st.session_state.get("quick_price", 0.0)),
                    step=0.01, format="%.2f"
                )
                t_shares = st.number_input(
                    "股數（1張=1000股）", min_value=0, value=1000, step=1000
                )

            f4, f5 = st.columns(2)
            with f4:
                t_comm = st.number_input("手續費 (元)", min_value=0.0, value=0.0, step=1.0)
            with f5:
                t_note = st.text_input("備註", placeholder="例：CCI上鉤訊號、法說前佈局")

            if st.button("✅ 確認新增", type="primary"):
                if t_ticker and t_price > 0 and t_shares > 0:
                    row = pd.DataFrame([{
                        "代號":  t_ticker,
                        "名稱":  t_name or self.get_display_name(t_ticker),
                        "方向":  t_dir.split(" ")[0],
                        "日期":  t_date.strftime("%Y-%m-%d"),
                        "成交價": t_price,
                        "股數":   t_shares,
                        "手續費": t_comm,
                        "備註":   t_note,
                    }])
                    st.session_state["journal"] = pd.concat(
                        [st.session_state["journal"], row], ignore_index=True
                    )
                    # Clear quick-add prefill
                    for k in ["quick_add", "quick_name", "quick_price", "quick_dir"]:
                        st.session_state.pop(k, None)
                    st.success(f"✅ 已新增：{t_ticker} {t_name}")
                    st.rerun()
                else:
                    st.error("⚠️ 請填寫代號、價格及股數")

        # ── P&L Summary ───────────────────────────────────────────────
        journal = st.session_state["journal"]

        if journal.empty:
            st.info("📭 尚無交易紀錄。點選掃描器中的「➕ 記錄」或手動新增。")
            return

        st.subheader("📊 損益概覽")
        summary = self._pnl_summary(journal)

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("已實現損益",   f"NT$ {summary['realized']:+,.0f}",
                  delta=f"{summary['realized']:+,.0f}")
        s2.metric("持倉帳面成本", f"NT$ {summary['open_cost']:,.0f}")
        s3.metric("持倉股數",     f"{summary['open_shares']:,} 股")
        s4.metric("總交易筆數",   str(len(journal)))
        s5.metric("持股標的數",   str(len(journal['代號'].unique())))

        st.divider()

        # ── Per-ticker P&L ────────────────────────────────────────────
        st.subheader("📈 各股損益明細")
        pnl_df = self._pnl_by_ticker(journal)
        if pnl_df is not None:
            def color_pnl(val):
                if isinstance(val, str) and "NT$" in val:
                    num = float(val.replace("NT$", "").replace(",", "").replace("+", "").strip())
                    if num > 0:   return "color: #26a69a"
                    if num < 0:   return "color: #ff4444"
                return ""
            st.dataframe(
                pnl_df.style.applymap(color_pnl, subset=["已實現損益"]),
                use_container_width=True
            )

        st.divider()

        # ── Editable Full Log ─────────────────────────────────────────
        st.subheader("📋 交易明細（可直接編輯/刪除）")
        edited = st.data_editor(
            journal,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "方向":  st.column_config.SelectboxColumn("方向", options=["買進", "賣出"]),
                "日期":  st.column_config.TextColumn("日期"),
                "成交價": st.column_config.NumberColumn("成交價", format="%.2f"),
                "股數":   st.column_config.NumberColumn("股數",   format="%d"),
                "手續費": st.column_config.NumberColumn("手續費", format="%.0f"),
            }
        )
        st.session_state["journal"] = edited

    # ── P&L Helpers ──────────────────────────────────────────────────────────
    def _pnl_summary(self, journal: pd.DataFrame) -> dict:
        realized, open_cost, open_shares = 0.0, 0.0, 0
        for _, r in journal.iterrows():
            p   = float(r.get("成交價", 0) or 0)
            n   = int(r.get("股數",   0) or 0)
            fee = float(r.get("手續費", 0) or 0)
            d   = str(r.get("方向",   ""))
            if "買" in d:
                open_cost   += p * n + fee
                open_shares += n
            elif "賣" in d:
                realized    += p * n - fee
                open_shares -= n
        return {"realized": realized, "open_cost": open_cost, "open_shares": max(open_shares, 0)}

    def _pnl_by_ticker(self, journal: pd.DataFrame) -> pd.DataFrame | None:
        if journal.empty:
            return None
        rows = []
        for ticker in journal['代號'].unique():
            sub  = journal[journal['代號'] == ticker].copy()
            name = sub['名稱'].iloc[0] if '名稱' in sub.columns else ""

            for col in ["成交價", "手續費"]:
                sub[col] = pd.to_numeric(sub.get(col, 0), errors="coerce").fillna(0)
            sub["股數"] = pd.to_numeric(sub.get("股數", 0), errors="coerce").fillna(0).astype(int)

            buys  = sub[sub['方向'].str.contains("買", na=False)]
            sells = sub[sub['方向'].str.contains("賣", na=False)]

            buy_cost  = (buys['成交價'] * buys['股數']).sum()  + buys['手續費'].sum()
            sell_inc  = (sells['成交價'] * sells['股數']).sum() - sells['手續費'].sum()
            buy_n     = buys['股數'].sum()
            sell_n    = sells['股數'].sum()
            open_n    = int(buy_n - sell_n)
            avg_cost  = buy_cost / buy_n if buy_n > 0 else 0
            realized  = sell_inc - avg_cost * sell_n if sell_n > 0 else 0

            rows.append({
                "代號":     ticker,
                "名稱":     name,
                "均攤成本": f"{avg_cost:.2f}",
                "買進成本": f"NT$ {buy_cost:,.0f}",
                "賣出收入": f"NT$ {sell_inc:,.0f}",
                "已實現損益": f"NT$ {realized:+,.0f}",
                "持倉股數": open_n if open_n > 0 else 0,
                "交易筆數": len(sub),
            })
        return pd.DataFrame(rows)

    # ── Excel Export ──────────────────────────────────────────────────────────
    def _export_to_excel(self, journal: pd.DataFrame) -> bytes:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

            # Sheet 1 – 交易紀錄
            journal.to_excel(writer, sheet_name="交易紀錄", index=False)

            # Sheet 2 – 損益摘要
            pnl_df = self._pnl_by_ticker(journal)
            if pnl_df is not None:
                pnl_df.to_excel(writer, sheet_name="損益摘要", index=False)

            # Sheet 3 – 說明
            info = pd.DataFrame({
                "欄位": ["代號", "名稱", "方向", "日期", "成交價", "股數", "手續費", "備註"],
                "說明": [
                    "Yahoo Finance 代碼（如 2330.TW）",
                    "公司中文名稱",
                    "買進 / 賣出",
                    "交易日期 YYYY-MM-DD",
                    "每股成交價格（元）",
                    "股數（1張＝1000股）",
                    "券商手續費（元）",
                    "自訂備註",
                ]
            })
            info.to_excel(writer, sheet_name="欄位說明", index=False)

            # Auto-fit column widths
            for ws in writer.sheets.values():
                for col in ws.columns:
                    max_w = max((len(str(cell.value or "")) for cell in col), default=8)
                    ws.column_dimensions[col[0].column_letter].width = min(max_w + 3, 35)

        buffer.seek(0)
        return buffer.getvalue()


if __name__ == "__main__":
    SentinelEngine().run()
