import os
import csv
from datetime import datetime, timezone
from collections import defaultdict

SOPX_HISTORY_PATH = "reports/history.csv"

SOPX_FIELDS = [
    "date_utc", "id", "symbol", "name", "rank",
    "constitutional", "demand", "capture", "risk", "total",
    "market_cap", "vol_to_mcap"
]

def sopx_ensure_reports_dir():
    os.makedirs("reports", exist_ok=True)

def sopx_utc_today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def sopx_append_history(scores: list, date_utc: str):
    sopx_ensure_reports_dir()
    exists = os.path.exists(SOPX_HISTORY_PATH)

    with open(SOPX_HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SOPX_FIELDS)
        if not exists:
            w.writeheader()

        for s in scores:
            row = {k: "" for k in SOPX_FIELDS}
            row.update({
                "date_utc": date_utc,
                "id": s["id"],
                "symbol": s.get("symbol") or "",
                "name": s.get("name") or "",
                "rank": s.get("rank") or "",
                "constitutional": s.get("constitutional"),
                "demand": s.get("demand"),
                "capture": s.get("capture"),
                "risk": s.get("risk"),
                "total": s.get("total"),
                "market_cap": s.get("market_cap") or 0,
                "vol_to_mcap": s.get("vol_to_mcap") or 0,
            })
            w.writerow(row)

def sopx_load_history():
    if not os.path.exists(SOPX_HISTORY_PATH):
        return []
    rows = []
    with open(SOPX_HISTORY_PATH, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows

def sopx_to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def sopx_compute_trends(current_scores: list, weeks_lookback: int = 7):
    hist = sopx_load_history()
    by_id = defaultdict(list)
    for row in hist:
        by_id[row["id"]].append(row)

    for cid in by_id:
        by_id[cid].sort(key=lambda r: r["date_utc"])

    movers = []
    drift_flags = []

    for s in current_scores:
        cid = s["id"]
        series = by_id.get(cid, [])
        if len(series) < 2:
            continue

        past = series[-(weeks_lookback+1)] if len(series) >= (weeks_lookback+1) else series[0]
        past_total = sopx_to_float(past.get("total"))
        delta = float(s["total"]) - past_total

        movers.append((cid, s["name"], s.get("symbol",""), delta, s["total"]))

        past_const = sopx_to_float(past.get("constitutional"))
        past_risk = sopx_to_float(past.get("risk"))
        const_drop = past_const - float(s["constitutional"])
        risk_jump = float(s["risk"]) - past_risk

        if const_drop >= 15:
            drift_flags.append((cid, s["name"], "Constitutional drop", const_drop))
        if risk_jump >= 25:
            drift_flags.append((cid, s["name"], "Risk spike", risk_jump))

    movers_up = sorted(movers, key=lambda x: x[3], reverse=True)[:10]
    movers_down = sorted(movers, key=lambda x: x[3])[:10]

    return movers_up, movers_down, drift_flags
