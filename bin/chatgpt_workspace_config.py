from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_APP_NAME = "codex"
DEFAULT_REGULAR_WEB_MODE = "regular"
CONFIG_FILE = "chatgpt-workspace.json"


def normalize_app_name(value: object) -> str:
    name = str(value or "").strip()
    if not name or name.startswith("@") or len(name) > 128 or any(ch in name for ch in "\r\n"):
        raise ValueError("app_name must be 1..128 characters without @ or line breaks")
    return name


def normalize_regular_web_mode(value: object) -> str:
    mode = str(value or "").strip().casefold()
    if mode not in {"regular", "pro"}:
        raise ValueError("regular_web_mode must be regular or pro")
    return mode


def config_path() -> Path:
    root = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser()
    return root / CONFIG_FILE


def _configured_values() -> dict[str, object]:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"workspace app config is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"workspace app config must be a JSON object: {path}")
    return value


def configured_app_name() -> str:
    override = str(os.environ.get("CODEX_CHATGPT_APP_NAME") or "").strip()
    if override:
        return normalize_app_name(override)
    value = _configured_values()
    return normalize_app_name(value.get("app_name") or DEFAULT_APP_NAME)


def configured_regular_web_mode() -> str:
    """Return the durable user-selected mode for ordinary web GPT sessions."""
    override = str(os.environ.get("CODEX_CHATGPT_REGULAR_WEB_MODE") or "").strip()
    if override:
        return normalize_regular_web_mode(override)
    value = _configured_values()
    return normalize_regular_web_mode(
        value.get("regular_web_mode") or DEFAULT_REGULAR_WEB_MODE
    )
