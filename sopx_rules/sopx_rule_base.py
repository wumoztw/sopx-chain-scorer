from dataclasses import dataclass
from typing import Any, Dict, TypedDict
from config import AppConfig

class SopxRuleContext(TypedDict):
    cfg: AppConfig
    overrides: dict

@dataclass
class SopxRuleResult:
    score: float          # 0..100
    reason: str
    meta: Dict[str, Any]

class SopxBaseRule:
    name: str = "base_rule"

    def evaluate(self, market_row: dict, detail: dict, context: SopxRuleContext) -> SopxRuleResult:
        raise NotImplementedError
