"""Tests for ingest pull log resume."""

import json

from scrapers.pull_log import PullLog, make_pull_key


def test_make_pull_key_normalizes_url() -> None:
    key = make_pull_key("https://Citaty.info/quote/1/?utm=1")
    assert key == "https://citaty.info/quote/1"


def test_pull_log_skip_success_only(tmp_path) -> None:
    path = tmp_path / "pull_log.json"
    log = PullLog(path)
    key = make_pull_key("https://example.com/page")
    log.record_failure(key, "test", "timeout")
    assert log.should_skip(key) is False
    log.record_success(key, "test")
    assert log.should_skip(key) is True
    log.save()

    reloaded = PullLog(path)
    assert reloaded.should_skip(key) is True
    summary = reloaded.summary()
    assert summary["pull_log_stored_success"] == 1
    assert summary["pull_log_stored_failure"] == 0


def test_pull_log_persists_failures(tmp_path) -> None:
    path = tmp_path / "pull_log.json"
    log = PullLog(path)
    key = make_pull_key("https://example.com/fail")
    log.record_failure(key, "citaty_info", "404")
    log.save()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["urls"][key]["status"] == "failure"
    assert payload["urls"][key]["error"] == "404"
