"""Cross-CWD regression for Settings — covers the bare .env anchor bug."""

from __future__ import annotations

from context_builder.config import Settings, _ENV_FILE


def test_settings_read_from_dotenv_regardless_of_cwd(tmp_path, monkeypatch) -> None:
    # The .env lives at the service package root; Settings must load it even when the
    # process runs from a *different* CWD (the repo-root-vs-service-dir bug). A bare
    # env_file=".env" would resolve against CWD and this would fail from tmp_path.
    monkeypatch.delenv("CONTEXT_BUILDER_LMS_BASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD that is NOT where the .env lives
    original = _ENV_FILE.read_text() if _ENV_FILE.exists() else None
    _ENV_FILE.write_text("CONTEXT_BUILDER_LMS_BASE_URL=http://cb.example\n")
    try:
        assert Settings().lms_base_url == "http://cb.example"
    finally:
        if original is None:
            _ENV_FILE.unlink()
        else:
            _ENV_FILE.write_text(original)
