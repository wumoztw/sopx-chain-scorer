from dataclasses import dataclass, field
from typing import List
import yaml
from pathlib import Path


def _config_section(data: dict, name: str) -> dict:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"Configuration section '{name}' must be a mapping")
    return section

@dataclass
class CoinGeckoConfig:
    """CoinGecko API configuration"""
    vs_currency: str = "usd"
    top_n: int = 100
    request_delay_sec: float = 2.5

    def __post_init__(self):
        if self.top_n <= 0:
            raise ValueError("top_n must be positive")
        if self.request_delay_sec < 0:
            raise ValueError("request_delay_sec must be non-negative")


@dataclass
class ScoringWeightsConfig:
    """Scoring component weights (sum should be approximately 1.0)"""
    constitutional: float = 0.40
    demand: float = 0.30
    capture: float = 0.20
    risk: float = 0.10

    def __post_init__(self):
        total = self.constitutional + self.demand + self.capture + self.risk
        if not abs(total - 1.0) < 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
        for attr, val in self.__dict__.items():
            if val < 0 or val > 1:
                raise ValueError(f"{attr} weight must be between 0 and 1")


@dataclass
class VetoConfig:
    """Scoring veto/penalties thresholds"""
    min_market_cap_usd: int = 50_000_000
    min_volume_to_mcap: float = 0.002
    missing_dev_data_penalty: int = 10

    def __post_init__(self):
        if self.min_market_cap_usd < 0:
            raise ValueError("min_market_cap_usd must be non-negative")
        if self.min_volume_to_mcap < 0:
            raise ValueError("min_volume_to_mcap must be non-negative")
        if self.missing_dev_data_penalty < 0:
            raise ValueError("missing_dev_data_penalty must be non-negative")


@dataclass
class ScoringConfig:
    """Scoring configuration including weights and veto rules"""
    weights: ScoringWeightsConfig = field(default_factory=ScoringWeightsConfig)
    veto: VetoConfig = field(default_factory=VetoConfig)


@dataclass
class DatasetConfig:
    """Dataset configuration"""
    curated_path: str = "curated_dataset.yml"

    def __post_init__(self):
        if not self.curated_path:
            raise ValueError("curated_path must not be empty")


@dataclass
class RuleWeightConfig:
    """Weights for individual rules in a rule group"""
    # This is a generic type; actual rule groups have specific rules
    sopx_curated_facts: float = 0.40
    sopx_age_maturity: float = 0.15
    sopx_decentralization_proxy: float = 0.15
    sopx_governance_admin_risk: float = 0.10
    sopx_l2_settlement_anchor: float = 0.20

    def __post_init__(self):
        for attr, val in self.__dict__.items():
            if val < 0:
                raise ValueError(f"{attr} weight must be non-negative")


@dataclass
class ConstitutionalRulesConfig:
    """Constitutional rule group configuration"""
    enabled: List[str] = field(default_factory=lambda: [
        "sopx_curated_facts",
        "sopx_age_maturity",
        "sopx_decentralization_proxy",
        "sopx_governance_admin_risk",
        "sopx_l2_settlement_anchor"
    ])
    weights: RuleWeightConfig = field(default_factory=RuleWeightConfig)

    def __post_init__(self):
        if not self.enabled:
            raise ValueError("At least one rule must be enabled")


@dataclass
class RulesConfig:
    """Rules configuration"""
    constitutional: ConstitutionalRulesConfig = field(default_factory=ConstitutionalRulesConfig)


@dataclass
class OutputConfig:
    """Output configuration"""
    top_to_post: int = 10
    report_dir: str = "reports"

    def __post_init__(self):
        if self.top_to_post <= 0:
            raise ValueError("top_to_post must be positive")
        if not self.report_dir:
            raise ValueError("report_dir must not be empty")


@dataclass
class PlurkConfig:
    """Plurk posting configuration"""
    max_chars: int = 2900

    def __post_init__(self):
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")


@dataclass
class Stage2Config:
    """Stage 2 scoring configuration"""
    detail_top_n: int = 20
    detail_extra_n: int = 10

    def __post_init__(self):
        if self.detail_top_n <= 0:
            raise ValueError("detail_top_n must be positive")
        if self.detail_extra_n <= 0:
            raise ValueError("detail_extra_n must be positive")


@dataclass
class AppConfig:
    """Complete application configuration"""
    coingecko: CoinGeckoConfig = field(default_factory=CoinGeckoConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    plurk: PlurkConfig = field(default_factory=PlurkConfig)
    stage2: Stage2Config = field(default_factory=Stage2Config)

    @classmethod
    def from_yaml(cls, path: str = "config.yml") -> "AppConfig":
        """Load configuration from YAML file"""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path_obj, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError("Configuration root must be a mapping")

        coingecko_data = _config_section(data, "coingecko")
        scoring_data = _config_section(data, "scoring")
        veto_data = _config_section(scoring_data, "veto")
        weights_data = _config_section(scoring_data, "weights")
        dataset_data = _config_section(data, "dataset")
        rules_data = _config_section(data, "rules")
        constitutional_rules_data = _config_section(rules_data, "constitutional")
        rules_weights_data = _config_section(constitutional_rules_data, "weights")
        output_data = _config_section(data, "output")
        plurk_data = _config_section(data, "plurk")
        stage2_data = _config_section(data, "stage2")

        return cls(
            coingecko=CoinGeckoConfig(**coingecko_data),
            scoring=ScoringConfig(
                weights=ScoringWeightsConfig(**weights_data),
                veto=VetoConfig(**veto_data)
            ),
            dataset=DatasetConfig(**dataset_data),
            rules=RulesConfig(
                constitutional=ConstitutionalRulesConfig(
                    enabled=constitutional_rules_data.get(
                        "enabled", ConstitutionalRulesConfig().enabled
                    ),
                    weights=RuleWeightConfig(**rules_weights_data)
                )
            ),
            output=OutputConfig(**output_data),
            plurk=PlurkConfig(**plurk_data),
            stage2=Stage2Config(**stage2_data),
        )

