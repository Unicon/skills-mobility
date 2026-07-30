"""Cross-CWD regression test for the Transformation Executor config.

The .env is anchored to the service package root via an absolute Path; a relative
env_file=".env" would resolve against the process CWD and silently fail when the
service is run from the repo root (the documented way). This test catches that.
"""

from __future__ import annotations

from transformation_executor.config import _ENV_FILE, Settings


def test_settings_read_from_dotenv_regardless_of_cwd(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("TRANSFORMATION_EXECUTOR_PORT", raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD that is NOT where the .env lives
    original = _ENV_FILE.read_text() if _ENV_FILE.exists() else None
    _ENV_FILE.write_text("TRANSFORMATION_EXECUTOR_PORT=9999\n")
    try:
        assert Settings().port == 9999
    finally:
        if original is None:
            _ENV_FILE.unlink()
        else:
            _ENV_FILE.write_text(original)
