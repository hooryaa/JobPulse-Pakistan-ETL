import pytest
from etl.extract import RemoteOKConnector


def test_fetch_returns_list(monkeypatch):
    class DummyResp:
        def raise_for_status(self):
            pass

        def json(self):
            return [{'id': 1, 'company': 'Acme', 'position': 'Python Developer'}]

    def dummy_get(*a, **k):
        return DummyResp()

    monkeypatch.setattr('requests.get', dummy_get)
    conn = RemoteOKConnector(raw_dir='tests/tmp_raw')
    data = conn.fetch()
    assert isinstance(data, list)
    assert data[0]['id'] == 1
from etl.extract import fetch_remoteok_jobs


def test_fetch_remoteok_jobs_returns_list():
    records = fetch_remoteok_jobs(pages=1)
    assert isinstance(records, list)
