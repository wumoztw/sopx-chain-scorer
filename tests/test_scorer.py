import pytest

import sopx_scorer
from config import AppConfig
from sopx_rules.sopx_rule_base import SopxRuleResult
from sopx_rules import sopx_rule_engine


def test_score_coin_combines_demand_capture_and_weighted_components(monkeypatch):
    monkeypatch.setattr(sopx_scorer, "sopx_run_rule_set", lambda **kwargs: (80, {}))
    market = {
        "id": "sample",
        "symbol": "smp",
        "name": "Sample",
        "market_cap": 100_000_000,
        "total_volume": 10_000_000,
        "market_cap_rank": 5,
        "price_change_percentage_7d_in_currency": 10,
    }
    detail = {
        "market_data": {
            "max_supply": 100,
            "total_supply": 90,
            "circulating_supply": 80,
        },
        "developer_data": {"commit_count_4_weeks": 12},
        "community_data": {"twitter_followers": 1_000_000, "reddit_subscribers": 250_000},
    }

    result = sopx_scorer.sopx_score_coin(market, detail, AppConfig(), {})

    assert result["constitutional"] == 80
    assert result["vol_to_mcap"] == pytest.approx(0.1)
    assert result["demand"] == 75
    assert result["capture"] == 100
    assert result["risk"] == 0
    assert result["total"] == 74.5


@pytest.mark.parametrize(
    ("market_cap", "volume", "expected_risk"),
    [
        (50_000_000, 100_000, 0),
        (50_000_000, 99_999, 20),
        (49_999_999, 100_000, 20),
        (49_999_999, 99_999, 40),
    ],
)
def test_risk_penalties_apply_only_below_veto_thresholds(
    monkeypatch, market_cap, volume, expected_risk
):
    monkeypatch.setattr(sopx_scorer, "sopx_run_rule_set", lambda **kwargs: (50, {}))
    market = {"id": "boundary", "market_cap": market_cap, "total_volume": volume}
    detail = {"developer_data": {"commit_count_4_weeks": 1}}

    result = sopx_scorer.sopx_score_coin(market, detail, AppConfig(), {})

    assert result["risk"] == expected_risk


def test_zero_market_cap_and_missing_supply_are_safe(monkeypatch):
    monkeypatch.setattr(sopx_scorer, "sopx_run_rule_set", lambda **kwargs: (50, {}))

    result = sopx_scorer.sopx_score_coin({"id": "empty"}, {}, AppConfig(), {})

    assert result["vol_to_mcap"] == 0
    assert result["capture"] == 0
    assert result["risk"] == 50
    assert 0 <= result["total"] <= 100


def test_rule_engine_normalizes_weights_and_clamps_rule_scores(monkeypatch):
    class FixedRule:
        def __init__(self, score):
            self.score = score

        def evaluate(self, market_row, detail, context):
            return SopxRuleResult(score=self.score, reason="fixed", meta={})

    rules = {"sopx_curated_facts": FixedRule(150), "sopx_age_maturity": FixedRule(-20)}
    monkeypatch.setattr(sopx_rule_engine, "_sopx_load_rule", lambda path: rules[path.rsplit(".", 1)[-1]])
    from config import RuleWeightConfig

    weights = RuleWeightConfig(sopx_curated_facts=1, sopx_age_maturity=3)
    score, breakdown = sopx_rule_engine.sopx_run_rule_set(
        rule_group="constitutional",
        enabled=["sopx_curated_facts", "sopx_age_maturity"],
        weights=weights,
        market_row={},
        detail={},
        context={},
    )

    assert score == 25
    assert breakdown["sopx_curated_facts"]["score"] == 100
    assert breakdown["sopx_age_maturity"]["score"] == 0


def test_governance_rule_category_and_platform_adjustments():
    from sopx_rules.constitutional.sopx_governance_admin_risk import Rule

    rule = Rule()

    category_only = rule.evaluate({}, {"categories": ["Centralized Exchange Token"]}, {})
    category_and_platform = rule.evaluate(
        {},
        {
            "categories": ["Centralized Exchange Token"],
            "platforms": {"ethereum": "0x123"},
        },
        {},
    )

    assert category_only.score == 40
    assert category_and_platform.score == 45
