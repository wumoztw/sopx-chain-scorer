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
    
    # 3. Generate Movers and flags from the latest MD report (if exists)
    # We will search for latest .md report to scrape/parse movers or compute them ourselves
    # Computing ourselves is more robust!
    # Let's compute Movers (7w trend)
    dates = sorted(df["date_utc"].unique())
    lookback_weeks = 7
    active_dates = dates[-lookback_weeks:] if len(dates) >= lookback_weeks else dates
    df_lookback = df[df["date_utc"].isin(active_dates)]
    
    # Calculate delta for each token
    movers_list = []
    drift_flags = []
    
    # Group history by ID
    by_id = df.groupby("id")
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
    # A. Trend Line Chart (Top 10 tokens by total score)
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
        title="SOPX 總分歷史趨勢 (Top 10 代幣)",
        labels={"date_str": "日期 (UTC)", "total": "SOPX 總分", "symbol": "代幣"},
        template="plotly_dark"
    )
    fig_trend.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=50, b=40)
    )
    trend_html = pio.to_html(fig_trend, include_plotlyjs=False, full_html=False)
    
    # B. Score Distribution Histogram
    fig_dist = px.histogram(
        df_latest,
        x="total",
        nbins=20,
        color="action",
        color_discrete_map={
            "HOLD": "#10B981",
            "ROTATE": "#3B82F6",
            "TRADE": "#F59E0B",
            "AVOID": "#EF4444"
        },
        title="本週 SOPX 總分區間分佈",
        labels={"total": "SOPX 總分", "count": "項目數量", "action": "投資決策"},
        template="plotly_dark"
    )
    fig_dist.update_layout(
        bargap=0.05,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=50, b=40)
    )
    dist_html = pio.to_html(fig_dist, include_plotlyjs=False, full_html=False)
    
    # C. Dimensional Scatter Plot (Constitutional vs. Risk)
    fig_scatter = px.scatter(
        df_latest,
        x="constitutional",
        y="risk",
        color="action",
        size="market_cap",
        hover_name="name",
        hover_data=["symbol", "total", "rank"],
        color_discrete_map={
            "HOLD": "#10B981",
            "ROTATE": "#3B82F6",
            "TRADE": "#F59E0B",
            "AVOID": "#EF4444"
        },
        title="🧱 制度分 vs. ⛔ 風險扣分（氣泡大小代表市值）",
        labels={"constitutional": "🧱 制度分", "risk": "⛔ 風險扣分", "action": "投資決策"},
        template="plotly_dark"
    )
    fig_scatter.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=50, b=40)
    )
    scatter_html = pio.to_html(fig_scatter, include_plotlyjs=False, full_html=False)
    
    # 5. Build Top 100 HTML Table
    table_rows_html = ""
    for idx, row in enumerate(df_latest.to_dict(orient="records"), 1):
        action_class = {
            "HOLD": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
            "ROTATE": "bg-blue-500/10 text-blue-400 border-blue-500/20",
            "TRADE": "bg-amber-500/10 text-amber-400 border-amber-500/20",
            "AVOID": "bg-red-500/10 text-red-400 border-red-500/20"
        }.get(row["action"], "bg-slate-500/10 text-slate-400 border-slate-500/20")
        
        tags = row.get("tags") or []
        tags_badges = " ".join([f'<span class="px-1.5 py-0.5 text-xs bg-slate-800 text-slate-400 rounded">{t}</span>' for t in tags[:3]])
        
        table_rows_html += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/30 transition-colors duration-150 token-row" 
            data-symbol="{row["symbol"].upper()}" data-name="{row["name"].lower()}">
            <td class="px-4 py-3 text-slate-400 font-mono text-center">{idx}</td>
            <td class="px-4 py-3 font-semibold text-white">{row["symbol"].upper()}</td>
            <td class="px-4 py-3 text-slate-300">
                <div class="flex flex-col">
                    <span>{row["name"]}</span>
                    <div class="flex gap-1 mt-1">{tags_badges}</div>
                </div>
            </td>
            <td class="px-4 py-3 text-emerald-400 font-bold text-right">{row["total"]:.1f}</td>
            <td class="px-4 py-3 text-slate-300 text-right">{row["constitutional"]:.0f}</td>
            <td class="px-4 py-3 text-slate-300 text-right">{row["demand"]:.0f}</td>
            <td class="px-4 py-3 text-slate-300 text-right">{row["capture"]:.0f}</td>
            <td class="px-4 py-3 text-red-400 text-right">{row["risk"]:.0f}</td>
            <td class="px-4 py-3 text-center">
                <span class="px-2.5 py-1 text-xs border rounded-full font-bold {action_class}">{row["action"]}</span>
            </td>
            <td class="px-4 py-3 text-slate-400 text-right font-mono">{row["vol_to_mcap"]:.3f}</td>
        </tr>
        """
        
    # Generate movers HTML lists
    movers_up_html = "".join([
        f'<li class="flex justify-between items-center py-2 border-b border-slate-800">'
        f'<span>{m["name"]} ({m["symbol"].upper()})</span>'
        f'<span class="text-emerald-400 font-bold">+{m["delta"]:.2f} → {m["total"]:.1f}</span></li>'
        for m in movers_up
    ])
    
    movers_down_html = "".join([
        f'<li class="flex justify-between items-center py-2 border-b border-slate-800">'
        f'<span>{m["name"]} ({m["symbol"].upper()})</span>'
        f'<span class="text-red-400 font-bold">{m["delta"]:.2f} → {m["total"]:.1f}</span></li>'
        for m in movers_down
    ])
    
    flags_html = "".join([
        f'<li class="text-red-400 py-2 border-b border-slate-800 text-sm">⚠️ {f}</li>'
        for f in drift_flags
    ]) if drift_flags else '<li class="text-slate-500 py-2">無警訊</li>'

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
        body {
            font-family: 'Outfit', 'Noto Sans TC', sans-serif;
            background: radial-gradient(circle at top, #0f172a 0%, #020617 100%);
        }
        .glass-panel {
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
    </style>
</head>
<body class="min-h-screen pb-12">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        
        <!-- Header -->
        <header class="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4 border-b border-slate-800 pb-6">
            <div>
                <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-red-500 to-amber-500 bg-clip-text text-transparent">
                    SOPX Chain Scorer 儀表板
                </h1>
                <p class="text-slate-400 mt-2">每週加密貨幣量化評分與制度分析趨勢監控系統</p>
            </div>
            <div class="flex flex-col items-end">
                <span class="text-xs text-slate-500 uppercase tracking-widest">最後更新時間</span>
                <span class="text-lg font-bold text-white font-mono">{{ latest_date_str }} UTC</span>
            </div>
        </header>

        <!-- Metric Cards -->
        <section class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div class="glass-panel p-5 rounded-2xl shadow-xl flex flex-col justify-between">
                <span class="text-xs text-slate-400 font-semibold tracking-wider uppercase">🧱 長期核心 (HOLD)</span>
                <span class="text-3xl font-extrabold text-emerald-400 mt-2">{{ hold_count }} <span class="text-lg font-normal text-slate-500">個項目</span></span>
            </div>
            <div class="glass-panel p-5 rounded-2xl shadow-xl flex flex-col justify-between">
                <span class="text-xs text-slate-400 font-semibold tracking-wider uppercase">🏗 成長配置 (ROTATE)</span>
                <span class="text-3xl font-extrabold text-blue-400 mt-2">{{ rotate_count }} <span class="text-lg font-normal text-slate-500">個項目</span></span>
            </div>
            <div class="glass-panel p-5 rounded-2xl shadow-xl flex flex-col justify-between">
                <span class="text-xs text-slate-400 font-semibold tracking-wider uppercase">🎭 高波動交易 (TRADE)</span>
                <span class="text-3xl font-extrabold text-amber-400 mt-2">{{ trade_count }} <span class="text-lg font-normal text-slate-500">個項目</span></span>
            </div>
            <div class="glass-panel p-5 rounded-2xl shadow-xl flex flex-col justify-between">
                <span class="text-xs text-slate-400 font-semibold tracking-wider uppercase">⛔ 結構風險 (AVOID)</span>
                <span class="text-3xl font-extrabold text-red-500 mt-2">{{ avoid_count }} <span class="text-lg font-normal text-slate-500">個項目</span></span>
            </div>
        </section>

        <!-- Trends and Movers -->
        <section class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            <!-- Movers List -->
            <div class="glass-panel p-6 rounded-2xl shadow-xl flex flex-col justify-between">
                <div>
                    <h2 class="text-lg font-bold text-white mb-4 border-b border-slate-800 pb-2">📈 7週最強勢 (Movers)</h2>
                    <ul class="space-y-1 font-mono text-sm">
                        {{ movers_up_html }}
                    </ul>
                </div>
                <div class="mt-6">
                    <h2 class="text-lg font-bold text-white mb-4 border-b border-slate-800 pb-2">📉 7週最弱勢 (Decliners)</h2>
                    <ul class="space-y-1 font-mono text-sm">
                        {{ movers_down_html }}
                    </ul>
                </div>
            </div>

            <!-- Warning flags -->
            <div class="glass-panel p-6 rounded-2xl shadow-xl">
                <h2 class="text-lg font-bold text-white mb-4 border-b border-slate-800 pb-2">⚠️ 結構變動警訊 (Drift Flags)</h2>
                <ul class="space-y-1 font-mono">
                    {{ flags_html }}
                </ul>
            </div>

            <!-- Historical line chart -->
            <div class="glass-panel p-6 rounded-2xl shadow-xl lg:col-span-1 flex flex-col justify-between">
                <div class="h-full w-full">
                    {{ trend_html }}
                </div>
            </div>
        </section>

        <!-- Charts Area -->
        <section class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <div class="glass-panel p-6 rounded-2xl shadow-xl animate-fade-in">
                {{ dist_html }}
            </div>
            <div class="glass-panel p-6 rounded-2xl shadow-xl animate-fade-in">
                {{ scatter_html }}
            </div>
        </section>

        <!-- Searchable Table -->
        <section class="glass-panel rounded-2xl shadow-xl overflow-hidden mb-8">
            <div class="p-6 border-b border-slate-800 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <h2 class="text-xl font-bold text-white">🏆 本週 Top 100 評分大盤</h2>
                <div class="w-full sm:w-72 relative">
                    <input type="text" id="token-search" placeholder="搜尋項目符號或名稱..." 
                           class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-amber-500 transition-colors duration-150">
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-900/50 border-b border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-400">
                            <th class="px-4 py-3 text-center">排名</th>
                            <th class="px-4 py-3">代幣</th>
                            <th class="px-4 py-3">名稱 / 標籤</th>
                            <th class="px-4 py-3 text-right">SOPX 總分</th>
                            <th class="px-4 py-3 text-right">🧱 制度</th>
                            <th class="px-4 py-3 text-right">🏗 需求</th>
                            <th class="px-4 py-3 text-right">🎭 捕獲</th>
                            <th class="px-4 py-3 text-right">⛔ 風險</th>
                            <th class="px-4 py-3 text-center">投資決策</th>
                            <th class="px-4 py-3 text-right">Vol/Mcap</th>
                        </tr>
                    </thead>
                    <tbody id="token-table-body">
                        {{ table_rows_html }}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Footer -->
        <footer class="text-center text-xs text-slate-600 mt-12">
            <p>SOPX Model: 總分 = (制度 × 權重) + (需求 × 權重) + (捕獲 × 權重) - (風險 × 100)</p>
            <p class="mt-2">量化系統由 GitHub Actions 自動執行 • 非投資建議 (DYOR)</p>
        </footer>

    </div>

    <!-- Search Handler script -->
    <script>
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
