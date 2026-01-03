from ..sopx_rule_base import SopxBaseRule, SopxRuleResult

class Rule(SopxBaseRule):
    name = "sopx_governance_admin_risk"

    def evaluate(self, market_row: dict, detail: dict, context: dict) -> SopxRuleResult:
        base = 55
        categories = detail.get("categories") or []
        platforms = detail.get("platforms") or {}

        if "Centralized Exchange Token" in categories:
            base -= 15

        if platforms and "ethereum" in platforms and len(platforms.keys()) == 1:
            base += 5

        score = max(0, min(100, base))
        return SopxRuleResult(score=score, reason="Admin/neutrality risk proxy (heuristic)", meta={"categories": categories})
