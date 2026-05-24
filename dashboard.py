import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import yaml
from glob import glob
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="SOPX Chain Scorer Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FF4B4B, #FF8F8F);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        font-size: 1.1rem;
        color: #88888b;
        margin-bottom: 2rem;
    }
    
    .card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 1rem;
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #ffffff;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #88888b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
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
    st.sidebar.markdown("## ⚙️ 篩選控制項")
    
    # Lookback Filter
    dates = sorted(df_hist["date_utc"].unique())
    num_weeks = len(dates)
    lookback = st.sidebar.slider("歷史回看週數", min_value=2, max_value=max(12, num_weeks), value=min(7, num_weeks))
    
    # Filter dates
    active_dates = dates[-lookback:]
    df_filtered = df_hist[df_hist["date_utc"].isin(active_dates)]
    
    # Search/Filter Tokens
    all_tokens = sorted(df_latest["symbol"].str.upper().unique())
    # Default to top 5 tokens from latest scores
    default_tokens = df_latest.sort_values(by="total", ascending=False)["symbol"].head(5).str.upper().tolist()
    selected_tokens = st.sidebar.multiselect("選擇 Token 進行趨勢對比", options=all_tokens, default=default_tokens)
    
    # Action labels filter
    actions_filter = st.sidebar.multiselect("篩選投資決策 (最新)", options=["HOLD", "ROTATE", "TRADE", "AVOID"], default=["HOLD", "ROTATE", "TRADE"])

    # ----------------- Main Interface -----------------
    st.markdown('<div class="main-title">SOPX Chain Scorer 視覺化儀表板</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">每週加密貨幣量化評分與制度分析趨勢看板（最新更新：{latest_date.strftime("%Y-%m-%d")} UTC）</div>', unsafe_allow_html=True)
    
    # High-level metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="card">
            <div class="metric-label">🧱 長期核心 (HOLD)</div>
            <div class="metric-value">{(df_latest["action"] == "HOLD").sum()} 個項目</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="card">
            <div class="metric-label">🏗 成長配置 (ROTATE)</div>
            <div class="metric-value">{(df_latest["action"] == "ROTATE").sum()} 個項目</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="card">
            <div class="metric-label">🎭 高波動交易 (TRADE)</div>
            <div class="metric-value">{(df_latest["action"] == "TRADE").sum()} 個項目</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="card">
            <div class="metric-label">⛔ 結構風險 (AVOID)</div>
            <div class="metric-value">{(df_latest["action"] == "AVOID").sum()} 個項目</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 最新評分大盤", "📈 歷史趨勢追蹤", "⚖️ 核心維度對比", "📉 分數分佈分析"])
    
    # Tab 1: Latest Standings
    with tab1:
        st.markdown("### 🏆 本週 Top 100 評分大盤")
        
        # Filtering latest dataframe
        df_latest_show = df_latest.copy()
        if actions_filter:
            df_latest_show = df_latest_show[df_latest_show["action"].isin(actions_filter)]
            
        search_query = st.text_input("🔍 搜尋項目名稱或代幣符號：")
        if search_query:
            df_latest_show = df_latest_show[
                df_latest_show["name"].str.contains(search_query, case=False) |
                df_latest_show["symbol"].str.contains(search_query, case=False)
            ]
            
        # Format columns for display
        df_latest_show = df_latest_show.sort_values(by="total", ascending=False)
        display_cols = ["rank", "symbol", "name", "total", "constitutional", "demand", "capture", "risk", "action", "vol_to_mcap"]
        
        # Color styling function
        def style_action(val):
            color_map = {
                "HOLD": "background-color: rgba(46, 204, 113, 0.2); color: #2ecc71; font-weight: bold;",
                "ROTATE": "background-color: rgba(52, 152, 219, 0.2); color: #3498db; font-weight: bold;",
                "TRADE": "background-color: rgba(241, 196, 15, 0.2); color: #f1c40f; font-weight: bold;",
                "AVOID": "background-color: rgba(231, 76, 60, 0.2); color: #e74c3c; font-weight: bold;"
            }
            return color_map.get(val, "")

        st.dataframe(
            df_latest_show[display_cols].style.map(style_action, subset=["action"]),
            column_config={
                "rank": "市值排名",
                "symbol": "代幣符號",
                "name": "項目名稱",
                "total": "SOPX 總分",
                "constitutional": "🧱 制度分",
                "demand": "🏗 需求分",
                "capture": "🎭 捕獲分",
                "risk": "⛔ 風險扣分",
                "action": "投資決策",
                "vol_to_mcap": "Vol/Mcap"
            },
            hide_index=True,
            use_container_width=True
        )
        
    # Tab 2: Historical Trends
    with tab2:
        st.markdown("### 📈 歷史評分趨勢對比")
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
            
            fig = px.line(
                df_trend,
                x="date_str",
                y=target_col,
                color="symbol",
                markers=True,
                title=f"{dimension} 歷史變化趨勢",
                labels={"date_str": "日期 (UTC)", target_col: "分數", "symbol": "代幣"},
                template="plotly_dark"
            )
            fig.update_layout(
                hovermode="x unified",
                xaxis={"tickangle": -45},
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)
            
    # Tab 3: Dimensional Comparison
    with tab3:
        st.markdown("### ⚖️ 多維度分佈與交叉對比")
        
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
                "HOLD": "#2ecc71",
                "ROTATE": "#3498db",
                "TRADE": "#f1c40f",
                "AVOID": "#e74c3c"
            },
            title=f"{col_x} vs. {col_y} 交叉對比（氣泡大小代表市值）",
            labels={x_col: col_x, y_col: col_y, "action": "投資決策"},
            template="plotly_dark"
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig, use_container_width=True)
        
    # Tab 4: Score Distribution
    with tab4:
        st.markdown("### 📉 評分區間分佈（最新一期）")
        
        fig = px.histogram(
            df_latest,
            x="total",
            nbins=20,
            color="action",
            color_discrete_map={
                "HOLD": "#2ecc71",
                "ROTATE": "#3498db",
                "TRADE": "#f1c40f",
                "AVOID": "#e74c3c"
            },
            title="SOPX 總分區間直方圖",
            labels={"total": "SOPX 總分", "count": "項目數量", "action": "投資決策"},
            template="plotly_dark"
        )
        fig.update_layout(
            bargap=0.05,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig, use_container_width=True)
