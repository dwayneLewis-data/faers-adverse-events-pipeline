"""Tests for the OpenFDA API client."""

import pytest
import requests

from src.api_client import (
    _build_initial_url,
    _extract_next_link,
    _get_with_retries,
    fetch_reports,
)

SAMPLE_API_CONFIG = {
    "base_url": "https://api.fda.gov/drug/event.json",
    "search": "serious:1 AND receivedate:[20190101 TO 20231231]",
    "sort": "receivedate:asc",
    "limit": 100,
}

SAMPLE_CONFIG = {
    "api": {
        **SAMPLE_API_CONFIG,
        "max_records": 5,
        "timeout_seconds": 30,
        "max_retries": 3,
        "backoff_seconds": 5,
    }
}


class FakeResponse:
    """Impersonates the parts of requests.Response that our code touches."""

    def __init__(self, status_code, links=None, payload=None):
        self.status_code = status_code
        self.links = links if links is not None else {}
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


def make_fake_get(outcomes):
    """Build a fake requests.get that follows a scripted list of outcomes.

    Each outcome is an exception instance (raise it), a prepared
    FakeResponse (return it), or a status code (wrap and return it).
    The fake records every call it receives.
    """
    calls = []

    def fake_get(url, timeout):
        outcome = outcomes[len(calls)]
        calls.append(url)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, FakeResponse):
            return outcome
        return FakeResponse(outcome)

    fake_get.calls = calls
    return fake_get


def make_report_batch(start_id, count):
    """Build a list of minimal fake FAERS report dicts."""
    return [{"safetyreportid": str(start_id + i)} for i in range(count)]


# ---------- _build_initial_url ----------


def test_url_starts_with_base_url(monkeypatch):
    monkeypatch.delenv("OPENFDA_API_KEY", raising=False)
    url = _build_initial_url(SAMPLE_API_CONFIG)
    assert url.startswith("https://api.fda.gov/drug/event.json?")


def test_search_expression_is_encoded(monkeypatch):
    monkeypatch.delenv("OPENFDA_API_KEY", raising=False)
    url = _build_initial_url(SAMPLE_API_CONFIG)
    assert " " not in url
    assert "serious%3A1" in url


def test_api_key_included_when_env_var_set(monkeypatch):
    monkeypatch.setenv("OPENFDA_API_KEY", "test_key_123")
    url = _build_initial_url(SAMPLE_API_CONFIG)
    assert "api_key=test_key_123" in url


def test_api_key_omitted_when_env_var_missing(monkeypatch):
    monkeypatch.delenv("OPENFDA_API_KEY", raising=False)
    url = _build_initial_url(SAMPLE_API_CONFIG)
    assert "api_key" not in url


# ---------- _get_with_retries ----------


def test_returns_response_on_first_success(monkeypatch):
    fake = make_fake_get([200])
    monkeypatch.setattr("src.api_client.requests.get", fake)
    response = _get_with_retries("http://test", 30, 3, 5)
    assert response.status_code == 200
    assert len(fake.calls) == 1


def test_retries_on_server_error_then_succeeds(monkeypatch):
    fake = make_fake_get([500, 200])
    monkeypatch.setattr("src.api_client.requests.get", fake)
    monkeypatch.setattr("src.api_client.time.sleep", lambda seconds: None)
    response = _get_with_retries("http://test", 30, 3, 5)
    assert response.status_code == 200
    assert len(fake.calls) == 2


def test_retries_on_timeout_then_succeeds(monkeypatch):
    fake = make_fake_get([requests.exceptions.Timeout("timed out"), 200])
    monkeypatch.setattr("src.api_client.requests.get", fake)
    monkeypatch.setattr("src.api_client.time.sleep", lambda seconds: None)
    response = _get_with_retries("http://test", 30, 3, 5)
    assert response.status_code == 200
    assert len(fake.calls) == 2


def test_fails_fast_on_client_error(monkeypatch):
    fake = make_fake_get([404])
    monkeypatch.setattr("src.api_client.requests.get", fake)
    with pytest.raises(requests.exceptions.HTTPError):
        _get_with_retries("http://test", 30, 3, 5)
    assert len(fake.calls) == 1


def test_raises_runtime_error_when_retries_exhausted(monkeypatch):
    fake = make_fake_get([500, 500, 500])
    monkeypatch.setattr("src.api_client.requests.get", fake)
    monkeypatch.setattr("src.api_client.time.sleep", lambda seconds: None)
    with pytest.raises(RuntimeError):
        _get_with_retries("http://test", 30, 3, 5)
    assert len(fake.calls) == 3


# ---------- _extract_next_link ----------


def test_extract_next_link_returns_url_when_present():
    response = FakeResponse(
        200,
        links={"next": {"url": "https://api.fda.gov/drug/event.json?page2"}},
    )
    assert _extract_next_link(response) == "https://api.fda.gov/drug/event.json?page2"


def test_extract_next_link_returns_none_on_last_page():
    response = FakeResponse(200)
    assert _extract_next_link(response) is None


# ---------- fetch_reports ----------


def test_fetch_reports_follows_links_until_last_page(monkeypatch):
    page1 = FakeResponse(
        200,
        links={"next": {"url": "http://test/page2"}},
        payload={"results": make_report_batch(100, 2)},
    )
    page2 = FakeResponse(200, payload={"results": make_report_batch(200, 2)})
    fake = make_fake_get([page1, page2])
    monkeypatch.setattr("src.api_client.requests.get", fake)

    batches = list(fetch_reports(SAMPLE_CONFIG))

    assert len(batches) == 2
    assert len(fake.calls) == 2
    assert batches[0][0]["safetyreportid"] == "100"
    assert batches[1][0]["safetyreportid"] == "200"


def test_fetch_reports_stops_and_trims_at_max_records(monkeypatch):
    page1 = FakeResponse(
        200,
        links={"next": {"url": "http://test/page2"}},
        payload={"results": make_report_batch(100, 3)},
    )
    page2 = FakeResponse(
        200,
        links={"next": {"url": "http://test/page3"}},
        payload={"results": make_report_batch(200, 3)},
    )
    fake = make_fake_get([page1, page2])
    monkeypatch.setattr("src.api_client.requests.get", fake)

    batches = list(fetch_reports(SAMPLE_CONFIG))  # max_records = 5

    total = sum(len(batch) for batch in batches)
    assert total == 5
    assert len(batches[1]) == 2
    assert len(fake.calls) == 2


def test_fetch_reports_handles_empty_results(monkeypatch):
    empty = FakeResponse(200, payload={"results": []})
    fake = make_fake_get([empty])
    monkeypatch.setattr("src.api_client.requests.get", fake)

    batches = list(fetch_reports(SAMPLE_CONFIG))

    assert batches == []
