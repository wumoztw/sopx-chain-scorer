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


def sopx_load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sopx_build_compact_top_post(scores, ts, top_n=10, max_chars=320):
    """
    Plurk tends to reject long / special formatted content.
    Keep it compact: plain text, short lines.
    """
    top = sorted(scores, key=lambda x: x["total"], reverse=True)[:top_n]
    lines = [f"【Weekly SOPX】Top {top_n}｜{ts} UTC"]

    for i, s in enumerate(top, 1):
        sym = (s.get("symbol") or "").upper()
        total = s["total"]
        const = s["constitutional"]
        lines.append(f"{i}. {sym} {total:.1f} (C{const:.0f})")

    msg = "\n".join(lines)
    if len(msg) > max_chars:
        # fallback: fewer items
        top2 = top[:5]
        lines = [f"【Weekly SOPX】Top 5｜{ts} UTC"]
        for i, s in enumerate(top2, 1):
            sym = (s.get("symbol") or "").upper()
            total = s["total"]
            const = s["constitutional"]
            lines.append(f"{i}. {sym} {total:.1f} (C{const:.0f})")
        msg = "\n".join(lines)
        msg = msg[:max_chars]
    return msg


def sopx_build_drift_alert_post(flags, ts, max_items=5, max_chars=320):
    if not flags:
        return None

    lines = [f"⚠️ SOPX Drift Alert｜{ts} UTC", "制度/風險漂移（前{}）：".format(min(max_items, len(flags)))]
    for i, (_, name, kind, v) in enumerate(flags[:max_items], 1):
        lines.append(f"{i}. {name} - {kind} ({v:+.1f})")

    lines.append("建議：查治理/admin key、應用遷移、補貼退潮（非投資建議）")
    msg = "\n".join(lines)
    return msg[:max_chars]


def main():
    cfg = sopx_load_yaml("config.yml")
    overrides = sopx_load_yaml("manual_overrides.yml")

    # ---------- Two-stage settings (safe defaults) ----------
    stage2_top_n = cfg.get("stage2", {}).get("detail_top_n", 20)         # only fetch details for top N
    stage2_extra_n = cfg.get("stage2", {}).get("detail_extra_n", 10)     # plus some extra by market cap
    plurk_max_chars = cfg.get("plurk", {}).get("max_chars", 320)
    if plurk_max_chars > 600:
        # Plurk often rejects long content; hard cap for safety
        plurk_max_chars = 320

    cg = SopxCoinGeckoClient(delay_sec=cfg["coingecko"]["request_delay_sec"])

    markets = cg.top_markets(
        vs_currency=cfg["coingecko"]["vs_currency"],
        per_page=cfg["coingecko"]["top_n"],
        page=1,
    )

    # ---------- Stage 1: fast scoring with NO /coins/{id} ----------
    stage1_scores = []
    for row in markets:
        # detail={} -> scorer will fall back to proxies + curated/manual
        s = sopx_score_coin(row, {}, cfg, overrides)
        stage1_scores.append(s)

    # Pick candidates for Stage 2 detail fetch:
    # 1) top by stage1 score
    stage1_sorted = sorted(stage1_scores, key=lambda x: x["total"], reverse=True)
    top_ids = {s["id"] for s in stage1_sorted[:stage2_top_n]}

    # 2) add extra by market cap rank (to avoid missing important majors that stage1 under-scores)
    by_rank = sorted(stage1_scores, key=lambda x: x.get("rank") or 999)
    extra_ids = {s["id"] for s in by_rank[:stage2_extra_n]}

    candidate_ids = set().union(top_ids).union(extra_ids)

    # ---------- Stage 2: fetch details only for candidates ----------
    score_by_id = {s["id"]: s for s in stage1_scores}

    for row in markets:
        coin_id = row["id"]
        if coin_id not in candidate_ids:
            continue

        try:
            detail = cg.coin_detail(coin_id)
        except Exception as e:
            print(f"[WARN] coin_detail failed for {coin_id}: {e} (keep stage1 score)")
            continue

        s2 = sopx_score_coin(row, detail, cfg, overrides)
        score_by_id[coin_id] = s2

    final_scores = list(score_by_id.values())

    # ---------- History + trends ----------
    date_utc = sopx_utc_today_str()
    sopx_append_history(final_scores, date_utc)

    trends = sopx_compute_trends(final_scores, weeks_lookback=7)
    movers_up, movers_down, flags = trends

    # ---------- Reports ----------
    report_dir = cfg["output"]["report_dir"]
    sopx_write_reports(final_scores, report_dir, trends=trends)

    # ---------- Plurk posting (safe + compact) ----------
    ck = os.getenv("PLURK_CONSUMER_KEY")
    cs = os.getenv("PLURK_CONSUMER_SECRET")
    at = os.getenv("PLURK_ACCESS_TOKEN")
    ats = os.getenv("PLURK_ACCESS_TOKEN_SECRET")

    if all([ck, cs, at, ats]):
        main_post = sopx_build_compact_top_post(final_scores, date_utc, top_n=10, max_chars=plurk_max_chars)
        res1 = sopx_post_plurk(main_post, ck, cs, at, ats)
        if res1:
            print("Posted main report to Plurk.")
        else:
            print("[WARN] Main Plurk post failed (non-fatal).")

        # second alert post
        if flags:
            alert_post = sopx_build_drift_alert_post(flags, date_utc, max_items=5, max_chars=plurk_max_chars)
            if alert_post:
                res2 = sopx_post_plurk(alert_post, ck, cs, at, ats)
                if res2:
                    print("Posted drift alert to Plurk.")
                else:
                    print("[WARN] Drift alert Plurk post failed (non-fatal).")
    else:
        print("Plurk secrets missing; skipping Plurk posts.")


if __name__ == "__main__":
    main()
