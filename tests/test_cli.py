"""CLI argument parsing and config override tests."""

import argparse
import pytest
from unittest.mock import patch, MagicMock

from sopx_main import main


def test_cli_defaults(argv_helper):
    """Verify default CLI values are parsed correctly."""
    args = argv_helper([])
    assert args.config == "config.yml"
    assert args.limit is None
    assert args.top_stage1 is None
    assert args.workers == 4
    assert args.no_cache is False
    assert args.output_dir is None


def test_cli_custom_config(argv_helper):
    """Verify --config / -c overrides config path."""
    args = argv_helper(["-c", "myconfig.yml"])
    assert args.config == "myconfig.yml"

    args = argv_helper(["--config", "myconfig.yml"])
    assert args.config == "myconfig.yml"


def test_cli_limit(argv_helper):
    """Verify --limit / -n value."""
    args = argv_helper(["-n", "10"])
    assert args.limit == 10

    args = argv_helper(["--limit", "5"])
    assert args.limit == 5


def test_cli_top_stage1(argv_helper):
    """Verify --top-stage1 overrides Stage 2 candidate count."""
    args = argv_helper(["--top-stage1", "30"])
    assert args.top_stage1 == 30


def test_cli_workers(argv_helper):
    """Verify -w / --workers value."""
    args = argv_helper(["-w", "8"])
    assert args.workers == 8

    args = argv_helper(["--workers", "2"])
    assert args.workers == 2


def test_cli_no_cache(argv_helper):
    """Verify --no-cache flag."""
    args = argv_helper([])
    assert args.no_cache is False

    args = argv_helper(["--no-cache"])
    assert args.no_cache is True


def test_cli_output_dir(argv_helper):
    """Verify --output-dir value."""
    args = argv_helper(["--output-dir", "custom_reports"])
    assert args.output_dir == "custom_reports"


def test_cli_all_args_combined(argv_helper):
    """Verify all CLI args combined."""
    args = argv_helper([
        "-c", "alt.yml",
        "-n", "25",
        "--top-stage1", "50",
        "-w", "6",
        "--no-cache",
        "--output-dir", "alt_reports",
    ])
    assert args.config == "alt.yml"
    assert args.limit == 25
    assert args.top_stage1 == 50
    assert args.workers == 6
    assert args.no_cache is True
    assert args.output_dir == "alt_reports"


@pytest.fixture
def argv_helper():
    """Helper to parse CLI args with sys.argv replacement."""

    def _parse(argv):
        parser = argparse.ArgumentParser(description="Score CoinGecko market data")
        parser.add_argument("-c", "--config", default="config.yml")
        parser.add_argument("--limit", "-n", type=int, default=None)
        parser.add_argument("--top-stage1", type=int, default=None)
        parser.add_argument("-w", "--workers", type=int, default=4)
        parser.add_argument("--no-cache", action="store_true")
        parser.add_argument("--output-dir", default=None)
        return parser.parse_args(argv)

    return _parse


@patch("sopx_main.AppConfig")
@patch("sopx_main.SopxCoinGeckoClient")
@patch("sopx_main.sopx_score_coin")
@patch("sopx_main.sopx_load_yaml")
@patch("sopx_main.sopx_append_history")
@patch("sopx_main.sopx_compute_trends")
@patch("sopx_main.sopx_write_reports")
@patch("sopx_main.sopx_make_dashboard")
@patch("sopx_main.sopx_utc_today_str")
def test_main_cli_overrides_config(
    mock_utc_str,
    mock_make_dashboard,
    mock_write_reports,
    mock_compute_trends,
    mock_append_history,
    mock_load_yaml,
    mock_score_coin,
    mock_client_cls,
    mock_appconfig_cls,
    tmp_path,
):
    """Verify CLI args override config object fields during main() execution."""
    mock_utc_str.return_value = "2024-01-01"
    mock_load_yaml.return_value = {}
    mock_score_coin.return_value = {"id": "bitcoin", "symbol": "btc", "total": 80, "rank": 1}
    mock_client = MagicMock()
    mock_client.top_markets.return_value = [{"id": "bitcoin", "symbol": "btc"}]
    mock_client.coin_detail.return_value = {}
    mock_client_cls.return_value = mock_client

    mock_cfg = MagicMock()
    mock_cfg.coingecko.vs_currency = "usd"
    mock_cfg.coingecko.top_n = 100
    mock_cfg.coingecko.request_delay_sec = 2.5
    mock_cfg.output.report_dir = "reports"
    mock_cfg.stage2.stage2_candidates = 20
    mock_cfg.stage2.detail_extra_n = 10
    mock_cfg.plurk.max_chars = 2900
    mock_appconfig_cls.from_yaml.return_value = mock_cfg

    mock_append_history.return_value = None
    mock_compute_trends.return_value = ([], [], [])
    mock_write_reports.return_value = None
    mock_make_dashboard.return_value = "dashboard.html"

    # Patch environment to skip Plurk
    with patch.dict("os.environ", {}, clear=True):
        main(["-c", "custom.yml", "--limit", "5", "--top-stage1", "30", "-w", "8", "--no-cache", "--output-dir", "out"])

    # Verify config was loaded from the custom path
    mock_appconfig_cls.from_yaml.assert_called_once_with("custom.yml")

    # Verify CLI overrides applied to config
    assert mock_cfg.stage2.stage2_candidates == 30
    assert mock_cfg.output.report_dir == "out"

    # Verify client created with cache_enabled=False (due to --no-cache)
    mock_client_cls.assert_called_once()
    call_kwargs = mock_client_cls.call_args.kwargs
    assert call_kwargs["cache_enabled"] is False

    # Verify limit applied to final scores
    assert len(mock_write_reports.call_args.args[0]) <= 5


def test_main_top_stage1_overrides_config(tmp_path):
    """Verify --top-stage1 overrides stage2_candidates from config."""
    with patch("sopx_main.AppConfig") as mock_appconfig_cls, \
         patch("sopx_main.SopxCoinGeckoClient") as mock_client_cls, \
         patch("sopx_main.sopx_score_coin") as mock_score_coin, \
         patch("sopx_main.sopx_load_yaml", return_value={}), \
         patch("sopx_main.sopx_append_history"), \
         patch("sopx_main.sopx_compute_trends", return_value=([], [], [])), \
         patch("sopx_main.sopx_write_reports"), \
         patch("sopx_main.sopx_make_dashboard"), \
         patch("sopx_main.sopx_utc_today_str", return_value="2024-01-01"), \
         patch.dict("os.environ", {}, clear=True):

        mock_cfg = MagicMock()
        mock_cfg.coingecko.vs_currency = "usd"
        mock_cfg.coingecko.top_n = 100
        mock_cfg.coingecko.request_delay_sec = 2.5
        mock_cfg.output.report_dir = "reports"
        mock_cfg.stage2.stage2_candidates = 20  # config value
        mock_cfg.stage2.detail_extra_n = 10
        mock_cfg.plurk.max_chars = 2900
        mock_appconfig_cls.from_yaml.return_value = mock_cfg

        mock_client = MagicMock()
        mock_client.top_markets.return_value = []
        mock_client_cls.return_value = mock_client

        main(["--top-stage1", "50"])

        # Verify stage2_candidates was overridden by CLI
        assert mock_cfg.stage2.stage2_candidates == 50
        mock_client_cls.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
