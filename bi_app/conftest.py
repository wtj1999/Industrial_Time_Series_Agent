"""Keep all BI contract-test conversations out of the user's durable history."""
import pytest
from .session_store import get_bi_sessions


@pytest.fixture(autouse=True)
def isolated_bi_conversations(monkeypatch, tmp_path):
    monkeypatch.setenv('BI_SESSIONS_DB_PATH', str(tmp_path / 'bi_sessions.sqlite3'))
    get_bi_sessions.cache_clear()
    yield
    get_bi_sessions.cache_clear()
