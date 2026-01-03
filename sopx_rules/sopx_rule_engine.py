from importlib import import_module
from typing import Dict, List, Tuple
from .sopx_rule_base import SopxRuleResult

def _sopx_load_rule(module_path: str, class_name: str = "Rule"):
    mod = import_module(module_path)
    cls = getattr(mod, class_name)
    return cls()

def sopx_run_rule_set(rule_group: str, enabled: List[str], weights: Dict[str, float],
                      market_row: dict, detail: dict, context: dict) -> Tuple[float, Dict[str, dict]]:
    breakdown = {}
    total_w = 0.0
    total = 0.0

    for rule_name in enabled:
        module_path = f"sopx_rules.{rule_group}.{rule_name}"
        rule = _sopx_load_rule(module_path)
        w = float(weights.get(rule_name, 1.0))

        res: SopxRuleResult = rule.evaluate(market_row, detail, context)
        score = max(0.0, min(100.0, float(res.score)))

        breakdown[rule_name] = {
            "score": round(score, 2),
            "weight": w,
            "reason": res.reason,
            "meta": res.meta,  # keep meta for tags/report
        }

        total_w += w
        total += w * score

    if total_w <= 0:
        return 0.0, breakdown

    return round(total / total_w, 2), breakdown
