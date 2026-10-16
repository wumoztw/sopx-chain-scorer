from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import sopx_coingecko
import sopx_main
from config import AppConfig


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_rate_limiter_paces_parallel_requests_at_sustained_rate(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(
        sopx_coingecko,
        "time",
        SimpleNamespace(time=clock.time, sleep=clock.sleep),
    )
    limiter = sopx_coingecko.RateLimiter(max_requests_per_second=2, burst=2)

    def request(_):
        with limiter:
            return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert list(executor.map(request, range(8))) == [True] * 8

    assert clock.sleeps == [0.5] * 6


def test_coin_detail_retries_429_using_retry_after_and_rate_limiter(monkeypatch):
    class Response:
        def __init__(self, status_code, payload=None, headers=None):
            self.status_code = status_code
            self.payload = payload
            self.headers = headers or {}

        def json(self):
            return self.payload

        def raise_for_status(self):
            raise AssertionError("unexpected HTTP error")

    class Session:
        def __init__(self):
            self.headers = {}
            self.responses = [Response(429, headers={"Retry-After": "3"}), Response(200, {"id": "coin"})]
            self.calls = []

        def get(self, url, params, timeout):
            self.calls.append((url, params, timeout))
            return self.responses.pop(0)

    class Limiter:
        def __init__(self):
            self.entries = 0

        def __enter__(self):
            self.entries += 1
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    client = sopx_coingecko.SopxCoinGeckoClient(delay_sec=0, max_retries=2, rate_limit_rps=1)
    session = Session()
    limiter = Limiter()
    sleeps = []
    client.s = session
    client.rate_limiter = limiter
    monkeypatch.setattr(client, "_sleep_with_jitter", sleeps.append)

    result = client.coin_detail("coin")

    assert result == {"id": "coin"}
    assert len(session.calls) == 2
    assert limiter.entries == 2
    assert sleeps == [4.0, 0.0]
    assert session.calls[0][0].endswith("/coins/coin")
    assert session.calls[0][1]["market_data"] == "true"


def test_stage2_details_cover_top_scores_and_rank_candidates(monkeypatch):
    config = AppConfig()
    config.stage2.detail_top_n = 1
    config.stage2.detail_extra_n = 1
    rows = [
        {"id": "alpha", "market_cap_rank": 3},
        {"id": "beta", "market_cap_rank": 1},
        {"id": "gamma", "market_cap_rank": 2},
    ]

    class FakeClient:
        def __init__(self, delay_sec):
            self.detail_calls = []

        def top_markets(self, **kwargs):
            return rows

        def coin_detail(self, coin_id):
            self.detail_calls.append(coin_id)
            return {"detailed": True}

    client = FakeClient(0)
    monkeypatch.setattr(sopx_main.AppConfig, "from_yaml", lambda path: config)
    monkeypatch.setattr(sopx_main, "sopx_load_yaml", lambda path: {})
    monkeypatch.setattr(sopx_main, "SopxCoinGeckoClient", lambda delay_sec: client)
    stage1_totals = {"alpha": 90, "beta": 80, "gamma": 70}

    def score(row, detail, cfg, overrides):
        total = 100 if detail else stage1_totals[row["id"]]
        return {"id": row["id"], "rank": row["market_cap_rank"], "total": total}

    monkeypatch.setattr(sopx_main, "sopx_score_coin", score)
    saved = {}
    monkeypatch.setattr(
        sopx_main,
        "sopx_append_history",
        lambda scores, date: saved.update(scores={score["id"]: score for score in scores}),
    )
    monkeypatch.setattr(sopx_main, "sopx_utc_today_str", lambda: "2026-01-01")
    monkeypatch.setattr(sopx_main, "sopx_compute_trends", lambda scores, weeks_lookback: ([], [], []))
    monkeypatch.setattr(sopx_main, "sopx_write_reports", lambda *args, **kwargs: None)
    monkeypatch.delenv("PLURK_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("PLURK_CONSUMER_SECRET", raising=False)
    monkeypatch.delenv("PLURK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("PLURK_ACCESS_TOKEN_SECRET", raising=False)

    sopx_main.main()

    assert client.detail_calls == ["alpha", "beta"]
    assert {coin_id: score["total"] for coin_id, score in saved["scores"].items()} == {
        "alpha": 100,
        "beta": 100,
        "gamma": 70,
    }
