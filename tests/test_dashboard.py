from html.parser import HTMLParser

from sopx_dashboard import sopx_make_dashboard


class DashboardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.badges = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "span" and attributes.get("class", "").startswith("action "):
            self.badges.append(attributes["class"].split()[-1])


def test_dashboard_ranks_scores_and_renders_scoring_dimensions(tmp_path):
    scores = [
        {"symbol": "BTC", "name": "Bitcoin", "total": 75.3, "constitutional": 60, "demand": 70, "capture": 80, "risk": 10, "tags": ["layer:regional"]},
        {"symbol": "ETH", "name": "Ether", "total": 88.2, "constitutional": 90, "demand": 85, "capture": 80, "risk": 5, "tags": ["layer:civilization"]},
    ]

    report_path = sopx_make_dashboard(scores, str(tmp_path))
    document = open(report_path, encoding="utf-8").read()

    assert document.index("ETH") < document.index("BTC")
    assert "Bitcoin" in document and "Ether" in document
    assert "88.2" in document and "75.3" in document
    assert "制度" in document and "需求" in document and "捕獲" in document and "風險" in document
    assert "layer:civilization" in document and "layer:regional" in document
    assert 'style="width:88.2%"' in document

    parser = DashboardParser()
    parser.feed(document)
    assert parser.badges == ["action-hold", "action-rotate"]


def test_dashboard_action_labels_follow_risk_and_score_rules(tmp_path):
    scores = [
        {"symbol": "RISK", "total": 10, "constitutional": 90, "risk": 40},
        {"symbol": "CORE", "total": 9, "constitutional": 85, "risk": 0},
        {"symbol": "GROW", "total": 8, "constitutional": 60, "risk": 0, "tags": ["thesis:product"]},
        {"symbol": "SPEC", "total": 7, "constitutional": 20, "risk": 0},
    ]

    report_path = sopx_make_dashboard(scores, str(tmp_path))
    parser = DashboardParser()
    parser.feed(open(report_path, encoding="utf-8").read())

    assert parser.badges == ["action-avoid", "action-hold", "action-rotate", "action-trade"]


def test_dashboard_escapes_untrusted_asset_text_and_clamps_progress(tmp_path):
    report_path = sopx_make_dashboard([
        {"symbol": '<img src=x onerror="alert(1)">', "name": "<script>run()</script>", "total": 120, "tags": ["<b>unsafe</b>"]},
        {"symbol": "LOW", "total": -5},
    ], str(tmp_path))
    document = open(report_path, encoding="utf-8").read()

    assert '<img src=x onerror="alert(1)">' not in document
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in document
    assert "&lt;script&gt;run()&lt;/script&gt;" in document
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in document
    assert 'style="width:100.0%"' in document
    assert 'style="width:0.0%"' in document


def test_empty_dashboard_is_valid_and_self_contained(tmp_path):
    report_path = sopx_make_dashboard([], str(tmp_path))
    document = open(report_path, encoding="utf-8").read()

    assert "目前沒有可顯示的評分資料。" in document
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in document
    assert "<style>" in document and "backdrop-filter: blur" in document
    assert "<script" not in document and "<link" not in document
    assert "最高評分" in document and "0.0" in document