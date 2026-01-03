import os, json
from datetime import datetime, timezone
from tabulate import tabulate

def sopx_ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def sopx_make_markdown(scores: list, top_n: int):
    top = sorted(scores, key=lambda x: x["total"], reverse=True)[:top_n]
    headers = ["#", "Name", "Sym", "Total", "Const", "Demand", "Capture", "Risk", "v/mcap", "Tags"]
    rows = []
    for i, s in enumerate(top, 1):
        rows.append([
            i,
            s["name"],
            s["symbol"].upper() if s["symbol"] else "",
            s["total"],
            s["constitutional"],
            s["demand"],
            s["capture"],
            s["risk"],
            f'{s["vol_to_mcap"]:.3f}',
            ",".join(s.get("tags", []))
        ])
    return tabulate(rows, headers=headers, tablefmt="github")

def sopx_format_movers(title: str, movers: list):
    lines = [f"### {title}"]
    for cid, name, sym, delta, total in movers[:10]:
        lines.append(f"- {name} ({(sym or '').upper()}): Δ{delta:+.2f} → {total:.2f}")
    return "\n".join(lines) + "\n"

def sopx_format_flags(flags: list):
    if not flags:
        return "### Drift flags\n- None\n"
    lines = ["### Drift flags"]
    for cid, name, kind, v in flags[:10]:
        lines.append(f"- {name}: {kind} ({v:.2f})")
    return "\n".join(lines) + "\n"

def sopx_write_reports(scores: list, report_dir: str, trends=None):
    sopx_ensure_dir(report_dir)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md_path = os.path.join(report_dir, f"report_{ts}.md")
    json_path = os.path.join(report_dir, f"report_{ts}.json")

    md = [f"# Weekly SOPX Score Report ({ts} UTC)\n"]
    if trends:
        movers_up, movers_down, flags = trends
        md.append(sopx_format_movers("Top movers (7w)", movers_up))
        md.append(sopx_format_movers("Top decliners (7w)", movers_down))
        md.append(sopx_format_flags(flags))
        md.append("\n---\n")

    md.append("## Top 100 (this week)\n")
    md.append(sopx_make_markdown(scores, top_n=100))
    md.append("\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)

    return md_path, json_path, ts
