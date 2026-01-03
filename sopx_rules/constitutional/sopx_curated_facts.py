import yaml
from ..sopx_rule_base import SopxBaseRule, SopxRuleResult

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

LAYER_SCORE = {
    "civilization": 95,
    "regional": 75,
    "application": 50,
    "narrative": 25,
    "unknown": 45,
}

ANCHOR_BONUS = {
    "global": 15,
    "regional": 7,
    "none": 0,
    "unknown": 0,
}

DECENTRALIZATION_ADJ = {
    "high": 8,
    "medium": 0,
    "low": -10,
    "unknown": -2,
}

ADMIN_RISK_ADJ = {
    "low": 6,
    "medium": 0,
    "high": -12,
    "unknown": -2,
}

EXIT_TEST_ADJ = {
    True: 8,
    False: -10,
    "partial": 0,
    "unknown": -2,
}

RISK_FLAG_PENALTY = {
    "admin_key": 10,
    "single_sequencer": 8,
    "frequent_upgrades": 4,
    "opaque_tokenomics": 6,
    "high_centralization": 10,
    "regulatory_dependency": 6,
    "bridge_risk": 6,
    "low_liquidity": 5,
    "heavy_incentives": 6,
    "security_incidents": 10,
    "weak_exit_paths": 7,
}

COMPOUND_PENALTIES = [
    ({"admin_key", "single_sequencer"}, 6),
    ({"high_centralization", "admin_key"}, 6),
    ({"bridge_risk", "weak_exit_paths"}, 4),
]

class Rule(SopxBaseRule):
    name = "sopx_curated_facts"
    _cache = None

    def _load_dataset(self, path: str):
        if Rule._cache is not None:
            return Rule._cache
        with open(path, "r", encoding="utf-8") as f:
            Rule._cache = yaml.safe_load(f) or {}
        return Rule._cache

    def evaluate(self, market_row: dict, detail: dict, context: dict) -> SopxRuleResult:
        cfg = context.get("cfg", {})
        ds_cfg = cfg.get("dataset", {})
        path = ds_cfg.get("curated_path", "curated_dataset.yml")

        ds = self._load_dataset(path)
        coins = (ds.get("coins") or {})
        defaults = (ds.get("defaults") or {})
        coin_id = market_row.get("id")

        entry = coins.get(coin_id)
        if not entry:
            return SopxRuleResult(score=45, reason="No curated entry; fallback", meta={})

        layer = entry.get("layer", "unknown")
        anchor = entry.get("settlement_anchor", "unknown")
        decentral = entry.get("decentralization", "unknown")
        admin_risk = entry.get("admin_risk", "unknown")
        exit_test = entry.get("exit_test", "unknown")

        thesis = entry.get("thesis", "narrative")
        review_interval_weeks = entry.get("review_interval_weeks", defaults.get("default_review_interval_weeks", 8))

        risk_flags = entry.get("risk_flags") or []
        risk_flags_set = set(risk_flags)

        score = LAYER_SCORE.get(layer, 45)
        score += ANCHOR_BONUS.get(anchor, 0)
        score += DECENTRALIZATION_ADJ.get(decentral, -2)
        score += ADMIN_RISK_ADJ.get(admin_risk, -2)

        if exit_test in (True, False):
            score += EXIT_TEST_ADJ[exit_test]
        else:
            score += EXIT_TEST_ADJ.get(exit_test, -2)

        penalties = 0
        for f in risk_flags:
            penalties += RISK_FLAG_PENALTY.get(f, 3)

        for combo, p in COMPOUND_PENALTIES:
            if combo.issubset(risk_flags_set):
                penalties += p

        score = clamp(score - penalties)

        reason = (
            f"curated: layer={layer}, anchor={anchor}, dec={decentral}, admin={admin_risk}, exit={exit_test}, "
            f"thesis={thesis}, flags={len(risk_flags)}"
        )
        meta = {
            "layer": layer,
            "settlement_anchor": anchor,
            "decentralization": decentral,
            "admin_risk": admin_risk,
            "exit_test": exit_test,
            "thesis": thesis,
            "review_interval_weeks": review_interval_weeks,
            "risk_flags": risk_flags,
            "penalties": penalties,
        }
        return SopxRuleResult(score=score, reason=reason, meta=meta)
