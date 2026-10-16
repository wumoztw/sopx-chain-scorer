import pytest

from config import AppConfig


@pytest.mark.parametrize("document", ["", "null"])
def test_empty_or_null_yaml_uses_defensive_defaults(tmp_path, document):
    path = tmp_path / "empty.yml"
    path.write_text(document, encoding="utf-8")

    config = AppConfig.from_yaml(str(path))

    assert config.coingecko.top_n == 100
    assert config.coingecko.request_delay_sec == 2.5
    assert config.scoring.weights.constitutional == 0.40
    assert config.stage2.detail_top_n == 20
    assert config.stage2.detail_extra_n == 10
    assert config.rules.constitutional.enabled


def test_yaml_scalar_types_and_nested_values_are_parsed(tmp_path):
    path = tmp_path / "typed.yml"
    path.write_text(
        "coingecko:\n  top_n: 25\n  request_delay_sec: 0.5\n"
        "stage2:\n  detail_top_n: 7\n  detail_extra_n: 3\n",
        encoding="utf-8",
    )

    config = AppConfig.from_yaml(str(path))

    assert config.coingecko.top_n == 25
    assert isinstance(config.coingecko.top_n, int)
    assert config.coingecko.request_delay_sec == 0.5
    assert isinstance(config.coingecko.request_delay_sec, float)
    assert (config.stage2.detail_top_n, config.stage2.detail_extra_n) == (7, 3)


@pytest.mark.parametrize("document", ["[]", "coingecko: []", "scoring: null"])
def test_non_mapping_yaml_roots_or_sections_are_rejected(tmp_path, document):
    path = tmp_path / "invalid.yml"
    path.write_text(document, encoding="utf-8")

    with pytest.raises(ValueError):
        AppConfig.from_yaml(str(path))


def test_missing_config_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        AppConfig.from_yaml(str(tmp_path / "missing.yml"))


def test_default_rule_lists_are_not_shared_between_configs():
    first = AppConfig()
    second = AppConfig()
    first.rules.constitutional.enabled.append("test_rule")

    assert "test_rule" not in second.rules.constitutional.enabled
