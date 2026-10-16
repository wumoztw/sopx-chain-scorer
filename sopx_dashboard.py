import html
import math
import os
from datetime import datetime, timezone


def _number(score, key):
    try:
        value = float(score.get(key) or 0)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return value if math.isfinite(value) else 0.0


def _action_label(score):
    constitutional = _number(score, "constitutional")
    risk = _number(score, "risk")
    tags = score.get("tags") or []
    if not isinstance(tags, (list, tuple, set)):
        tags = []
    tag_values = [tag for tag in tags if isinstance(tag, str)]
    layer = next((tag.split(":", 1)[1].strip() for tag in tag_values if tag.startswith("layer:")), None)
    thesis = next((tag.split(":", 1)[1].strip() for tag in tag_values if tag.startswith("thesis:")), None)

    if risk >= 40:
        return "AVOID"
    if constitutional >= 85 or layer == "civilization":
        return "HOLD"
    if (constitutional >= 55 and thesis != "narrative") or layer == "regional":
        return "ROTATE"
    return "TRADE"


def sopx_make_dashboard(scores, report_dir="reports"):
    """Write a self-contained, responsive HTML ranking for scored assets."""
    os.makedirs(report_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(report_dir, f"dashboard_{ts}.html")
    ranked = sorted(scores or [], key=lambda score: _number(score, "total"), reverse=True)
    average = sum(_number(score, "total") for score in ranked) / len(ranked) if ranked else 0

    rows = []
    for rank, score in enumerate(ranked, 1):
        symbol = html.escape(str(score.get("symbol") or "—"))
        name = html.escape(str(score.get("name") or ""))
        total = _number(score, "total")
        progress = max(0.0, min(total, 100.0))
        tags = score.get("tags") or []
        if not isinstance(tags, (list, tuple, set)):
            tags = []
        tag_badges = "".join(
            f'<span class="tag">{html.escape(str(tag))}</span>'
            for tag in tags
        )
        action = _action_label(score)
        rows.append(f"""
          <tr>
            <td class="rank">{rank:02d}</td>
            <td><div class="asset"><strong>{symbol}</strong><span>{name}</span></div></td>
            <td class="score"><strong>{total:.1f}</strong><div class="progress" role="img" aria-label="{total:.1f} / 100"><span style="width:{progress:.1f}%"></span></div></td>
            <td>{_number(score, "constitutional"):.1f}</td>
            <td>{_number(score, "demand"):.1f}</td>
            <td>{_number(score, "capture"):.1f}</td>
            <td>{_number(score, "risk"):.1f}</td>
            <td><span class="action action-{action.lower()}">{action}</span></td>
            <td class="tags">{tag_badges or '<span class="muted">—</span>'}</td>
          </tr>""")

    empty_state = '<tr><td class="empty" colspan="9">目前沒有可顯示的評分資料。</td></tr>'
    html_doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>SOPX Dashboard · {ts}</title>
  <style>
    :root {{ color-scheme: dark; --bg: #080b14; --panel: rgba(18, 25, 42, .76); --line: rgba(151, 174, 220, .14); --text: #eaf0ff; --muted: #91a0bb; --accent: #72e4d3; }}
    * {{ box-sizing: border-box; }}
    body {{ min-height: 100vh; margin: 0; padding: 42px clamp(18px, 5vw, 76px); color: var(--text); font: 14px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; background: radial-gradient(ellipse at 14% 0%, #172b45 0, transparent 42%), radial-gradient(ellipse at 90% 12%, #281d47 0, transparent 34%), var(--bg); }}
    .shell {{ max-width: 1440px; margin: 0 auto; }}
    .eyebrow {{ color: var(--accent); font-size: 11px; font-weight: 800; letter-spacing: .2em; text-transform: uppercase; }}
    header {{ display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 30px; }}
    h1 {{ margin: 8px 0 0; font-size: clamp(30px, 5vw, 48px); letter-spacing: -.045em; line-height: 1.05; }}
    .date {{ color: var(--muted); white-space: nowrap; }}
    .overview {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }}
    .panel {{ border: 1px solid var(--line); border-radius: 16px; background: var(--panel); box-shadow: 0 18px 48px rgba(0, 0, 0, .22); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); }}
    .stat {{ padding: 19px 22px; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .stat strong {{ display: block; margin-top: 5px; font-size: 25px; letter-spacing: -.03em; }}
    .table-panel {{ overflow: hidden; }}
    .table-heading {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 20px 22px; border-bottom: 1px solid var(--line); }}
    h2 {{ margin: 0; font-size: 16px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; min-width: 980px; border-collapse: collapse; text-align: left; }}
    th {{ padding: 12px 14px; color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
    td {{ padding: 13px 14px; border-top: 1px solid rgba(151, 174, 220, .08); white-space: nowrap; }}
    tbody tr:hover {{ background: rgba(255, 255, 255, .025); }}
    .rank {{ width: 54px; color: var(--muted); font-variant-numeric: tabular-nums; }}
    .asset {{ display: grid; gap: 2px; }}
    .asset strong {{ font-size: 14px; }}
    .asset span, .muted {{ color: var(--muted); font-size: 11px; }}
    .score {{ min-width: 150px; font-variant-numeric: tabular-nums; }}
    .score strong {{ font-size: 15px; }}
    .progress {{ height: 5px; margin-top: 7px; overflow: hidden; border-radius: 99px; background: rgba(255, 255, 255, .09); }}
    .progress span {{ display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #70e2d0, #8584ff); }}
    .action {{ display: inline-flex; padding: 4px 9px; border: 1px solid currentColor; border-radius: 999px; font-size: 10px; font-weight: 800; letter-spacing: .08em; }}
    .action-hold {{ color: #6be3c0; background: rgba(50, 190, 147, .12); }}
    .action-rotate {{ color: #78baff; background: rgba(65, 145, 235, .12); }}
    .action-trade {{ color: #f3c66e; background: rgba(227, 171, 58, .12); }}
    .action-avoid {{ color: #ff8298; background: rgba(237, 78, 111, .12); }}
    .tags {{ max-width: 240px; white-space: normal; }}
    .tag {{ display: inline-block; margin: 2px 4px 2px 0; padding: 3px 7px; border: 1px solid var(--line); border-radius: 6px; color: #b6c4dc; font-size: 10px; }}
    .empty {{ padding: 40px 16px; color: var(--muted); text-align: center; }}
    footer {{ padding: 16px 2px; color: var(--muted); font-size: 11px; }}
    @media (max-width: 640px) {{ body {{ padding: 26px 14px; }} header {{ align-items: start; flex-direction: column; }} .overview {{ grid-template-columns: 1fr; gap: 9px; }} .stat {{ padding: 14px 17px; }} .stat strong {{ font-size: 21px; }} .table-heading {{ padding: 16px; }} }}
    @media (prefers-reduced-transparency: reduce) {{ .panel {{ background: #12192a; backdrop-filter: none; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <header><div><div class="eyebrow">SOPX · Market Intelligence</div><h1>Chain Scoreboard</h1></div><div class="date">UTC · {ts}</div></header>
    <section class="overview" aria-label="評分摘要">
      <article class="panel stat"><span>追蹤資產</span><strong>{len(ranked)}</strong></article>
      <article class="panel stat"><span>平均總分</span><strong>{average:.1f}<small> / 100</small></strong></article>
      <article class="panel stat"><span>最高評分</span><strong>{_number(ranked[0], "total") if ranked else 0:.1f}<small> / 100</small></strong></article>
    </section>
    <section class="panel table-panel" aria-labelledby="ranking-title">
      <div class="table-heading"><h2 id="ranking-title">資產評分排行</h2><span class="muted">依總分排序 · {len(ranked)} 項</span></div>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>資產</th><th>總分</th><th>制度</th><th>需求</th><th>捕獲</th><th>風險</th><th>Action</th><th>標籤</th></tr></thead>
        <tbody>{''.join(rows) if rows else empty_state}</tbody>
      </table></div>
    </section>
    <footer>由 SOPX Chain Scorer 產生 · 本檔包含完整樣式，無需外部資源</footer>
  </main>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as report:
        report.write(html_doc)
    return path
