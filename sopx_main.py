import os
import yaml

from sopx_coingecko import SopxCoinGeckoClient
from sopx_scorer import sopx_score_coin
from sopx_report import sopx_write_reports, sopx_make_markdown
from sopx_plurk import sopx_post_plurk
from sopx_history import (
    sopx_append_history,
    sopx_compute_trends,
    sopx_utc_today_str,
)


def sopx_load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sopx_build_drift_alert_post(flags, date_utc, max_items=5):
    """
    Build second Plurk post for drift alerts.
    flags: list of (coin_id, name, kind, value)
    """
    if not flags:
        return None

    lines = []
    lines.append(f"⚠️ SOPX Drift Alert｜{date_utc} UTC\n")
    lines.append(
        "以下標的出現「制度 / 風險漂移」警示（前 {} 名）：\n".format(
            min(max_items, len(flags))
        )
    )

    for i, (_, name, kind, v) in enumerate(flags[:max_items], 1):
        lines.append(f"{i}️⃣ {name}")
        lines.append(f"   - {kind} ({v:+.2f})\n")

    lines.append("建議檢查：")
    lines.append("- 治理 / admin key / 升級權限")
    lines.append("- 核心應用或流動性是否遷移")
    lines.append("- 補貼是否退潮、敘事是否轉向\n")
    lines.append("（SOPX 自動偵測｜非投資建議）")

    return "\n".join(lines)


def main():
    cfg = sopx_load_yaml("config.yml")
    overrides = sopx_load_yaml("manual_overrides.yml")

    cg = SopxCoinGeckoClient(
        delay_sec=cfg["coingecko"]["request_delay_sec"]
    )

    markets = cg.top_markets(
        vs_currency=cfg["coingecko"]["vs_currency"],
        per_page=cfg["coingecko"]["top_n"],
        page=1,
    )

    scores = []

    for row in markets:
        coin_id = row["id"]

        try:
            detail = cg.coin_detail(coin_id)
        except Exception as e:
            # Do NOT fail the whole job due to one coin
            print(f"[WARN] coin_detail failed for {coin_id}: {e}")
            detail = {}

        s = sopx_score_coin(row, detail, cfg, overrides)
        scores.append(s)

    date_utc = sopx_utc_today_str()
    sopx_append_history(scores, date_utc)

    trends = sopx_compute_trends(scores, weeks_lookback=7)
    movers_up, movers_down, flags = trends

    report_dir = cfg["output"]["report_dir"]
    md_path, json_path, ts = sopx_write_reports(
        scores, report_dir, trends=trends
    )

    top_n = cfg["output"]["top_to_post"]
    top_md = sopx_make_markdown(scores, top_n=top_n)

    movers_line = ""
    if movers_up:
        _, name, sym, delta, _ = movers_up[0]
        movers_line = f"\n最大上升（7w）：{name}({(sym or '').upper()}) Δ{delta:+.2f}"
    if movers_down:
        _, name, sym, delta, _ = movers_down[0]
        movers_line += f"\n最大下降（7w）：{name}({(sym or '').upper()}) Δ{delta:+.2f}"

    flag_line = f"\nDrift flags：{len(flags)}"

    header = (
        f"【Weekly SOPX Scores】Top {top_n}｜{ts} UTC"
        f"{movers_line}{flag_line}\n"
    )
    note = (
        "\n(Scoring = SOP-Quant proxy + curated_facts + plugin rules; "
        "full report in repo)\n"
    )

    content = header + "```\n" + top_md + "\n```\n" + note

    max_chars = cfg["plurk"]["max_chars"]
    if len(content) > max_chars:
        top_md_small = sopx_make_markdown(scores, top_n=min(5, top_n))
        content = header + "```\n" + top_md_small + "\n```\n" + note
        content = content[: max_chars - 5] + "…"

    ck = os.getenv("PLURK_CONSUMER_KEY")
    cs = os.getenv("PLURK_CONSUMER_SECRET")
    at = os.getenv("PLURK_ACCESS_TOKEN")
    ats = os.getenv("PLURK_ACCESS_TOKEN_SECRET")

    if all([ck, cs, at, ats]):
        sopx_post_plurk(content, ck, cs, at, ats)
        print("Posted main report to Plurk.")
    else:
        print("Plurk secrets missing; skipping main post.")
        print(content)

    # --- SECOND POST: Drift Alert ---
    if all([ck, cs, at, ats]) and flags:
        alert_post = sopx_build_drift_alert_post(flags, ts, max_items=5)
        if alert_post:
            try:
                sopx_post_plurk(alert_post, ck, cs, at, ats)
                print("Posted drift alert to Plurk.")
            except Exception as e:
                print("Failed to post drift alert:", e)


if __name__ == "__main__":
    main()
