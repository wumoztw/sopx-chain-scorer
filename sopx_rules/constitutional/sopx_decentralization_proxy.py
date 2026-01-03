from ..sopx_rule_base import SopxBaseRule, SopxRuleResult

class Rule(SopxBaseRule):
    name = "sopx_decentralization_proxy"

    def evaluate(self, market_row: dict, detail: dict, context: dict) -> SopxRuleResult:
        dev = detail.get("developer_data") or {}
        pub = detail.get("public_interest_stats") or {}

        commits = dev.get("commit_count_4_weeks") or 0
        contributors = dev.get("pull_request_contributors") or 0
        alexa = pub.get("alexa_rank")

        dev_score = min(100, (commits / 200) * 70 + (contributors / 50) * 30)
        if alexa:
            interest_score = max(0, min(100, 100 - min(alexa, 1_000_000) / 10_000))
        else:
            interest_score = 40

        score = 0.65 * dev_score + 0.35 * interest_score
        return SopxRuleResult(
            score=score,
            reason=f"Dev proxy (commits={commits}, contrib={contributors}) + interest",
            meta={"commits": commits, "contributors": contributors, "alexa_rank": alexa}
        )
