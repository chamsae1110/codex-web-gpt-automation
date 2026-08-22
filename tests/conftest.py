from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def stable_regular_web_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent from a developer's host-level Pro preference."""
    monkeypatch.setenv("CODEX_CHATGPT_REGULAR_WEB_MODE", "regular")
