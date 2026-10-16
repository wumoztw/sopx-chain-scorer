import argparse

import os
import yaml

from config import AppConfig
from sopx_coingecko import SopxCoinGeckoClient
from sopx_scorer import sopx_score_coin
from sopx_report import sopx_write_reports
from sopx_history import (
    sopx_append_history,
    sopx_compute_trends,
    sopx_utc_today_str,
)
from sopx_plurk import sopx_post_plurk
from sopx_dashboard import sopx_make_dashboard


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
    Investor-friendly Plurk output containing top tokens and Streamlit dashboard link.
    """
    flags = flags or []
    sorted_scores = sorted(scores, key=lambda x: x["total"], reverse=True)
    
    hold = []
    rotate = []
    for s in sorted_scores:
        act = sopx_action_label(s)
        if act == "HOLD":
            hold.append(s.get("symbol", "").upper())
        elif act == "ROTATE":
            rotate.append(s.get("symbol", "").upper())

    # Build the message
    lines = []
    lines.append(f"【Weekly SOPX｜量化評分週報】{ts} UTC")
    lines.append("")
    
    hold_str = ", ".join(hold[:3]) if hold else "無"
    lines.append(f"🧱 長期核心 (HOLD): {hold_str}")
    
    rotate_str = ", ".join(rotate[:4]) if rotate else "無"
    lines.append(f"🏗 成長配置 (ROTATE): {rotate_str}")
    
    if flags:
        lines.append(f"⚠️ 本週有 {len(flags)} 個結構警訊，請特別留意！")
    
    lines.append("")
    lines.append("📊 完整數據與歷史趨勢儀表板：")
    lines.append("https://sopx-chain-scorer.streamlit.app/")
    
    msg = "\n".join(lines)
    
    # Fallback to shorter text if exceeds character limit
    if len(msg) > max_chars:
        lines = [
            f"【Weekly SOPX｜量化評分週報】{ts} UTC",
            "",
            f"🧱 HOLD: {', '.join(hold[:2]) if hold else '無'}",
            f"🏗 ROTATE: {', '.join(rotate[:2]) if rotate else '無'}",
            "",
            "📊 完整數據與趨勢儀表板：",
            "https://sopx-chain-scorer.streamlit.app/"
        ]
        msg = "\n".join(lines)
        if len(msg) > max_chars:
            msg = msg[:max_chars]
            
    return msg


# ---------- main ----------
def main(argv=None):
    parser = argparse.ArgumentParser(description="Score CoinGecko market data")
    parser.add_argument("-c", "--config", default="config.yml", help="path to YAML config file (default: config.yml)")
    parser.add_argument("--limit", "-n", type=int, default=None, help="limit final output and scoring currency count")
    parser.add_argument("--top-stage1", type=int, default=None, help="override Stage 2 candidate count from Stage 1 (overrides config stage2_candidates)")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Stage 2 parallel fetch thread count (default: 4)")
    parser.add_argument("--no-cache", action="store_true", help="bypass local CoinGecko cache")
    parser.add_argument("--output-dir", default=None, help="custom report output directory (default: reports)")
    args = parser.parse_args(argv)

    cfg: AppConfig = AppConfig.from_yaml(args.config)
    overrides = sopx_load_yaml("manual_overrides.yml")

    # CLI overrides for config values
    if args.top_stage1 is not None:
        cfg.stage2.stage2_candidates = args.top_stage1
    if args.output_dir is not None:
        cfg.output.report_dir = args.output_dir

    cg = SopxCoinGeckoClient(
        delay_sec=cfg.coingecko.request_delay_sec,
        cache_enabled=not args.no_cache,
    )
    markets = cg.top_markets(
        vs_currency=cfg.coingecko.vs_currency,
        per_page=cfg.coingecko.top_n,
        page=1,
    )

    # ---------- Stage 1: fast scoring ----------
    stage1_scores = []
    for row in markets:
        s = sopx_score_coin(row, {}, cfg, overrides)
        stage1_scores.append(s)

    # Apply --limit to stage1 candidates if provided
    if args.limit is not None:
        stage1_scores = stage1_scores[: args.limit]

    # ---------- Stage 2 selection ----------
    if args.top_stage1 is not None:
        stage2_top_n = args.top_stage1
    else:
        stage2_top_n = cfg.stage2.detail_top_n if cfg.stage2.detail_top_n is not None else cfg.stage2.stage2_candidates
    stage2_extra_n = cfg.stage2.detail_extra_n

    by_total = sorted(stage1_scores, key=lambda x: x["total"], reverse=True)
    by_rank = sorted(stage1_scores, key=lambda x: x.get("rank") or 999)

    candidate_ids = {s["id"] for s in by_total[:stage2_top_n]}
    candidate_ids |= {s["id"] for s in by_rank[:stage2_extra_n]}

    score_by_id = {s["id"]: s for s in stage1_scores}

    # Stage 2 parallel detail fetching
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_detail(row):
        cid = row["id"]
        if cid not in candidate_ids:
            return cid, None
        try:
            detail = cg.coin_detail(cid)
            s2 = sopx_score_coin(row, detail, cfg, overrides)
            return cid, s2
        except Exception as e:
            print(f"[WARN] coin_detail failed for {cid}: {e}")
            return cid, None

    rows = [r for r in markets if r["id"] in candidate_ids]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_cid = {executor.submit(_fetch_detail, row): row["id"] for row in rows}
        for future in as_completed(future_to_cid):
            cid, s2 = future.result()
            if s2 is not None:
                score_by_id[cid] = s2

    final_scores = list(score_by_id.values())

    # Apply --limit to final output if provided
    if args.limit is not None:
        final_scores = sorted(final_scores, key=lambda x: x["total"], reverse=True)[: args.limit]

    # ---------- History & trends ----------
    date_utc = sopx_utc_today_str()
    sopx_append_history(final_scores, date_utc)
    movers_up, movers_down, flags = sopx_compute_trends(final_scores, weeks_lookback=7)

    # ---------- Reports ----------
    sopx_write_reports(final_scores, cfg.output.report_dir, trends=(movers_up, movers_down, flags))

    # ---------- Dashboard ----------
    dashboard_path = sopx_make_dashboard(final_scores, cfg.output.report_dir)
    print(f"Dashboard generated: {dashboard_path}")

    # ---------- Plurk ----------
    ck = os.getenv("PLURK_CONSUMER_KEY")
    cs = os.getenv("PLURK_CONSUMER_SECRET")
    at = os.getenv("PLURK_ACCESS_TOKEN")
    ats = os.getenv("PLURK_ACCESS_TOKEN_SECRET")

    if all([ck, cs, at, ats]):
        max_chars = cfg.plurk.max_chars
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

    # ---------- Generate Dashboard ----------
    try:
        from sopx_dashboard_generator import generate_html_dashboard
        generate_html_dashboard()
    except Exception as e:
        print(f"[WARN] Failed to generate HTML dashboard: {e}")


if __name__ == "__main__":
    main()
