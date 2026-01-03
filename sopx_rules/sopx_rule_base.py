from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SopxRuleResult:
    score: float          # 0..100
    reason: str
    meta: Dict[str, Any]

class SopxBaseRule:
    name: str = "base_rule"

    def evaluate(self, market_row: dict, detail: dict, context: dict) -> SopxRuleResult:
        raise NotImplementedError
