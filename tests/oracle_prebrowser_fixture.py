from __future__ import annotations

import hashlib
import json
from pathlib import Path


def write_prebrowser_attach_refusal(
    root: Path,
    *,
    owner: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    run_id: str = "20260828T140214Z-48451a5d41d6",
    project_root: Path | None = None,
    source_mission: Path | None = None,
    run_root: Path | None = None,
    failure: str = "econnrefused",
) -> Path:
    """Write the exact bounded Oracle 0.18 persistent-attach failure shape."""
    if failure not in {"econnrefused", "stale-ws-404"}:
        raise ValueError(f"unsupported prebrowser failure fixture: {failure}")
    root.mkdir(parents=True, exist_ok=True)
    project_root = project_root or (root / "project")
    project_root.mkdir(parents=True, exist_ok=True)
    run_dir = (run_root or (root / "projects" / "projectkey" / "runs")) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    browser_temp = run_dir / "browser-temp"
    browser_temp.mkdir()
    profile_path = root / "persistent-profile"
    profile_path.mkdir(exist_ok=True)
    slug = "oracle-project-48451a5d41"
    mission_path = run_dir / "mission.md"
    mission_path.write_bytes(
        source_mission.read_bytes()
        if source_mission is not None
        else b"read-only review mission\n"
    )
    mission_sha = hashlib.sha256(mission_path.read_bytes()).hexdigest()
    output_path = run_dir / "output.md"
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    transcript_path = run_dir / "transcript.md"
    failure_lines = (
        "ERROR: connect ECONNREFUSED 127.0.0.1:19356\n"
        "User error (browser-automation): connect ECONNREFUSED 127.0.0.1:19356\n"
        if failure == "econnrefused"
        else "ERROR: Unexpected server response: 404\n"
        "User error (browser-automation): Unexpected server response: 404\n"
    )
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
        f"{failure_lines}"
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
            "path": str(source_mission.resolve()) if source_mission is not None else str(mission_path),
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


def write_prebrowser_settlement(run_dir: Path, *, owner: str) -> Path:
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    profile = state["profile"]["browser_attach"]
    stdout = (run_dir / "stdout.log").read_text(encoding="utf-8")
    signature = (
        "persistent-attach-stale-browser-websocket-404-before-browser"
        if "Unexpected server response: 404" in stdout
        else "persistent-attach-cdp-refused-before-browser"
    )
    receipt = {
        "schema": "codex.chatgpt.oracle-prebrowser-attach-nonexecution-settlement/v1",
        "confirmation": "user-authorized-fresh-run-after-prebrowser-attach-nonexecution",
        "reason": "user confirmed no browser or review conversation existed",
        "authorized_source_thread_id": owner,
        "run_id": state["run_id"],
        "project_root": state["project_root"],
        "slug": state["oracle"]["slug"],
        "transport": state["transport"],
        "app_name": state["app_name"],
        "signature": signature,
        "endpoint": f"{profile['host']}:{profile['port']}",
        "profile_path": profile["profile_path"],
        "state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
        "transcript_sha256": hashlib.sha256((run_dir / "transcript.md").read_bytes()).hexdigest(),
        "stdout_sha256": hashlib.sha256((run_dir / "stdout.log").read_bytes()).hexdigest(),
        "stderr_sha256": hashlib.sha256((run_dir / "stderr.log").read_bytes()).hexdigest(),
        "mission_sha256": hashlib.sha256((run_dir / "mission.md").read_bytes()).hexdigest(),
        "ownership_receipt_sha256": hashlib.sha256(
            (run_dir / "ownership-receipt.json").read_bytes()
        ).hexdigest(),
        "output_absent": True,
        "retry_ordinal": 1,
        "auto_retry": False,
        "submission_action": "none",
        "authorized_at": "2026-08-28T00:00:00Z",
    }
    path = run_dir / "settlements" / "prebrowser-attach-nonexecution-fresh-run.json"
    path.parent.mkdir()
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def write_settled_owner_guard_rejection(
    root: Path,
    *,
    owner: str,
    project_root: Path,
    source_mission: Path,
    run_root: Path,
    run_id: str = "20260828T145107Z-2eb1dab4f338",
) -> Path:
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    slug = "oracle-project-2eb1dab4f3"
    profile_path = root / "persistent-profile"
    profile_path.mkdir(exist_ok=True)
    mission_path = run_dir / "mission.md"
    mission_path.write_bytes(source_mission.read_bytes())
    mission_sha = hashlib.sha256(mission_path.read_bytes()).hexdigest()
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    transcript_path = run_dir / "transcript.md"
    stdout_path.write_bytes(b"")
    stderr_path.write_text(
        "Oracle launch/run failed: PROJECT_SESSION_STILL_LIVE: an exact Oracle "
        "session still owns this project; recover it before submitting\n",
        encoding="utf-8",
    )
    transcript_path.write_bytes(stderr_path.read_bytes())
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
        "transport_status": "prepared",
        "task_outcome": "pending",
        "mission": {
            "path": str(source_mission.resolve()),
            "transport_path": str(mission_path),
            "sha256": mission_sha,
        },
        "attachments": [],
        "oracle": {
            "resolved_version": "0.18.0",
            "command": ["npx.cmd", "-y", "@steipete/oracle@0.18.0"],
            "slug": slug,
            "session_locator": slug,
        },
        "artifacts": {
            "output": str(run_dir / "output.md"),
            "transcript": str(transcript_path),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "browser_temp": str(run_dir / "browser-temp"),
        },
        "browser_identity": {
            "schema": "codex.chatgpt.oracle-browser-identity/v1",
            "expected_cdp_port": 19356,
            "mode": "persistent-attach",
            "expected_profile_path": str(profile_path.resolve()),
            "receipt_path": None,
            "receipt_sha256": None,
        },
        "status": "failed",
        "exit_code": None,
        "session_authority": "pre_submit",
        "terminal_harvested": False,
        "artifact_sha256": None,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return run_dir
