from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


CLI = Path(__file__).resolve().parents[1] / "bin" / "chatgpt_chrome_cdp.mjs"


class CdpHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/json/version":
            payload = {"Browser": "MockChrome/1", "webSocketDebuggerUrl": "ws://127.0.0.1/mock-browser"}
        elif self.path == "/json/list":
            payload = [{
                "id": "page-1",
                "type": "page",
                "title": "Mock page",
                "url": "https://example.test/",
                "webSocketDebuggerUrl": "ws://127.0.0.1/mock-page",
            }]
        else:
            self.send_response(404)
            self.end_headers()
            return
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(CLI), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_documents_full_generic_cdp_surface() -> None:
    result = run_cli("help")
    assert result.returncode == 0
    assert "version" in result.stdout
    assert "list" in result.stdout
    assert "eval" in result.stdout
    assert "call" in result.stdout
    assert "--browser" in result.stdout


def test_non_loopback_endpoint_is_rejected_before_network_access() -> None:
    result = run_cli("list", "--endpoint", "https://example.com:9222")
    assert result.returncode == 1
    assert json.loads(result.stderr)["error"]["code"] == "ENDPOINT_NOT_LOOPBACK"


def test_loopback_version_and_target_listing() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), CdpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    try:
        version = run_cli("version", "--endpoint", endpoint)
        targets = run_cli("list", "--endpoint", endpoint)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert version.returncode == 0
    assert json.loads(version.stdout)["Browser"] == "MockChrome/1"
    assert targets.returncode == 0
    assert json.loads(targets.stdout)[0]["id"] == "page-1"
