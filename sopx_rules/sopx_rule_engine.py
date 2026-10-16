from importlib import import_module
import pkgutil
from typing import Dict, List, Tuple

import sopx_rules
from config import RuleWeightConfig
from .sopx_rule_base import SopxRuleContext, SopxRuleResult


def _sopx_load_rule(module_path: str, class_name: str = "Rule"):
    module = import_module(module_path)
    rule_class = getattr(module, class_name)
    return rule_class()


class SopxRuleEngine:
    """Discover and instantiate rule plugins once, then reuse them for scoring."""

    def __init__(self):
        self._rules = {}
        for group_info in pkgutil.iter_modules(sopx_rules.__path__):
            if not group_info.ispkg:
                continue
            group_name = group_info.name
            group = import_module(f"sopx_rules.{group_name}")
            self._rules[group_name] = {
                rule_info.name: _sopx_load_rule(f"sopx_rules.{group_name}.{rule_info.name}")
                for rule_info in pkgutil.iter_modules(group.__path__)
                if not rule_info.ispkg and not rule_info.name.startswith("_")
            }

    def run(
        self,
        rule_group: str,
        enabled: List[str],
        weights: RuleWeightConfig,
        market_row: dict,
        detail: dict,
        context: SopxRuleContext,
    ) -> Tuple[float, Dict[str, dict]]:
        breakdown = {}
        total_w = 0.0
        total = 0.0

        for rule_name in enabled:
            rule = self._rules[rule_group][rule_name]
            weight = float(getattr(weights, rule_name, 1.0))
            result: SopxRuleResult = rule.evaluate(market_row, detail, context)
            score = max(0.0, min(100.0, float(result.score)))

            breakdown[rule_name] = {
                "score": round(score, 2),
                "weight": weight,
                "reason": result.reason,
                "meta": result.meta,  # keep meta for tags/report
            }
            total_w += weight
            total += weight * score

        if total_w <= 0:
            return 0.0, breakdown
        return round(total / total_w, 2), breakdown


_DEFAULT_ENGINE = SopxRuleEngine()


def sopx_run_rule_set(rule_group: str, enabled: List[str], weights: RuleWeightConfig,
                      market_row: dict, detail: dict, context: SopxRuleContext) -> Tuple[float, Dict[str, dict]]:
    return _DEFAULT_ENGINE.run(
        rule_group, enabled, weights, market_row, detail, context
    )
