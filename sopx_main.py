import os
import yaml

from sopx_coingecko import SopxCoinGeckoClient
from sopx_scorer import sopx_score_coin
from sopx_report import sopx_write_reports, sopx_make_markdown
from sopx_plurk import sopx_post_plurk
from sopx_history import sopx_append_history, sopx_compute_trends, sopx_utc_today_str

def sopx_load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    cfg = sopx_load_yaml("config.yml")
    overrides = sopx_load_yaml("manual_overrides.yml")

    cg = SopxCoinGeckoClient(delay_sec=cfg["coingecko"]["request_delay_sec"])

    markets = cg.top_markets(
        vs_currency=cfg["coingecko"]["vs_currency"],
        per_page=cfg["coingecko"]["top_n"],
        page=1
    )

    scores = []
    for row in markets:
        coin_id = row["id"]
try:
    detail = cg.coin_detail(coin_id)
except Exception as e:
    # Don't fail the whole job on a single coin
    print(f"[WARN] coin_detail failed for {coin_id}: {e}. Using empty detail.")
    detail = {}
s = sopx_score_coin(row, detail, cfg, overrides)
        scores.append(s)

    date_utc = sopx_utc_today_str()
    sopx_append_history(scores, date_utc)

    trends = sopx_compute_trends(scores, weeks_lookback=7)

    report_dir = cfg["output"]["report_dir"]
    md_path, json_path, ts = sopx_write_reports(scores, report_dir, trends=trends)

    top_n = cfg["output"]["top_to_post"]
    top_md = sopx_make_markdown(scores, top_n=top_n)

    movers_up, movers_down, flags = trends
    movers_line = ""
    if movers_up:
        cid, name, sym, delta, total = movers_up[0]
        movers_line = f"\n最大上升（7w）：{name}({(sym or '').upper()}) Δ{delta:+.2f}"
    if movers_down:
        cid, name, sym, delta, total = movers_down[0]
        movers_line += f"\n最大下降（7w）：{name}({(sym or '').upper()}) Δ{delta:+.2f}"
    flag_line = f"\nDrift flags：{len(flags)}"

    header = f"【Weekly SOPX Scores】Top {top_n}｜{ts} UTC{movers_line}{flag_line}\n"
    note = "\n(Scoring = SOP-Quant proxy + curated_facts + plugin rules; full report in repo)\n"
    content = header + "```\n" + top_md + "\n```\n" + note

    max_chars = cfg["plurk"]["max_chars"]
    if len(content) > max_chars:
        top_md2 = sopx_make_markdown(scores, top_n=min(5, top_n))
        content = header + "```\n" + top_md2 + "\n```\n" + note
        content = content[:max_chars-5] + "…"

    ck = os.getenv("PLURK_CONSUMER_KEY")
    cs = os.getenv("PLURK_CONSUMER_SECRET")
    at = os.getenv("PLURK_ACCESS_TOKEN")
    ats = os.getenv("PLURK_ACCESS_TOKEN_SECRET")

    if all([ck, cs, at, ats]):
        sopx_post_plurk(content, ck, cs, at, ats)
        print("Posted to Plurk.")
    else:
        print("Plurk secrets missing; skipping post.")
        print(content)

if __name__ == "__main__":
    main()
