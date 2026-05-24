import os
import json
import pandas as pd
import yaml
from glob import glob
from datetime import datetime
import plotly.express as px
import plotly.io as pio

# Set Plotly default template to dark
pio.templates.default = "plotly_dark"

def get_tag_value(tags, prefix):
    if not tags:
        return None
    for t in tags:
        if isinstance(t, str) and t.startswith(prefix):
            return t.split(":", 1)[1].strip()
    return None

def compute_action_label(row, tags_map):
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

def generate_html_dashboard():
    # 1. Load Data
    csv_path = "reports/history.csv"
    if not os.path.exists(csv_path):
        print("[ERROR] history.csv not found. Cannot generate dashboard.")
        return False
        
    df = pd.read_csv(csv_path)
    df["date_utc"] = pd.to_datetime(df["date_utc"])
    
    # Load latest tags from report json files
    json_files = glob("reports/report_*.json")
    tags_map = {}
    if json_files:
        latest_file = max(json_files, key=os.path.getmtime)
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                report_data = json.load(f)
            tags_map = {item["id"]: item.get("tags", []) for item in report_data}
        except Exception as e:
            print(f"[WARN] Failed to load latest tags from {latest_file}: {e}")
            
    # Enrich data
    df["tags"] = df["id"].map(lambda x: tags_map.get(x, []))
    df["action"] = df.apply(lambda r: compute_action_label(r, tags_map), axis=1)
    
    latest_date = df["date_utc"].max()
    df_latest = df[df["date_utc"] == latest_date].copy()
    df_latest = df_latest.sort_values(by="total", ascending=False)
    
    # Latest date string
    latest_date_str = latest_date.strftime("%Y-%m-%d")
    
    # 2. Compute Summary Metrics
    hold_count = int((df_latest["action"] == "HOLD").sum())
    rotate_count = int((df_latest["action"] == "ROTATE").sum())
    trade_count = int((df_latest["action"] == "TRADE").sum())
    avoid_count = int((df_latest["action"] == "AVOID").sum())
    
    # Calculate delta for each token
    movers_list = []
    drift_flags = []
    
    # Group history by ID
    by_id = df.groupby("id")
    lookback_weeks = 7
    for coin_id, group in by_id:
        group_sorted = group.sort_values(by="date_utc")
        if len(group_sorted) < 2:
            continue
            
        latest_row = group_sorted.iloc[-1]
        if latest_row["date_utc"] != latest_date:
            continue
            
        past_row = group_sorted.iloc[-(lookback_weeks+1)] if len(group_sorted) >= (lookback_weeks+1) else group_sorted.iloc[0]
        
        delta = float(latest_row["total"]) - float(past_row["total"])
        movers_list.append({
            "id": coin_id,
            "name": latest_row["name"],
            "symbol": latest_row["symbol"],
            "delta": delta,
            "total": float(latest_row["total"])
        })
        
        # Drift flags
        const_drop = float(past_row["constitutional"]) - float(latest_row["constitutional"])
        risk_jump = float(latest_row["risk"]) - float(past_row["risk"])
        if const_drop >= 15:
            drift_flags.append(f"{latest_row['name']} ({latest_row['symbol'].upper()}): 🧱 制度評分暴跌 (-{const_drop:.1f})")
        if risk_jump >= 25:
            drift_flags.append(f"{latest_row['name']} ({latest_row['symbol'].upper()}): ⛔ 風險等級飆升 (+{risk_jump:.1f})")
            
    # Sort movers
    movers_up = sorted(movers_list, key=lambda x: x["delta"], reverse=True)[:5]
    movers_down = sorted(movers_list, key=lambda x: x["delta"])[:5]
    
    # 4. Generate Interactive Plots (Plotly to HTML)
    # A. Trend Line Chart (Top 10 tokens by total score) - Using soft Morandi Sequentials
    top_10_latest_symbols = df_latest["symbol"].head(10).tolist()
    df_trend_plot = df[df["symbol"].isin(top_10_latest_symbols)].copy()
    df_trend_plot = df_trend_plot.sort_values(by="date_utc")
    df_trend_plot["date_str"] = df_trend_plot["date_utc"].dt.strftime("%Y-%m-%d")
    
    fig_trend = px.line(
        df_trend_plot,
        x="date_str",
        y="total",
        color="symbol",
        markers=True,
        line_shape="spline",  # Smooth lines
        color_discrete_sequence=["#ff6b4a", "#84cc16", "#38bdf8", "#f43f5e", "#a78bfa", "#fb923c", "#2dd4bf", "#f472b6"],
        title="SOPX 總分歷史趨勢 (Top 10 代幣)",
        labels={"date_str": "日期 (UTC)", "total": "SOPX 總分", "symbol": "代幣"},
        template="plotly_dark"
    )
    fig_trend.update_traces(line=dict(width=3.0)) # Thicker lines
    fig_trend.update_layout(
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-45, showgrid=True, gridcolor="rgba(255,255,255,0.08)", rangeslider=dict(visible=True)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        margin=dict(l=40, r=40, t=50, b=40),
        font=dict(family="Outfit, Noto Sans TC, sans-serif", size=12),
        hoverlabel=dict(
            bgcolor="rgba(18,18,18,0.9)",
            font_size=13,
            font_family="Outfit, Noto Sans TC, sans-serif",
            bordercolor="rgba(255,255,255,0.1)"
        )
    )
    trend_html = pio.to_html(fig_trend, include_plotlyjs=False, full_html=False, config={'displayModeBar': False})
    
    # B. Score Distribution Histogram - Plurk brand colors
    fig_dist = px.histogram(
        df_latest,
        x="total",
        nbins=20,
        color="action",
        marginal="box",
        color_discrete_map={
            "HOLD": "#84cc16",
            "ROTATE": "#38bdf8",
            "TRADE": "#ff6b4a",
            "AVOID": "#f43f5e"
        },
        title="本週 SOPX 總分區間分佈",
        labels={"total": "SOPX 總分", "action": "投資決策"},
        template="plotly_dark"
    )
    fig_dist.update_layout(
        bargap=0.08,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        margin=dict(l=40, r=40, t=50, b=40),
        font=dict(family="Outfit, Noto Sans TC, sans-serif", size=12),
        hoverlabel=dict(
            bgcolor="rgba(18,18,18,0.9)",
            font_size=13,
            font_family="Outfit, Noto Sans TC, sans-serif",
            bordercolor="rgba(255,255,255,0.1)"
        )
    )
    dist_html = pio.to_html(fig_dist, include_plotlyjs=False, full_html=False, config={'displayModeBar': False})
    
    median_c = df_latest["constitutional"].median()
    median_r = df_latest["risk"].median()

    fig_scatter = px.scatter(
        df_latest,
        x="constitutional",
        y="risk",
        color="action",
        size="market_cap",
        hover_name="name",
        hover_data=["symbol", "total", "rank"],
        color_discrete_map={
            "HOLD": "#84cc16",
            "ROTATE": "#38bdf8",
            "TRADE": "#ff6b4a",
            "AVOID": "#f43f5e"
        },
        title="🧱 制度分 vs. ⛔ 風險扣分（氣泡大小代表市值）",
        labels={"constitutional": "🧱 制度分", "risk": "⛔ 風險扣分", "action": "投資決策"},
        template="plotly_dark"
    )
    
    fig_scatter.update_traces(
        hovertemplate="<br>".join([
            "<b>%{hovertext}</b> (%{customdata[0]})",
            "🧱 制度分: <b>%{x:.1f}</b>",
            "⛔ 風險扣分: <b>%{y:.1f}</b>",
            "SOPX 總分: %{customdata[1]:.1f} (Rank #%{customdata[2]})"
        ]),
        marker=dict(line=dict(width=1.2, color='rgba(255,255,255,0.25)'), opacity=0.9)
    )
    
    # Add Quadrant Crosshairs
    fig_scatter.add_vline(x=median_c, line_dash="dash", line_color="rgba(255,255,255,0.15)", annotation_text=" 中位數", annotation_position="top right", annotation_font_color="rgba(255,255,255,0.4)")
    fig_scatter.add_hline(y=median_r, line_dash="dash", line_color="rgba(255,255,255,0.15)", annotation_text="中位數", annotation_position="top right", annotation_font_color="rgba(255,255,255,0.4)")

    fig_scatter.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        margin=dict(l=40, r=40, t=50, b=40),
        font=dict(family="Outfit, Noto Sans TC, sans-serif", size=12),
        hoverlabel=dict(
            bgcolor="rgba(18,18,18,0.9)",
            font_size=13,
            font_family="Outfit, Noto Sans TC, sans-serif",
            bordercolor="rgba(255,255,255,0.1)"
        )
    )
    scatter_html = pio.to_html(fig_scatter, include_plotlyjs=False, full_html=False, config={'displayModeBar': False})
    
    # 5. Build Top 100 HTML Table - Premium dark theme styling
    table_rows_html = ""
    for idx, row in enumerate(df_latest.to_dict(orient="records"), 1):
        action_class = {
            "HOLD": "bg-[#84cc16]/10 text-[#84cc16] border-[#84cc16]/25",
            "ROTATE": "bg-[#38bdf8]/10 text-[#38bdf8] border-[#38bdf8]/25",
            "TRADE": "bg-[#ff6b4a]/10 text-[#ff6b4a] border-[#ff6b4a]/25",
            "AVOID": "bg-[#f43f5e]/10 text-[#f43f5e] border-[#f43f5e]/25"
        }.get(row["action"], "bg-white/5 text-white/40 border-white/10")
        
        tags = row.get("tags") or []
        tags_badges = " ".join([f'<span class="px-2 py-0.5 text-2xs bg-white/[0.04] text-white/50 border border-white/[0.08] rounded font-medium">{t}</span>' for t in tags[:3]])
        
        total_score_class = "text-[#f43f5e]" if row["action"] == "AVOID" else "text-[#ff6b4a]"
        
        table_rows_html += f"""
        <tr class="token-row" 
            data-symbol="{row["symbol"].upper()}" data-name="{row["name"].lower()}">
            <td class="px-4 py-3.5 text-white/35 font-mono text-center">{idx}</td>
            <td class="px-4 py-3.5 font-semibold text-white tracking-wider">{row["symbol"].upper()}</td>
            <td class="px-4 py-3.5 text-white/60">
                <div class="flex flex-col">
                    <span class="font-medium text-white/80">{row["name"]}</span>
                    <div class="flex flex-wrap gap-1 mt-1">{tags_badges}</div>
                </div>
            </td>
            <td class="px-4 py-3.5 {total_score_class} font-bold text-right text-base">{row["total"]:.1f}</td>
            <td class="px-4 py-3.5 text-white/70 text-right">{row["constitutional"]:.0f}</td>
            <td class="px-4 py-3.5 text-white/70 text-right">{row["demand"]:.0f}</td>
            <td class="px-4 py-3.5 text-white/70 text-right">{row["capture"]:.0f}</td>
            <td class="px-4 py-3.5 text-[#f43f5e] font-medium text-right">{row["risk"]:.0f}</td>
            <td class="px-4 py-3.5 text-center">
                <span class="px-2.5 py-1 text-xs border rounded-full font-bold {action_class}">{row["action"]}</span>
            </td>
            <td class="px-4 py-3.5 text-white/30 text-right font-mono text-xs">{row["vol_to_mcap"]:.3f}</td>
        </tr>
        """
        
    # Generate movers HTML lists
    movers_up_html = "".join([
        f'<li class="flex justify-between items-center py-2.5 border-b border-white/[0.06]">'
        f'<span class="font-semibold text-white/80">{m["name"]} ({m["symbol"].upper()})</span>'
        f'<span class="text-[#84cc16] font-bold font-mono">+{m["delta"]:.2f} → {m["total"]:.1f}</span></li>'
        for m in movers_up
    ])
    
    movers_down_html = "".join([
        f'<li class="flex justify-between items-center py-2.5 border-b border-white/[0.06]">'
        f'<span class="font-semibold text-white/80">{m["name"]} ({m["symbol"].upper()})</span>'
        f'<span class="text-[#f43f5e] font-bold font-mono">{m["delta"]:.2f} → {m["total"]:.1f}</span></li>'
        for m in movers_down
    ])
    
    flags_html = "".join([
        f'<li class="text-[#f43f5e] py-2.5 border-b border-white/[0.06] text-sm font-semibold flex items-center gap-2">'
        f'<span class="w-1.5 h-1.5 rounded-full bg-[#f43f5e] shadow-[0_0_6px_rgba(244,63,94,0.5)]"></span>{f}</li>'
        for f in drift_flags
    ]) if drift_flags else '<li class="text-white/30 py-3 text-sm">無異常變動警訊</li>'

    # 6. HTML Template (Jinja2)
    html_template = """<!DOCTYPE html>
<html lang="zh-Hant" class="bg-slate-950 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SOPX Chain Scorer 視覺化儀表板</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+TC:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        /* ═══════════════════════════════════════════════════
           SOPX Premium Design System — Plurk Dark Edition
           ═══════════════════════════════════════════════════ */

        /* --- Animated Counter via @property --- */
        @property --counter-val {
            syntax: "<integer>";
            initial-value: 0;
            inherits: false;
        }

        /* --- Base & Mesh Gradient Background --- */
        body {
            font-family: 'Outfit', 'Noto Sans TC', sans-serif;
            background-color: #121212;
            background-image:
                radial-gradient(ellipse at 15% 20%, rgba(207, 81, 48, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 85% 25%, rgba(56, 189, 248, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(168, 85, 247, 0.04) 0%, transparent 50%);
            background-attachment: fixed;
            color: rgba(255,255,255,0.87);
        }

        /* Grain Texture Overlay */
        body::after {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.03;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
            background-repeat: repeat;
            background-size: 256px 256px;
        }

        /* --- Enhanced Glassmorphism Panels --- */
        .glass-panel {
            background: rgba(255, 255, 255, 0.04);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-top-color: rgba(255, 255, 255, 0.12); /* top highlight */
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                        box-shadow 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                        border-color 0.35s ease;
            position: relative;
            z-index: 1;
        }

        /* --- Metric Card Gradient Border Glow --- */
        .metric-card {
            background:
                linear-gradient(rgba(18,18,18,0.92), rgba(18,18,18,0.92)) padding-box,
                linear-gradient(135deg, var(--glow-from, rgba(255,107,74,0.4)), var(--glow-to, rgba(255,107,74,0.08))) border-box;
            border: 1.5px solid transparent;
            border-radius: 20px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                        box-shadow 0.35s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            z-index: 1;
        }
        .metric-card--hold   { --glow-from: rgba(132,204,22,0.5);  --glow-to: rgba(132,204,22,0.08); }
        .metric-card--rotate { --glow-from: rgba(56,189,248,0.5);  --glow-to: rgba(56,189,248,0.08); }
        .metric-card--trade  { --glow-from: rgba(255,107,74,0.5);  --glow-to: rgba(255,107,74,0.08); }
        .metric-card--avoid  { --glow-from: rgba(244,63,94,0.5);   --glow-to: rgba(244,63,94,0.08); }

        /* --- Hover Glow --- */
        .metric-card:hover {
            transform: translateY(-6px);
        }
        .metric-card--hold:hover   { box-shadow: 0 12px 40px rgba(132,204,22,0.18); }
        .metric-card--rotate:hover { box-shadow: 0 12px 40px rgba(56,189,248,0.18); }
        .metric-card--trade:hover  { box-shadow: 0 12px 40px rgba(255,107,74,0.18); }
        .metric-card--avoid:hover  { box-shadow: 0 12px 40px rgba(244,63,94,0.18); }

        .glass-panel:hover {
            transform: translateY(-3px);
            border-color: rgba(255, 255, 255, 0.14);
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
        }

        /* --- Staggered Entrance Animations --- */
        @keyframes fadeSlideUp {
            from { opacity: 0; transform: translateY(24px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to   { opacity: 1; }
        }
        .anim-enter {
            opacity: 0;
            animation: fadeSlideUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }
        .anim-enter-1 { animation-delay: 0.08s; }
        .anim-enter-2 { animation-delay: 0.16s; }
        .anim-enter-3 { animation-delay: 0.24s; }
        .anim-enter-4 { animation-delay: 0.32s; }
        .anim-section {
            opacity: 0;
            animation: fadeSlideUp 0.8s cubic-bezier(0.22, 1, 0.36, 1) 0.5s forwards;
        }

        /* --- CSS Counter Animation --- */
        .counter-animate {
            --counter-val: 0;
            counter-reset: c var(--counter-val);
            animation: countUp 1.8s cubic-bezier(0.22, 1, 0.36, 1) forwards;
            font-variant-numeric: tabular-nums;
        }
        .counter-animate::after {
            content: counter(c);
        }
        @keyframes countUp {
            /* target values set inline via style attr */
        }

        /* --- Section Headers with Decorative Accent --- */
        .section-title {
            position: relative;
            padding-left: 16px;
            font-weight: 700;
            font-size: 1.05rem;
            color: rgba(255,255,255,0.92);
        }
        .section-title::before {
            content: "";
            position: absolute;
            left: 0;
            top: 2px;
            bottom: 2px;
            width: 3px;
            border-radius: 2px;
            background: linear-gradient(180deg, #ff6b4a, #cf5130);
        }

        /* --- Table Enhancements --- */
        .table-container thead th {
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: rgba(18, 18, 18, 0.95);
            backdrop-filter: blur(8px);
        }
        .token-row:nth-child(even) {
            background-color: rgba(255, 255, 255, 0.02);
        }
        .token-row {
            transition: background-color 0.18s ease;
        }
        .token-row:hover {
            background-color: rgba(255, 107, 74, 0.06) !important;
        }

        /* --- Custom Scrollbar --- */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: rgba(20, 20, 20, 0.2); }
        ::-webkit-scrollbar-thumb { background: rgba(255, 107, 74, 0.12); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255, 107, 74, 0.25); }

        /* --- Utility --- */
        .text-2xs { font-size: 0.65rem; }

        /* --- Accessibility: Reduced Motion --- */
        @media (prefers-reduced-motion: reduce) {
            .anim-enter,
            .anim-section,
            .counter-animate {
                animation: none !important;
                opacity: 1 !important;
            }
            .metric-card,
            .glass-panel,
            .token-row {
                transition: none !important;
            }
        }
    </style>
</head>
<body class="min-h-screen pb-16 relative overflow-x-hidden">
    
    <!-- Top Plurk Brand Gradient Border -->
    <div class="w-full h-[3px] bg-gradient-to-r from-[#cf5130] via-[#ff6b4a] via-[#84cc16] to-[#3b82f6] absolute top-0 left-0 z-50"></div>
 
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-10 relative z-10">
        
        <!-- Header -->
        <header class="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 border-b border-white/[0.06] pb-8 anim-enter anim-enter-1">
            <div>
                <h1 class="text-4xl sm:text-5xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-[#f5f4f0] bg-clip-text text-transparent">
                    SOPX Chain Scorer 儀表板
                </h1>
                <p class="text-white/60 mt-3 text-sm sm:text-base font-medium">每週加密貨幣量化評分與制度分析趨勢監控系統</p>
            </div>
            <div class="flex flex-col md:items-end glass-panel rounded-2xl px-5 py-3 mt-4 md:mt-0">
                <span class="text-2xs text-white/40 uppercase tracking-widest font-bold">最後更新時間</span>
                <span class="text-base sm:text-lg font-extrabold text-white font-mono mt-1">{{ latest_date_str }} UTC</span>
            </div>
        </header>
 
        <!-- Metric Cards (Premium Gradient Border Glow) -->
        <section class="grid grid-cols-2 lg:grid-cols-4 gap-5 mb-10">
            <div class="metric-card metric-card--hold p-6 flex flex-col justify-between anim-enter anim-enter-1">
                <span class="text-xs text-white/70 font-semibold tracking-wider uppercase flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-[#84cc16] shadow-[0_0_8px_rgba(132,204,22,0.5)]"></span>🧱 長期核心 (HOLD)
                </span>
                <div class="mt-4 flex items-baseline gap-2">
                    <span class="text-3xl sm:text-4xl font-extrabold text-[#84cc16] font-mono" data-count="{{ hold_count }}">{{ hold_count }}</span>
                    <span class="text-sm font-normal text-white/40">個項目</span>
                </div>
            </div>
            <div class="metric-card metric-card--rotate p-6 flex flex-col justify-between anim-enter anim-enter-2">
                <span class="text-xs text-white/70 font-semibold tracking-wider uppercase flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-[#38bdf8] shadow-[0_0_8px_rgba(56,189,248,0.5)]"></span>🏗 成長配置 (ROTATE)
                </span>
                <div class="mt-4 flex items-baseline gap-2">
                    <span class="text-3xl sm:text-4xl font-extrabold text-[#38bdf8] font-mono" data-count="{{ rotate_count }}">{{ rotate_count }}</span>
                    <span class="text-sm font-normal text-white/40">個項目</span>
                </div>
            </div>
            <div class="metric-card metric-card--trade p-6 flex flex-col justify-between anim-enter anim-enter-3">
                <span class="text-xs text-white/70 font-semibold tracking-wider uppercase flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-[#ff6b4a] shadow-[0_0_8px_rgba(255,107,74,0.5)]"></span>🎭 高波動交易 (TRADE)
                </span>
                <div class="mt-4 flex items-baseline gap-2">
                    <span class="text-3xl sm:text-4xl font-extrabold text-[#ff6b4a] font-mono" data-count="{{ trade_count }}">{{ trade_count }}</span>
                    <span class="text-sm font-normal text-white/40">個項目</span>
                </div>
            </div>
            <div class="metric-card metric-card--avoid p-6 flex flex-col justify-between anim-enter anim-enter-4">
                <span class="text-xs text-white/70 font-semibold tracking-wider uppercase flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.5)]"></span>⛔ 結構風險 (AVOID)
                </span>
                <div class="mt-4 flex items-baseline gap-2">
                    <span class="text-3xl sm:text-4xl font-extrabold text-[#f43f5e] font-mono" data-count="{{ avoid_count }}">{{ avoid_count }}</span>
                    <span class="text-sm font-normal text-white/40">個項目</span>
                </div>
            </div>
        </section>

        <!-- Trends and Movers -->
        <section class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10 anim-section">
            <!-- Movers List -->
            <div class="glass-panel p-6 rounded-2xl flex flex-col justify-between lg:col-span-1">
                <div>
                    <h2 class="section-title mb-4 pb-2 border-b border-white/[0.06] flex items-center gap-2">
                        📈 7週強勢榜 (Movers)
                    </h2>
                    <ul class="space-y-1 font-mono text-sm">
                        {{ movers_up_html }}
                    </ul>
                </div>
                <div class="mt-8">
                    <h2 class="section-title mb-4 pb-2 border-b border-white/[0.06] flex items-center gap-2">
                        📉 7週弱勢榜 (Decliners)
                    </h2>
                    <ul class="space-y-1 font-mono text-sm">
                        {{ movers_down_html }}
                    </ul>
                </div>
            </div>

            <!-- Warning flags -->
            <div class="glass-panel p-6 rounded-2xl lg:col-span-1">
                <h2 class="section-title mb-4 pb-2 border-b border-white/[0.06] flex items-center gap-2">
                    ⚠️ 結構變動警訊 (Drift Flags)
                </h2>
                <ul class="space-y-1">
                    {{ flags_html }}
                </ul>
            </div>

            <!-- Historical line chart -->
            <div class="glass-panel p-6 rounded-2xl lg:col-span-1 flex flex-col justify-between">
                <div class="h-full w-full">
                    {{ trend_html }}
                </div>
            </div>
        </section>

        <!-- Charts Area -->
        <section class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10 anim-section" style="animation-delay: 0.7s;">
            <div class="glass-panel p-6 rounded-2xl min-h-[360px]">
                {{ dist_html }}
            </div>
            <div class="glass-panel p-6 rounded-2xl min-h-[360px]">
                {{ scatter_html }}
            </div>
        </section>

        <!-- Searchable Table -->
        <section class="glass-panel rounded-2xl overflow-hidden mb-10 anim-section" style="animation-delay: 0.9s;">
            <div class="p-6 border-b border-white/[0.06] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <h2 class="section-title text-lg flex items-center gap-2">🏆 本週 Top 100 評分大盤</h2>
                <div class="w-full sm:w-72 relative">
                    <input type="text" id="token-search" placeholder="搜尋項目符號或名稱..." 
                           class="w-full bg-black/30 border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-[#ff6b4a]/40 focus:ring-1 focus:ring-[#ff6b4a]/20 transition-all duration-200">
                </div>
            </div>
            <div class="overflow-x-auto table-container" style="max-height: 700px; overflow-y: auto;">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="border-b border-white/[0.06] text-2xs font-bold uppercase tracking-widest text-white/35">
                            <th class="px-4 py-3.5 text-center w-16">排名</th>
                            <th class="px-4 py-3.5 w-24">代幣</th>
                            <th class="px-4 py-3.5">項目 / 標籤</th>
                            <th class="px-4 py-3.5 text-right w-28">SOPX 總分</th>
                            <th class="px-4 py-3.5 text-right w-20">🧱 制度</th>
                            <th class="px-4 py-3.5 text-right w-20">🏗 需求</th>
                            <th class="px-4 py-3.5 text-right w-20">🎭 捕獲</th>
                            <th class="px-4 py-3.5 text-right w-20">⛔ 風險</th>
                            <th class="px-4 py-3.5 text-center w-32">投資決策</th>
                            <th class="px-4 py-3.5 text-right w-24">Vol/Mcap</th>
                        </tr>
                    </thead>
                    <tbody id="token-table-body" class="divide-y divide-white/[0.04]">
                        {{ table_rows_html }}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Footer -->
        <footer class="mt-16 mb-8">
            <div class="w-full h-px bg-gradient-to-r from-transparent via-[#ff6b4a]/30 to-transparent mb-8"></div>
            <div class="flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-white/30">
                <div class="flex flex-col items-center md:items-start gap-1.5">
                    <p class="font-semibold text-white/50">SOPX Chain Scorer</p>
                    <p>總分 = (制度 × 權重) + (需求 × 權重) + (捕獲 × 權重) - (風險 × 100)</p>
                </div>
                <div class="flex flex-col items-center md:items-end gap-1.5 text-right">
                    <p>量化系統由 GitHub Actions 自動執行</p>
                    <p class="text-white/20">非投資建議 (DYOR) • Powered by SOPX Model</p>
                </div>
            </div>
        </footer>

    </div>

    <!-- Scripts -->
    <script>
        /* === Search Handler === */
        document.getElementById('token-search').addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase().trim();
            const rows = document.querySelectorAll('.token-row');
            
            rows.forEach(row => {
                const symbol = row.getAttribute('data-symbol').toLowerCase();
                const name = row.getAttribute('data-name').toLowerCase();
                
                if (symbol.includes(query) || name.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });

        /* === Animated Number Counter === */
        function animateCounters() {
            const counters = document.querySelectorAll('[data-count]');
            counters.forEach(counter => {
                const target = parseInt(counter.getAttribute('data-count'), 10);
                const duration = 1600;
                const start = performance.now();
                
                counter.textContent = '0';
                
                function update(now) {
                    const elapsed = now - start;
                    const progress = Math.min(elapsed / duration, 1);
                    // Ease-out cubic
                    const eased = 1 - Math.pow(1 - progress, 3);
                    counter.textContent = Math.round(eased * target);
                    
                    if (progress < 1) {
                        requestAnimationFrame(update);
                    } else {
                        counter.textContent = target;
                    }
                }
                
                requestAnimationFrame(update);
            });
        }
        
        /* Respect prefers-reduced-motion */
        if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            animateCounters();
        }
    </script>
</body>
</html>
"""

    from jinja2 import Template
    t = Template(html_template)
    html_content = t.render(
        latest_date_str=latest_date_str,
        hold_count=hold_count,
        rotate_count=rotate_count,
        trade_count=trade_count,
        avoid_count=avoid_count,
        movers_up_html=movers_up_html,
        movers_down_html=movers_down_html,
        flags_html=flags_html,
        trend_html=trend_html,
        dist_html=dist_html,
        scatter_html=scatter_html,
        table_rows_html=table_rows_html
    )

    # Ensure docs directory exists
    os.makedirs("docs", exist_ok=True)
    out_path = "docs/index.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"[SUCCESS] Dashboard generated successfully at: {out_path}")
    return True

if __name__ == "__main__":
    generate_html_dashboard()
