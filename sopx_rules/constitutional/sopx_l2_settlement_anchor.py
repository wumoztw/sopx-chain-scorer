from ..sopx_rule_base import SopxBaseRule, SopxRuleResult

class Rule(SopxBaseRule):
    name = "sopx_l2_settlement_anchor"

    def evaluate(self, market_row: dict, detail: dict, context: dict) -> SopxRuleResult:
        coin_id = market_row.get("id")
        overrides = context.get("overrides", {})
        ov = (overrides.get("overrides") or {}).get(coin_id, {})
        tags = ov.get("tags") or []

        if "Settlement" in tags or "Civilization-Layer" in tags:
            return SopxRuleResult(score=95, reason="Manual tag: settlement/civilization anchor", meta={"tags": tags})

        return SopxRuleResult(score=35, reason="Not identified as settlement anchor", meta={"tags": tags})
