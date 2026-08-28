from __future__ import annotations

import hashlib
import json
from pathlib import Path


def write_prebrowser_attach_refusal(
    root: Path,
    *,
    owner: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    run_id: str = "20260828T140214Z-48451a5d41d6",
) -> Path:
    """Write the exact bounded Oracle 0.18 persistent-attach failure shape."""
    project_root = root / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    run_dir = root / "projects" / "projectkey" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    browser_temp = run_dir / "browser-temp"
    browser_temp.mkdir()
    profile_path = root / "persistent-profile"
    profile_path.mkdir()
    slug = "oracle-project-48451a5d41"
    mission_path = run_dir / "mission.md"
    mission_path.write_text("read-only review mission\n", encoding="utf-8")
    mission_sha = hashlib.sha256(mission_path.read_bytes()).hexdigest()
    output_path = run_dir / "output.md"
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    transcript_path = run_dir / "transcript.md"
    stdout = (
        "🧿 oracle 0.18.0 — Your code's confessional booth.\n"
        f"Session: {slug}\n"
        "Mode: browser foreground\n"
        "Models: 1\n"
        "Detach: no\n"
        f"Reattach: oracle session {slug}\n"
        "Launching browser mode (target=GPT-5.6 Sol; requested=gpt-5.6-sol) with ~444 tokens.\n"
        "This run can take up to an hour (usually ~10 minutes).\n"
        "[browser] Browser control: attach to an already-running local Chrome session; "
        "may focus/control the browser UI.\n"
        "[browser] Browser guidance: Oracle opens a dedicated tab and leaves the existing "
        "browser process alone.\n"
        "[browser] Acquired ChatGPT browser slot f554424e (3 max).\n"
        "[browser] Released ChatGPT browser slot f554424e.\n"
        "ERROR: connect ECONNREFUSED 127.0.0.1:19356\n"
        "User error (browser-automation): connect ECONNREFUSED 127.0.0.1:19356\n"
    )
    stderr = (
        "npm notice run fixture@0.1.0 npx\n"
        "npm notice run oracle --engine browser --model gpt-5.6-sol "
        "--browser-model-strategy select --browser-thinking-time pro "
        "--browser-research off --browser-archive never --browser-timeout 100m "
        "--browser-attach-running --remote-chrome 127.0.0.1:19356 "
        f"--slug {slug} --prompt @Chat On Steroids Core Read the exact immutable mission. "
        f"--write-output {output_path.resolve()}\n"
    )
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    transcript_path.write_bytes(stdout_path.read_bytes() + stderr_path.read_bytes())
    state = {
        "schema": "codex.chatgpt.oracle-run-state/v1",
        "run_id": run_id,
        "project_root": str(project_root.resolve()),
        "mode": "browser",
        "transport": "pro-devspace",
        "app_name": "Chat On Steroids Core",
        "profile": {
            "model": "gpt-5.6-sol",
            "model_strategy": "select",
            "thinking_time": "pro",
            "copy_profile": None,
            "browser_attach": {
                "host": "127.0.0.1",
                "port": 19356,
                "profile_path": str(profile_path.resolve()),
            },
        },
        "originating_task": {
            "schema": "codex.chatgpt.oracle-task-owner/v1",
            "source_thread_id": owner,
            "binding": "bound",
        },
        "ownership": {
            "schema": "codex.chatgpt.oracle-ownership/v1",
            "source_thread_id": owner,
            "binding": "bound",
            "project_root_sha256": "a" * 64,
            "run_id": run_id,
            "mission_sha256": mission_sha,
            "slug": slug,
        },
        "transport_status": "failed",
        "task_outcome": "pending",
        "mission": {
            "path": str(mission_path),
            "transport_path": str(mission_path),
            "sha256": mission_sha,
        },
        "oracle": {
            "resolved_version": "0.18.0",
            "command": ["npx.cmd", "-y", "@steipete/oracle@0.18.0"],
            "slug": slug,
            "session_locator": slug,
        },
        "artifacts": {
            "output": str(output_path),
            "transcript": str(transcript_path),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "browser_temp": str(browser_temp),
        },
        "browser_identity": {
            "schema": "codex.chatgpt.oracle-browser-identity/v1",
            "expected_cdp_port": 19356,
            "mode": "persistent-attach",
            "expected_profile_path": str(profile_path.resolve()),
            "receipt_path": None,
            "receipt_sha256": None,
        },
        "status": "attention_required",
        "exit_code": 1,
        "session_authority": "submitted_unknown",
        "terminal_harvested": False,
        "artifact_sha256": None,
        "browser_observer": {
            "status": "process-exited",
            "oracle_process_pid": 2147483000,
            "timeout_is_terminal": False,
        },
    }
    state_path = run_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (run_dir / "ownership-receipt.json").write_text(json.dumps({
        "schema": "codex.chatgpt.oracle-ownership-receipt/v1",
        "source_thread_id": owner,
        "binding": "bound",
        "project_root": state["project_root"],
        "project_root_sha256": state["ownership"]["project_root_sha256"],
        "run_id": run_id,
        "mission_sha256": mission_sha,
        "slug": slug,
        "expected_cdp_port": 19356,
        "browser_temp": str(browser_temp),
    }), encoding="utf-8")
    return run_dir
