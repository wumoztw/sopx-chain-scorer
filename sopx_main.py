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
    """
    Investor-friendly Plurk output with stable formatting.
    Never slices mid-text (except ultra fallback end-trim), so newlines won't break.
    """
    flags = flags or []

    def build_with_caps(hold_cap, rotate_cap, trade_cap, avoid_cap, flag_cap):
        # Sort by total score
        sorted_scores = sorted(scores, key=lambda x: x["total"], reverse=True)

        hold, rotate, trade, avoid = [], [], [], []
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

        hold = hold[:hold_cap]
        rotate = rotate[:rotate_cap]
        trade = trade[:trade_cap]
        avoid = avoid[:avoid_cap]
        show_flags = flags[:flag_cap] if flags else []

        lines = []
        lines.append(f"【Weekly SOPX｜投資人版】{ts} UTC")

        lines.append("")
        lines.append("🧱 長期核心（HOLD）")
        if hold:
            for s in hold:
                lines.append(sopx_fmt_line(s))
        else:
            lines.append("• 無")

        lines.append("")
        lines.append("🏗 成長配置（ROTATE）")
        if rotate:
            for s in rotate:
                lines.append(sopx_fmt_line(s))
        else:
            lines.append("• 無")

        lines.append("")
        lines.append("🎭 高波動交易（TRADE）")
        if trade:
            for s in trade:
                lines.append(sopx_fmt_line(s))
        else:
            lines.append("• 無")

        if avoid:
            lines.append("")
            lines.append("⛔ 結構風險（AVOID）")
            for s in avoid:
                lines.append(sopx_fmt_line(s))

        if show_flags:
            lines.append("")
            lines.append("⚠️ 本週結構警訊")
            for i, (_, name, kind, v) in enumerate(show_flags, 1):
                lines.append(f"{i}. {name}｜{kind} ({v:+.1f})")

        lines.append("")
        lines.append("（SOPX＝制度×需求×捕獲－風險｜非投資建議）")

        return "\n".join(lines)

    # Start caps (the “nice” version)
    msg = build_with_caps(3, 4, 4, 3, 3)

    # If too long, progressively shrink by reducing items (never by slicing the string)
    shrink_steps = [
        (3, 4, 3, 2, 2),
        (2, 3, 3, 2, 2),
        (2, 3, 2, 1, 2),
        (2, 2, 2, 1, 1),
        (1, 2, 2, 0, 1),
        (1, 1, 2, 0, 0),
        (1, 1, 1, 0, 0),
    ]

    if len(msg) > max_chars:
        for caps in shrink_steps:
            msg2 = build_with_caps(*caps)
            if len(msg2) <= max_chars:
                return msg2

        # Ultra-compact fallback with guaranteed newlines
        sorted_scores = sorted(scores, key=lambda x: x["total"], reverse=True)
        ultra = []
        ultra.append(f"【Weekly SOPX｜投資人版】{ts} UTC")
        ultra.append("")

        def pick_syms(act, n):
            out = []
            for s in sorted_scores:
                if sopx_action_label(s) == act:
                    out.append((s.get("symbol") or "").upper())
                if len(out) >= n:
                    break
            return out

        ultra.append("🧱 HOLD：" + (", ".join(pick_syms("HOLD", 2)) or "無"))
        ultra.append("🏗 ROTATE：" + (", ".join(pick_syms("ROTATE", 2)) or "無"))
        ultra.append("🎭 TRADE：" + (", ".join(pick_syms("TRADE", 3)) or "無"))
        if flags:
            _, name, kind, _ = flags[0]
            ultra.append(f"⚠️ 警訊：{name}({kind})")
        ultra.append("（非投資建議）")

        msg3 = "\n".join(ultra)

        # final safeguard (rare): trim only at the very end
        if len(msg3) > max_chars:
            msg3 = msg3[:max_chars]
        return msg3

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
        max_chars = cfg.get("plurk", {}).get("max_chars", 320)
        if max_chars > 600:
            max_chars = 320  # keep safe for Plurk

        msg = sopx_build_investor_plurk_post(
            final_scores,
            date_utc,
            flags=flags,
            max_chars=max_chars,
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
