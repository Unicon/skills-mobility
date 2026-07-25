"""Cross-CWD regression for Settings — covers the bare .env anchor bug."""

from __future__ import annotations

from event_consumer.config import _ENV_FILE, Settings


def test_settings_read_from_dotenv_regardless_of_cwd(tmp_path, monkeypatch) -> None:
    # The .env lives at the service package root; Settings must load it even when the
    # process runs from a *different* CWD (the repo-root-vs-service-dir bug). A bare
    # env_file=".env" would resolve against CWD and this would fail from tmp_path.
    monkeypatch.delenv("EVENT_CONSUMER_ORCHESTRATOR_URL", raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD that is NOT where the .env lives
    original = _ENV_FILE.read_text() if _ENV_FILE.exists() else None
    _ENV_FILE.write_text("EVENT_CONSUMER_ORCHESTRATOR_URL=http://orch.example\n")
    try:
        assert Settings().orchestrator_url == "http://orch.example"
    finally:
        if original is None:
            _ENV_FILE.unlink()
        else:
            _ENV_FILE.write_text(original)
