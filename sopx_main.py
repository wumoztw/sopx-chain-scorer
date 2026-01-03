import os
import yaml

from sopx_coingecko import SopxCoinGeckoClient
from sopx_scorer import sopx_score_coin
from sopx_report import sopx_write_reports
from sopx_history import (
    sopx_append_history,
    sopx_compute_trends,
    sopx_utc_today_str,
)
from sopx_plurk import sopx_post_plurk


# ---------- helpers ----------
def sopx_load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sopx_get_tag_value(tags, prefix):
    if not tags:
        return None
    for t in tags:
        if isinstance(t, str) and t.startswith(prefix):
            return t.split(":", 1)[1].strip()
    return None


def sopx_action_label(s):
    """
    Decide investor action automatically.
    """
    c = float(s.get("constitutional") or 0)
    total = float(s.get("total") or 0)
    layer = sopx_get_tag_value(s.get("tags", []), "layer:")
    thesis = sopx_get_tag_value(s.get("tags", []), "thesis:")
    risk = float(s.get("risk") or 0)

    # Hard avoid conditions
    if risk >= 40:
        return "AVOID"

    # Long-term anchors
    if c >= 85 or layer == "civilization":
        return "HOLD"

    # Growth / rotation candidates
    if (c >= 55 and thesis != "narrative") or layer == "regional":
        return "ROTATE"

    # Everything else = trading only
    return "TRADE"


def sopx_fmt_line(s):
    sym = (s.get("symbol") or "").upper()
    total = float(s.get("total") or 0)
    c = float(s.get("constitutional") or 0)
    action = sopx_action_label(s)
    return f"• {sym}｜總 {total:.1f}｜制 {c:.0f}｜{action}"


def sopx_build_investor_plurk_post(scores, ts, flags=None, max_chars=320):
    flags = flags or []

    # Sort by total score
    sorted_scores = sorted(scores, key=lambda x: x["total"], reverse=True)

    # Buckets
    hold = []
    rotate = []
    trade = []
    avoid = []

    for s in sorted_scores:
        act = sopx_action_label(s)
        if act == "HOLD":
            hold.append(s)
        elif act == "ROTATE":
            rotate.append(s)
        elif act == "TRADE":
            trade.append(s)
        else:
            avoid.append(s)

    # Caps (to keep message readable)
    hold = hold[:3]
    rotate = rotate[:4]
    trade = trade[:4]
    avoid = avoid[:3]

    lines = []
    lines.append(f"【Weekly SOPX｜投資人版】{ts} UTC")

    # HOLD
    lines.append("")
    lines.append("🧱 長期核心（HOLD）")
    if hold:
        for s in hold:
            lines.append(sopx_fmt_line(s))
    else:
        lines.append("• 無")

    # ROTATE
    lines.append("")
    lines.append("🏗 成長配置（ROTATE）")
    if rotate:
        for s in rotate:
            lines.append(sopx_fmt_line(s))
    else:
        lines.append("• 無")

    # TRADE
    lines.append("")
    lines.append("🎭 高波動交易（TRADE）")
    if trade:
        for s in trade:
            lines.append(sopx_fmt_line(s))
    else:
        lines.append("• 無")

    # AVOID
    if avoid:
        lines.append("")
        lines.append("⛔ 結構風險（AVOID）")
        for s in avoid:
            lines.append(sopx_fmt_line(s))

    # Drift flags
    if flags:
        lines.append("")
        lines.append("⚠️ 本週結構警訊")
        for i, (_, name, kind, v) in enumerate(flags[:3], 1):
            lines.append(f"{i}. {name}｜{kind} ({v:+.1f})")

    lines.append("")
    lines.append("（SOPX＝制度×需求×捕獲－風險｜非投資建議）")

    msg = "\n".join(lines)

    # Hard safety: shrink if too long
    if len(msg) > max_chars:
        msg = "\n".join(lines[:18])
        msg = msg[:max_chars]

    return msg


# ---------- main ----------
def main():
    cfg = sopx_load_yaml("config.yml")
    overrides = sopx_load_yaml("manual_overrides.yml")

    cg = SopxCoinGeckoClient(delay_sec=cfg["coingecko"]["request_delay_sec"])

    markets = cg.top_markets(
        vs_currency=cfg["coingecko"]["vs_currency"],
        per_page=cfg["coingecko"]["top_n"],
        page=1,
    )

    # ---------- Stage 1: fast scoring ----------
    stage1_scores = []
    for row in markets:
        s = sopx_score_coin(row, {}, cfg, overrides)
        stage1_scores.append(s)

    # ---------- Stage 2 selection ----------
    stage2_top_n = cfg.get("stage2", {}).get("detail_top_n", 20)
    stage2_extra_n = cfg.get("stage2", {}).get("detail_extra_n", 10)

    by_total = sorted(stage1_scores, key=lambda x: x["total"], reverse=True)
    by_rank = sorted(stage1_scores, key=lambda x: x.get("rank") or 999)

    candidate_ids = {s["id"] for s in by_total[:stage2_top_n]}
    candidate_ids |= {s["id"] for s in by_rank[:stage2_extra_n]}

    score_by_id = {s["id"]: s for s in stage1_scores}

    for row in markets:
        cid = row["id"]
        if cid not in candidate_ids:
            continue
        try:
            detail = cg.coin_detail(cid)
        except Exception as e:
            print(f"[WARN] coin_detail failed for {cid}: {e}")
            continue
        s2 = sopx_score_coin(row, detail, cfg, overrides)
        score_by_id[cid] = s2

    final_scores = list(score_by_id.values())

    # ---------- History & trends ----------
    date_utc = sopx_utc_today_str()
    sopx_append_history(final_scores, date_utc)
    movers_up, movers_down, flags = sopx_compute_trends(final_scores, weeks_lookback=7)

    # ---------- Reports ----------
    sopx_write_reports(final_scores, cfg["output"]["report_dir"], trends=(movers_up, movers_down, flags))

    # ---------- Plurk ----------
    ck = os.getenv("PLURK_CONSUMER_KEY")
    cs = os.getenv("PLURK_CONSUMER_SECRET")
    at = os.getenv("PLURK_ACCESS_TOKEN")
    ats = os.getenv("PLURK_ACCESS_TOKEN_SECRET")

    if all([ck, cs, at, ats]):
        msg = sopx_build_investor_plurk_post(
            final_scores,
            date_utc,
            flags=flags,
            max_chars=cfg["plurk"]["max_chars"],
        )
        res = sopx_post_plurk(msg, ck, cs, at, ats)
        if res:
            print("Posted investor-style SOPX report to Plurk.")
        else:
            print("[WARN] Plurk post failed (non-fatal).")
    else:
        print("Plurk secrets missing; skipping Plurk post.")


if __name__ == "__main__":
    main()
