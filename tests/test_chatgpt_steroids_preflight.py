from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "chatgpt_steroids_preflight.py"


def load_module():
    name = "chatgpt_steroids_preflight_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def roots(tmp_path: Path) -> tuple[Path, Path]:
    profile = tmp_path / "profile"
    extension = tmp_path / "extension"
    profile.mkdir()
    extension.mkdir()
    (extension / "manifest.json").write_text("{}\n", encoding="utf-8")
    return profile.resolve(), extension.resolve()


def process(profile: Path, extension: Path, *, port: int = 19356) -> dict:
    return {
        "listenerCount": 1,
        "processCount": 1,
        "pid": 4242,
        "executablePath": r"C:\browsers\chrome.exe",
        "commandLine": (
            rf'chrome.exe --user-data-dir="{profile}" --remote-debugging-port={port} '
            rf'--load-extension="{extension}" https://chatgpt.com/'
        ),
    }


def version(port: int = 19356) -> dict:
    return {
        "Browser": "Chrome/152.0.0.0",
        "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/browser/exact-uuid",
    }


def test_accepts_only_exact_extension_enabled_loopback_controller(tmp_path: Path) -> None:
    module = load_module()
    profile, extension = roots(tmp_path)
    result = module.ensure_persistent_controller_ready(
        host="127.0.0.1",
        port=19356,
        profile=profile,
        extension_root=extension,
        process_probe=lambda host, port: process(profile, extension),
        version_probe=lambda host, port: version(),
    )

    assert result["ok"] is True
    assert result["extension_load_proven"] is True
    assert result["submitted_question"] is False
    assert result["profile"] == str(profile)
    assert result["extension_root"] == str(extension)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda item, profile, extension: {**item, "commandLine": item["commandLine"].replace(f' --load-extension="{extension}"', "")}, "STEROIDS_CONTROLLER_EXTENSION_UNVERIFIED"),
        (lambda item, profile, extension: {**item, "commandLine": item["commandLine"].replace(str(profile), str(profile.parent / "other"))}, "STEROIDS_CONTROLLER_EXTENSION_UNVERIFIED"),
        (lambda item, profile, extension: {**item, "commandLine": item["commandLine"].replace(str(extension), str(extension.parent / "other"))}, "STEROIDS_CONTROLLER_EXTENSION_UNVERIFIED"),
        (lambda item, profile, extension: {"listenerCount": 0, "processCount": 0}, "STEROIDS_CONTROLLER_LISTENER_AMBIGUOUS"),
    ],
)
def test_rejects_missing_or_mismatched_controller_evidence(
    tmp_path: Path, mutation, code: str
) -> None:
    module = load_module()
    profile, extension = roots(tmp_path)
    observed = mutation(process(profile, extension), profile, extension)

    with pytest.raises(module.SteroidsPreflightError) as exc:
        module.ensure_persistent_controller_ready(
            host="127.0.0.1",
            port=19356,
            profile=profile,
            extension_root=extension,
            process_probe=lambda host, port: observed,
            version_probe=lambda host, port: version(),
        )
    assert exc.value.code == code


def test_rejects_nonloopback_or_substituted_websocket(tmp_path: Path) -> None:
    module = load_module()
    profile, extension = roots(tmp_path)

    with pytest.raises(module.SteroidsPreflightError) as endpoint:
        module.ensure_persistent_controller_ready(
            host="localhost",
            port=19356,
            profile=profile,
            extension_root=extension,
            process_probe=lambda host, port: process(profile, extension),
            version_probe=lambda host, port: version(),
        )
    assert endpoint.value.code == "STEROIDS_CONTROLLER_ENDPOINT_INVALID"

    with pytest.raises(module.SteroidsPreflightError) as websocket:
        module.ensure_persistent_controller_ready(
            host="127.0.0.1",
            port=19356,
            profile=profile,
            extension_root=extension,
            process_probe=lambda host, port: process(profile, extension),
            version_probe=lambda host, port: {
                "Browser": "Chrome",
                "webSocketDebuggerUrl": "ws://127.0.0.1:19357/devtools/browser/substitute",
            },
        )
    assert websocket.value.code == "STEROIDS_CONTROLLER_CDP_IDENTITY_INVALID"


def test_managed_launcher_verifies_reuse_and_never_rewrites_profile_metadata() -> None:
    text = (MODULE_PATH.with_name("start_chat_on_steroids_chrome.ps1")).read_text(encoding="utf-8")

    assert "chatgpt_steroids_preflight.py" in text
    assert "--load-extension=$Extension" in text
    assert "STEROIDS_PERSISTENT_BROWSER_INCOMPATIBLE" in text
    assert "Stop-Process" not in text
    assert "DevToolsActivePort" not in text
    assert "WriteAllText" not in text
