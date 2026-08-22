from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "bin" / "chatgpt_workspace_config.py"


def load():
    spec = importlib.util.spec_from_file_location("chatgpt_workspace_config_test", PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_app_name_defaults_and_supports_host_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.delenv("CODEX_CHATGPT_APP_NAME", raising=False)
    assert module.configured_app_name() == "codex"

    (tmp_path / "chatgpt-workspace.json").write_text(
        json.dumps({"app_name": "codex"}), encoding="utf-8"
    )
    assert module.configured_app_name() == "codex"

    monkeypatch.setenv("CODEX_CHATGPT_APP_NAME", "temporary")
    assert module.configured_app_name() == "temporary"


def test_regular_web_mode_defaults_and_supports_durable_pro_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.delenv("CODEX_CHATGPT_REGULAR_WEB_MODE", raising=False)
    assert module.configured_regular_web_mode() == "regular"

    (tmp_path / "chatgpt-workspace.json").write_text(
        json.dumps({"app_name": "dev", "regular_web_mode": "pro"}),
        encoding="utf-8",
    )
    assert module.configured_regular_web_mode() == "pro"

    monkeypatch.setenv("CODEX_CHATGPT_REGULAR_WEB_MODE", "regular")
    assert module.configured_regular_web_mode() == "regular"


@pytest.mark.parametrize("value", ["", "@codex", "line\nbreak"])
def test_workspace_app_name_rejects_unsafe_values(value: str) -> None:
    module = load()
    with pytest.raises(ValueError):
        module.normalize_app_name(value)


@pytest.mark.parametrize("value", ["", "max", "extra-high"])
def test_regular_web_mode_rejects_unknown_values(value: str) -> None:
    module = load()
    with pytest.raises(ValueError):
        module.normalize_regular_web_mode(value)
