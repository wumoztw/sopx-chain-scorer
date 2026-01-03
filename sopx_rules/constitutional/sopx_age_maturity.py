from datetime import datetime
from dateutil.parser import isoparse
from ..sopx_rule_base import SopxBaseRule, SopxRuleResult

class Rule(SopxBaseRule):
    name = "sopx_age_maturity"

    def evaluate(self, market_row: dict, detail: dict, context: dict) -> SopxRuleResult:
        gd = detail.get("genesis_date")
        if not gd:
            return SopxRuleResult(score=35, reason="No genesis_date; assume young/unknown", meta={})
        try:
            d = isoparse(gd).date()
            yrs = (datetime.utcnow().date() - d).days / 365.25
            score = min(100, max(0, yrs * 12.5))  # ~8y -> 100
            return SopxRuleResult(score=score, reason=f"Age≈{yrs:.1f}y", meta={"age_years": yrs})
        except Exception:
            return SopxRuleResult(score=35, reason="Bad genesis_date format", meta={})
