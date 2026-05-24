import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
from glob import glob
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="SOPX Chain Scorer Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling (High-Contrast Premium Dark Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+TC:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Noto Sans TC', sans-serif;
        background-color: #0b0f19;
        color: #f9fafb; /* High contrast body text */
    }
    
    /* Top Brand border representing decisions */
    .stApp::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 3px;
        background: linear-gradient(90deg, #10b981, #38bdf8, #fbbf24, #f43f5e);
        z-index: 9999;
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff, #e2e8f0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    
    .subtitle {
        font-size: 1rem;
        color: #cbd5e1; /* Brighter subtitle */
        margin-bottom: 2.2rem;
    }
    
    /* High contrast premium card design */
    .metric-card {
        background: rgba(17, 24, 39, 0.75); /* Elevated Gray-900 panel */
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.08); /* More visible border */
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
        transition: all 0.3s ease;
        margin-bottom: 1rem;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.18);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1.1;
        margin-top: 0.4rem;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #cbd5e1; /* Brighter label */
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #070a13 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }
    
    /* Custom tab headers */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(17, 24, 39, 0.5);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        color: #9ca3af; /* High contrast unselected tab */
        font-weight: 600;
        transition: all 0.2s ease;
        border: none;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #ffffff !important; /* Pure white active tab text */
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Data Loading -----------------
@st.cache_data
def load_history_data():
    csv_path = "reports/history.csv"
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    df["date_utc"] = pd.to_datetime(df["date_utc"])
    return df

@st.cache_data
def load_latest_tags():
    json_files = glob("reports/report_*.json")
    if not json_files:
        return {}
    latest_file = max(json_files, key=os.path.getmtime)
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {item["id"]: item.get("tags", []) for item in data}
    except Exception:
        return {}

df_hist = load_history_data()
tags_map = load_latest_tags()

# Helper function to get tag value
def get_tag_value(tags, prefix):
    if not tags:
        return None
    for t in tags:
        if isinstance(t, str) and t.startswith(prefix):
            return t.split(":", 1)[1].strip()
    return None

# Compute action labels
def compute_action_label(row):
    tags = tags_map.get(row["id"], [])
    c = float(row.get("constitutional") or 0)
    risk = float(row.get("risk") or 0)
    layer = get_tag_value(tags, "layer:")
    thesis = get_tag_value(tags, "thesis:")
    
    if risk >= 40:
        return "AVOID"
    if c >= 85 or layer == "civilization":
        return "HOLD"
    if (c >= 55 and thesis != "narrative") or layer == "regional":
        return "ROTATE"
    return "TRADE"

if df_hist.empty:
    st.error("⚠️ 找不到 `reports/history.csv`，請先執行評分程序以產生數據。")
else:
    # Add Action & Tags columns to df_hist
    df_hist["tags"] = df_hist["id"].map(lambda x: tags_map.get(x, []))
    df_hist["action"] = df_hist.apply(compute_action_label, axis=1)
    
    latest_date = df_hist["date_utc"].max()
    df_latest = df_hist[df_hist["date_utc"] == latest_date]
    
    # ----------------- Sidebar -----------------
    st.sidebar.markdown("<h2 style='font-weight: 700; color: #fff;'>⚙️ 篩選控制項</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<hr style='border: 1px solid rgba(255,255,255,0.05); margin-top: 0.5rem; margin-bottom: 1.5rem;'/>", unsafe_allow_html=True)
    
    # Lookback Filter
    dates = sorted(df_hist["date_utc"].unique())
    num_weeks = len(dates)
    lookback = st.sidebar.slider("歷史回看週數", min_value=2, max_value=max(12, num_weeks), value=min(7, num_weeks))
    
    # Filter dates
    active_dates = dates[-lookback:]
    df_filtered = df_hist[df_hist["date_utc"].isin(active_dates)]
    
    # Search/Filter Tokens
    all_tokens = sorted(df_latest["symbol"].str.upper().unique())
    default_tokens = df_latest.sort_values(by="total", ascending=False)["symbol"].head(5).str.upper().tolist()
    
    st.sidebar.markdown("<p style='font-size: 0.9rem; font-weight: 600; color: #94a3b8; margin-bottom: 0.3rem;'>🔍 對比代幣代號</p>", unsafe_allow_html=True)
    selected_tokens = st.sidebar.multiselect("選擇對比代幣", options=all_tokens, default=default_tokens, label_visibility="collapsed")
    
    st.sidebar.markdown("<p style='font-size: 0.9rem; font-weight: 600; color: #94a3b8; margin-bottom: 0.3rem; margin-top: 1rem;'>⚖️ 篩選投資決策</p>", unsafe_allow_html=True)
    actions_filter = st.sidebar.multiselect("篩選決策類型", options=["HOLD", "ROTATE", "TRADE", "AVOID"], default=["HOLD", "ROTATE", "TRADE"], label_visibility="collapsed")

    # ----------------- Main Interface -----------------
    st.markdown('<div class="main-title">SOPX Chain Scorer 視覺化儀表板</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">每週加密貨幣量化評分與制度分析趨勢看板（最新更新：{latest_date.strftime("%Y-%m-%d")} UTC）</div>', unsafe_allow_html=True)
    
    # High-level metrics (High Contrast & Salience SaaS Theme)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #34d399;">🧱 長期核心 (HOLD)</div>
            <div class="metric-value" style="color: #34d399;">{(df_latest["action"] == "HOLD").sum()} <span style="font-size: 1rem; font-weight: 400; color: #d1d5db;">項</span></div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #38bdf8;">🏗 成長配置 (ROTATE)</div>
            <div class="metric-value" style="color: #38bdf8;">{(df_latest["action"] == "ROTATE").sum()} <span style="font-size: 1rem; font-weight: 400; color: #d1d5db;">項</span></div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #fbbf24;">🎭 高波動交易 (TRADE)</div>
            <div class="metric-value" style="color: #fbbf24;">{(df_latest["action"] == "TRADE").sum()} <span style="font-size: 1rem; font-weight: 400; color: #d1d5db;">項</span></div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #f43f5e;">⛔ 結構風險 (AVOID)</div>
            <div class="metric-value" style="color: #f43f5e;">{(df_latest["action"] == "AVOID").sum()} <span style="font-size: 1rem; font-weight: 400; color: #d1d5db;">項</span></div>
        </div>
        """, unsafe_allow_html=True)
        
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 最新評分大盤", "📈 歷史趨勢追蹤", "⚖️ 核心維度對比", "📉 分數分佈分析"])
    
    # Tab 1: Latest Standings
    with tab1:
        st.markdown("<h3 style='font-weight: 700; color: #fff; margin-bottom: 1rem;'>🏆 本週 Top 100 評分大盤</h3>", unsafe_allow_html=True)
        
        # Filtering latest dataframe
        df_latest_show = df_latest.copy()
        if actions_filter:
            df_latest_show = df_latest_show[df_latest_show["action"].isin(actions_filter)]
            
        search_query = st.text_input("🔍 搜尋項目名稱或代幣符號：", placeholder="請輸入例如 eth, btc...")
        if search_query:
            df_latest_show = df_latest_show[
                df_latest_show["name"].str.contains(search_query, case=False) |
                df_latest_show["symbol"].str.contains(search_query, case=False)
            ]
            
        # Format columns for display
        df_latest_show = df_latest_show.sort_values(by="total", ascending=False)
        display_cols = ["rank", "symbol", "name", "total", "constitutional", "demand", "capture", "risk", "action", "vol_to_mcap"]
        
        # High-contrast cell styling function for DataFrame
        def style_columns(row):
            styles = pd.Series("", index=row.index)
            # Action styling (SaaS Bright Glow Badges)
            action_map = {
                "HOLD": "background-color: rgba(16, 185, 129, 0.15); color: #34d399; font-weight: bold; border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px;",
                "ROTATE": "background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; font-weight: bold; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 6px;",
                "TRADE": "background-color: rgba(251, 191, 36, 0.15); color: #fbbf24; font-weight: bold; border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 6px;",
                "AVOID": "background-color: rgba(244, 63, 94, 0.15); color: #f43f5e; font-weight: bold; border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 6px;"
            }
            styles["action"] = action_map.get(row["action"], "")
            
            # Highlight Total Score
            if row["action"] == "AVOID":
                styles["total"] = "color: #f43f5e; font-weight: bold; font-size: 1.05rem;"
            else:
                styles["total"] = "color: #ffffff; font-weight: bold; font-size: 1.05rem;"
                
            # Highlight high risk values
            if float(row["risk"]) >= 40:
                styles["risk"] = "color: #f43f5e; font-weight: bold;"
            elif float(row["risk"]) > 0:
                styles["risk"] = "color: #fca5a5; font-weight: 500;"
                
            # Brighter defaults for regular columns to avoid low contrast
            for col in ["rank", "symbol", "name", "constitutional", "demand", "capture", "vol_to_mcap"]:
                styles[col] = "color: #e5e7eb;"
                
            return styles

        st.dataframe(
            df_latest_show[display_cols].style.apply(style_columns, axis=1),
            column_config={
                "rank": st.column_config.NumberColumn("市值排名", format="%d"),
                "symbol": st.column_config.TextColumn("代幣符號"),
                "name": st.column_config.TextColumn("項目名稱"),
                "total": st.column_config.NumberColumn("SOPX 總分", format="%.1f"),
                "constitutional": st.column_config.NumberColumn("🧱 制度分", format="%d"),
                "demand": st.column_config.NumberColumn("🏗 需求分", format="%d"),
                "capture": st.column_config.NumberColumn("🎭 捕獲分", format="%d"),
                "risk": st.column_config.NumberColumn("⛔ 風險扣分", format="%d"),
                "action": st.column_config.TextColumn("投資決策"),
                "vol_to_mcap": st.column_config.NumberColumn("Vol/Mcap", format="%.3f")
            },
            hide_index=True,
            use_container_width=True,
            height=500
        )
        
    # Tab 2: Historical Trends
    with tab2:
        st.markdown("<h3 style='font-weight: 700; color: #fff; margin-bottom: 1rem;'>📈 歷史評分趨勢對比</h3>", unsafe_allow_html=True)
        if not selected_tokens:
            st.warning("請在側邊欄選擇至少一個 Token 來查看趨勢。")
        else:
            df_trend = df_filtered[df_filtered["symbol"].str.upper().isin(selected_tokens)].copy()
            df_trend = df_trend.sort_values(by="date_utc")
            df_trend["date_str"] = df_trend["date_utc"].dt.strftime("%Y-%m-%d")
            
            dimension = st.selectbox("選擇要檢視的指標", options=["SOPX 總分 (Total)", "🧱 制度分 (Constitutional)", "🏗 需求分 (Demand)", "🎭 捕獲分 (Capture)", "⛔ 風險分 (Risk)"])
            dim_map = {
                "SOPX 總分 (Total)": "total",
                "🧱 制度分 (Constitutional)": "constitutional",
                "🏗 需求分 (Demand)": "demand",
                "🎭 捕獲分 (Capture)": "capture",
                "⛔ 風險分 (Risk)": "risk"
            }
            target_col = dim_map[dimension]
            
            # Custom high-contrast color sequence for lines
            fig = px.line(
                df_trend,
                x="date_str",
                y=target_col,
                color="symbol",
                markers=True,
                line_shape="spline",
                color_discrete_sequence=["#38bdf8", "#34d399", "#fbbf24", "#f43f5e", "#a78bfa", "#fb923c", "#2dd4bf", "#f472b6"],
                labels={"date_str": "日期 (UTC)", target_col: "分數", "symbol": "代幣"},
                template="plotly_dark"
            )
            fig.update_traces(line=dict(width=3.0)) # Thicker lines for readability
            fig.update_layout(
                hovermode="x unified",
                xaxis={"tickangle": -45, "showgrid": True, "gridcolor": "rgba(255,255,255,0.08)"},
                yaxis={"showgrid": True, "gridcolor": "rgba(255,255,255,0.08)"},
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=30, b=20),
                font=dict(family="Outfit, Noto Sans TC, sans-serif", size=12)
            )
            st.plotly_chart(fig, use_container_width=True)
            
    # Tab 3: Dimensional Comparison
    with tab3:
        st.markdown("<h3 style='font-weight: 700; color: #fff; margin-bottom: 1rem;'>⚖️ 多維度分佈與交叉對比</h3>", unsafe_allow_html=True)
        
        col_x = st.selectbox("橫軸 (X 軸)", options=["🧱 制度分 (Constitutional)", "🏗 需求分 (Demand)", "🎭 捕獲分 (Capture)", "⛔ 風險分 (Risk)"], index=0)
        col_y = st.selectbox("縱軸 (Y 軸)", options=["🧱 制度分 (Constitutional)", "🏗 需求分 (Demand)", "🎭 捕獲分 (Capture)", "⛔ 風險分 (Risk)"], index=1)
        
        dim_map_xy = {
            "🧱 制度分 (Constitutional)": "constitutional",
            "🏗 需求分 (Demand)": "demand",
            "🎭 捕獲分 (Capture)": "capture",
            "⛔ 風險分 (Risk)": "risk"
        }
        
        x_col = dim_map_xy[col_x]
        y_col = dim_map_xy[col_y]
        
        fig = px.scatter(
            df_latest,
            x=x_col,
            y=y_col,
            color="action",
            size="market_cap",
            hover_name="name",
            hover_data=["symbol", "total", "rank"],
            color_discrete_map={
                "HOLD": "#34d399",
                "ROTATE": "#38bdf8",
                "TRADE": "#fbbf24",
                "AVOID": "#f43f5e"
            },
            labels={x_col: col_x, y_col: col_y, "action": "投資決策"},
            template="plotly_dark"
        )
        fig.update_traces(marker=dict(line=dict(width=1.2, color='rgba(255,255,255,0.25)'), opacity=0.9))
        fig.update_layout(
            xaxis={"showgrid": True, "gridcolor": "rgba(255,255,255,0.08)"},
            yaxis={"showgrid": True, "gridcolor": "rgba(255,255,255,0.08)"},
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=30, b=20),
            font=dict(family="Outfit, Noto Sans TC, sans-serif", size=12)
        )
        st.plotly_chart(fig, use_container_width=True)
        
    # Tab 4: Score Distribution
    with tab4:
        st.markdown("<h3 style='font-weight: 700; color: #fff; margin-bottom: 1rem;'>📉 評分區間分佈（最新一期）</h3>", unsafe_allow_html=True)
        
        fig = px.histogram(
            df_latest,
            x="total",
            nbins=20,
            color="action",
            color_discrete_map={
                "HOLD": "#34d399",
                "ROTATE": "#38bdf8",
                "TRADE": "#fbbf24",
                "AVOID": "#f43f5e"
            },
            labels={"total": "SOPX 總分", "count": "項目數量", "action": "投資決策"},
            template="plotly_dark"
        )
        fig.update_layout(
            bargap=0.08,
            xaxis={"showgrid": False},
            yaxis={"showgrid": True, "gridcolor": "rgba(255,255,255,0.08)"},
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=30, b=20),
            font=dict(family="Outfit, Noto Sans TC, sans-serif", size=12)
        )
        st.plotly_chart(fig, use_container_width=True)
