from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


class SteroidsPreflightError(RuntimeError):
    def __init__(self, code: str, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence or {}

    def envelope(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {"code": self.code, "message": str(self), "evidence": self.evidence},
        }


def default_extension_root(platform_name: str | None = None) -> Path:
    configured = str(os.environ.get("CHAT_ON_STEROIDS_EXTENSION_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser()
    platform = os.name if platform_name is None else platform_name
    if platform == "nt":
        appdata = str(os.environ.get("APPDATA") or "").strip()
        if not appdata:
            raise SteroidsPreflightError(
                "STEROIDS_EXTENSION_CONFIG_REQUIRED",
                "APPDATA or CHAT_ON_STEROIDS_EXTENSION_ROOT is required for the persistent controller",
            )
        return Path(appdata) / "chat-on-steroids" / "extension"
    return Path.home() / ".config" / "chat-on-steroids" / "extension"


def _exact_directory(path: Path, *, code: str, label: str) -> Path:
    raw = path.expanduser()
    if not raw.is_absolute() or raw.is_symlink():
        raise SteroidsPreflightError(code, f"{label} must be an absolute real directory")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise SteroidsPreflightError(code, f"{label} does not exist", {"path": str(raw)}) from exc
    if not resolved.is_dir():
        raise SteroidsPreflightError(code, f"{label} must be a directory", {"path": str(resolved)})
    return resolved


def _powershell_listener_process(host: str, port: int) -> dict[str, Any]:
    if host != "127.0.0.1" or not isinstance(port, int):
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_ENDPOINT_INVALID",
            "the process probe accepts only an exact loopback host and integer port",
        )
    script = r"""
$ErrorActionPreference = 'Stop'
$hostName = '127.0.0.1'
$portNumber = __PORT__
$connections = @(Get-NetTCPConnection -State Listen -LocalPort $portNumber -ErrorAction Stop |
  Where-Object { $_.LocalAddress -eq $hostName })
$pids = @($connections | ForEach-Object { [int]$_.OwningProcess } | Sort-Object -Unique)
if ($pids.Count -ne 1) {
  [pscustomobject]@{ listenerCount = $connections.Count; processCount = $pids.Count } | ConvertTo-Json -Compress
  exit 0
}
$process = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pids[0]) -ErrorAction Stop
[pscustomobject]@{
  listenerCount = $connections.Count
  processCount = 1
  pid = [int]$process.ProcessId
  executablePath = [string]$process.ExecutablePath
  commandLine = [string]$process.CommandLine
} | ConvertTo-Json -Compress
""".replace("__PORT__", str(port))
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=15,
    )
    if completed.returncode != 0:
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_PROCESS_UNVERIFIED",
            "the persistent controller listener process could not be inspected",
            {"detail": (completed.stderr or completed.stdout).strip()[:500]},
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_PROCESS_UNVERIFIED",
            "the persistent controller process probe returned invalid output",
        ) from exc
    return value if isinstance(value, dict) else {}


def _live_version(host: str, port: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/version", timeout=5) as response:
            if response.status != 200:
                raise OSError(f"HTTP {response.status}")
            value = json.loads(response.read().decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError) as exc:
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_CDP_UNAVAILABLE",
            "the configured persistent controller CDP endpoint is unavailable",
            {"endpoint": f"{host}:{port}"},
        ) from exc
    return value if isinstance(value, dict) else {}


def _switch_value(command_line: str, name: str) -> str | None:
    pattern = re.compile(
        rf"(?:^|\s)--{re.escape(name)}=(?:\"([^\"]*)\"|'([^']*)'|(\S+))",
        re.IGNORECASE,
    )
    match = pattern.search(command_line)
    if match is None:
        return None
    return next((group for group in match.groups() if group is not None), None)


def _same_path(left: str | None, right: Path) -> bool:
    if not left:
        return False
    try:
        candidate = Path(left).expanduser().resolve(strict=True)
    except OSError:
        return False
    return os.path.normcase(str(candidate)) == os.path.normcase(str(right))


def ensure_persistent_controller_ready(
    *,
    host: str,
    port: int,
    profile: Path,
    platform_name: str | None = None,
    extension_root: Path | None = None,
    process_probe: Callable[[str, int], dict[str, Any]] | None = None,
    version_probe: Callable[[str, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prove the exact persistent Chrome was launched with the stable extension.

    A matching CDP port and profile are not enough: Chrome can reuse that pair
    without loading the content script that supplies caller identity.  This
    gate therefore binds the listener PID to its command line and accepts only
    an explicit load of the exact stable extension mirror.
    """
    platform = os.name if platform_name is None else platform_name
    if host != "127.0.0.1" or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_ENDPOINT_INVALID",
            "the Steroids persistent controller must use an exact 127.0.0.1 high port",
        )
    exact_profile = _exact_directory(
        Path(profile), code="STEROIDS_CONTROLLER_PROFILE_INVALID", label="persistent controller profile"
    )
    exact_extension = _exact_directory(
        extension_root or default_extension_root(platform),
        code="STEROIDS_EXTENSION_MISSING",
        label="stable Chat On Steroids extension",
    )
    manifest = exact_extension / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise SteroidsPreflightError(
            "STEROIDS_EXTENSION_MISSING",
            "the stable Chat On Steroids extension has no regular manifest.json",
            {"extension_root": str(exact_extension)},
        )
    if process_probe is None:
        if platform != "nt":
            raise SteroidsPreflightError(
                "STEROIDS_CONTROLLER_PROCESS_PROOF_UNSUPPORTED",
                "persistent controller process proof is not implemented on this platform",
            )
        process_probe = _powershell_listener_process
    process = process_probe(host, port)
    if process.get("processCount") != 1 or not isinstance(process.get("pid"), int):
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_LISTENER_AMBIGUOUS",
            "the configured persistent controller must have exactly one inspectable listener owner",
            {
                "endpoint": f"{host}:{port}",
                "listener_count": process.get("listenerCount"),
                "process_count": process.get("processCount"),
            },
        )
    command_line = str(process.get("commandLine") or "")
    observed_profile = _switch_value(command_line, "user-data-dir")
    observed_port = _switch_value(command_line, "remote-debugging-port")
    observed_extension = _switch_value(command_line, "load-extension")
    if (
        not _same_path(observed_profile, exact_profile)
        or observed_port != str(port)
        or not _same_path(observed_extension, exact_extension)
    ):
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_EXTENSION_UNVERIFIED",
            "the live CDP listener is not the exact extension-enabled Steroids controller; close it manually and run start_chat_on_steroids_chrome.ps1",
            {
                "endpoint": f"{host}:{port}",
                "pid": process["pid"],
                "profile_matches": _same_path(observed_profile, exact_profile),
                "port_matches": observed_port == str(port),
                "extension_matches": _same_path(observed_extension, exact_extension),
            },
        )
    version = (version_probe or _live_version)(host, port)
    ws_url = str(version.get("webSocketDebuggerUrl") or "")
    parsed = urlparse(ws_url)
    try:
        websocket_port = parsed.port
    except ValueError:
        websocket_port = None
    if (
        parsed.scheme != "ws"
        or parsed.hostname != host
        or websocket_port != port
        or re.fullmatch(r"/devtools/browser/[A-Za-z0-9-]+", parsed.path) is None
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
    ):
        raise SteroidsPreflightError(
            "STEROIDS_CONTROLLER_CDP_IDENTITY_INVALID",
            "the live CDP browser WebSocket does not match the exact loopback controller endpoint",
            {"endpoint": f"{host}:{port}"},
        )
    return {
        "ok": True,
        "schema": "codex.chatgpt.steroids-controller-preflight/v1",
        "endpoint": f"{host}:{port}",
        "pid": process["pid"],
        "profile": str(exact_profile),
        "extension_root": str(exact_extension),
        "browser": str(version.get("Browser") or ""),
        "browser_websocket_path": parsed.path,
        "extension_load_proven": True,
        "submitted_question": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the extension-enabled Steroids persistent controller.")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--extension", type=Path)
    args = parser.parse_args(argv)
    match = re.fullmatch(r"127\.0\.0\.1:([0-9]{4,5})", args.endpoint)
    if match is None:
        result = SteroidsPreflightError(
            "STEROIDS_CONTROLLER_ENDPOINT_INVALID",
            "--endpoint must be exact 127.0.0.1:port",
        ).envelope()
        print(json.dumps(result, ensure_ascii=False))
        return 1
    try:
        result = ensure_persistent_controller_ready(
            host="127.0.0.1",
            port=int(match.group(1)),
            profile=args.profile,
            extension_root=args.extension,
        )
    except SteroidsPreflightError as exc:
        print(json.dumps(exc.envelope(), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
