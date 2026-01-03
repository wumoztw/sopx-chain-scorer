from sopx_rules.sopx_rule_engine import sopx_run_rule_set

def sopx_clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def sopx_safe_div(a, b):
    if not b:
        return 0.0
    return a / b

def sopx_score_coin(market_row: dict, detail: dict, cfg: dict, overrides: dict):
    md = (detail or {}).get("market_data") or {}
    dev = (detail or {}).get("developer_data") or {}
    com = (detail or {}).get("community_data") or {}

    coin_id = market_row.get("id")
    mcap = market_row.get("market_cap") or md.get("market_cap", {}).get("usd") or 0
    vol = market_row.get("total_volume") or md.get("total_volume", {}).get("usd") or 0
    vol_to_mcap = sopx_safe_div(vol, mcap)
    rank = market_row.get("market_cap_rank") or 999

    # --- Constitutional (plugin rules) ---
    rule_cfg = cfg.get("rules", {}).get("constitutional", {})
    enabled = rule_cfg.get("enabled", [])
    weights = rule_cfg.get("weights", {})

    context = {"overrides": overrides, "cfg": cfg}
    constitutional, constitutional_breakdown = sopx_run_rule_set(
        rule_group="constitutional",
        enabled=enabled,
        weights=weights,
        market_row=market_row,
        detail=detail,
        context=context
    )

    ov = (overrides or {}).get("overrides", {}).get(coin_id, {})
    constitutional_bonus = ov.get("constitutional_bonus", 0)
    tags = ov.get("tags", [])[:]  # copy
    constitutional = sopx_clamp(constitutional + constitutional_bonus)

    # Enrich tags from curated meta
    cf_meta = (constitutional_breakdown.get("sopx_curated_facts") or {}).get("meta") or {}
    if cf_meta:
        layer = cf_meta.get("layer")
        anchor = cf_meta.get("settlement_anchor")
        thesis = cf_meta.get("thesis")
        flags = cf_meta.get("risk_flags") or []

        if layer:
            tags.append(f"layer:{layer}")
        if anchor and anchor != "none":
            tags.append(f"anchor:{anchor}")
        if thesis:
            tags.append(f"thesis:{thesis}")
        for f in flags[:3]:
            tags.append(f"flag:{f}")

    # dedupe tags preserving order
    seen = set()
    tags2 = []
    for t in tags:
        if t not in seen:
            tags2.append(t)
            seen.add(t)
    tags = tags2

    # --- Demand proxy ---
    liq_score = sopx_clamp((vol_to_mcap / 0.10) * 100)

    twitter = com.get("twitter_followers") or 0
    reddit = com.get("reddit_subscribers") or 0
    community_score = sopx_clamp(((twitter/2_000_000) + (reddit/500_000)) * 50)

    chg_7d = market_row.get("price_change_percentage_7d_in_currency")
    if chg_7d is None:
        chg_7d = 0.0
    momentum_score = sopx_clamp(50 + chg_7d)

    demand = sopx_clamp(0.45 * liq_score + 0.30 * community_score + 0.25 * momentum_score)

    # --- Capture proxy ---
    max_supply = md.get("max_supply")
    total_supply = md.get("total_supply")
    circ_supply = md.get("circulating_supply")

    supply_info = 0
    supply_info += 1 if max_supply else 0
    supply_info += 1 if total_supply else 0
    supply_info += 1 if circ_supply else 0
    supply_score = sopx_clamp((supply_info / 3) * 100)

    inflation_penalty = 0
    if not max_supply and total_supply:
        inflation_penalty = 10
    elif not max_supply and not total_supply:
        inflation_penalty = 20

    capture = sopx_clamp(supply_score - inflation_penalty)

    # --- Risk penalties ---
    missing_dev_pen = cfg["scoring"]["veto"]["missing_dev_data_penalty"] if dev.get("commit_count_4_weeks") is None else 0
    liq_pen = 20 if vol_to_mcap < cfg["scoring"]["veto"]["min_volume_to_mcap"] else 0
    small_pen = 20 if mcap < cfg["scoring"]["veto"]["min_market_cap_usd"] else 0
    risk = sopx_clamp(missing_dev_pen + liq_pen + small_pen)

    # --- Total ---
    w = cfg["scoring"]["weights"]
    total = (
        w["constitutional"] * constitutional +
        w["demand"] * demand +
        w["capture"] * capture -
        w["risk"] * (risk / 100) * 100
    )
    total = sopx_clamp(total)

    return {
        "id": coin_id,
        "symbol": market_row.get("symbol"),
        "name": market_row.get("name"),
        "rank": rank,
        "market_cap": mcap,
        "vol_to_mcap": vol_to_mcap,
        "constitutional": round(constitutional, 2),
        "constitutional_breakdown": constitutional_breakdown,
        "demand": round(demand, 2),
        "capture": round(capture, 2),
        "risk": round(risk, 2),
        "total": round(total, 2),
        "tags": tags,
    }
