from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest


RUNNER_PATH = Path(__file__).resolve().parents[1] / "bin" / "chatgpt_oracle_run.py"
OWNER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FOREIGN = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def load_runner():
    name = "chatgpt_oracle_followup_test"
    spec = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runner = load_runner()
    project = tmp_path / "project"
    project.mkdir()
    mission = project / "parent.md"
    mission.write_text("parent task", encoding="utf-8")
    followup = project / "followup.md"
    followup.write_text("follow up only", encoding="utf-8")
    host = tmp_path / "host"
    run_root = host / "runs"
    monkeypatch.setenv("CODEX_ORACLE_STATE_ROOT", str(host))
    monkeypatch.setenv("CODEX_THREAD_ID", OWNER)
    manifest = tmp_path / "parent.json"
    manifest.write_text(json.dumps({
        "schema": "codex.chatgpt.oracle-run/v1",
        "project_root": str(project), "mission_path": str(mission), "app_name": "codex",
        "mode": "browser", "transport": "pro-devspace-readonly", "run_root": str(run_root),
        "oracle_command": ["oracle"], "model": "gpt-5.6-sol", "model_strategy": "select",
        "thinking_time": "heavy", "research": "off", "task_outcome_contract": "v1",
        "source_thread_id": OWNER,
    }), encoding="utf-8")
    config = runner.STATE.load_manifest(manifest, bind_runtime_task=True)
    layout = runner.STATE.create_layout(config, run_id="parent-followup-0001")
    layout.run_dir.mkdir(parents=True)
    layout.browser_temp_path.mkdir()
    (layout.browser_temp_path / "profile").mkdir()
    layout.output_path.write_text("answer\nTASK_OUTCOME: EXECUTED\n", encoding="utf-8")
    layout.transcript_path.write_text("terminal transcript", encoding="utf-8")
    Path(str(layout.run_dir / "mission.md")).write_bytes(mission.read_bytes())
    runner.STATE.write_json_atomic(
        layout.state_path,
        runner.STATE.state_payload(config, layout, status="prepared", resolved_version="oracle 0.17.1", cdp_port=43101),
    )
    runner.STATE.persist_ownership_receipt(layout.state_path, oracle_process_pid=100)
    session_root = tmp_path / "sessions"
    monkeypatch.setenv("ORACLE_SESSION_ROOT", str(session_root))
    url = "https://chatgpt.com/c/exact-parent-conversation"
    meta = {"browser": {"runtime": {
        "chromePid": 101, "controllerPid": 100, "chromePort": 43101,
        "userDataDir": str(layout.browser_temp_path / "profile"), "chromeTargetId": "exact-target", "tabUrl": url,
    }}}
    meta_path = session_root / layout.slug / "meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert runner.STATE.capture_browser_identity_receipt(layout.state_path) is not None
    runner.STATE.update_state(
        layout.state_path, status="complete", session_authority="terminal", terminal_harvested=True,
        transport_status="complete", task_outcome="executed", artifact_sha256=hashlib.sha256(layout.output_path.read_bytes()).hexdigest(),
    )
    return runner, layout, followup


def test_followup_dry_run_is_same_task_and_same_conversation_without_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)

    result = runner.followup_run(layout.run_dir, mission_path=mission, round_key="round-1", dry_run=True)

    assert result["ok"] is True
    assert result["submitted_question"] is False
    assert result["parent_conversation_url"] == "https://chatgpt.com/c/exact-parent-conversation"
    assert result["argv_plan"][:2] == ["--followup", layout.slug]
    assert not Path(result["manifest_path"]).exists()
    assert not Path(result["round_receipt_path"]).exists()


@pytest.mark.parametrize("mutation, code", [
    ("foreign", "FOREIGN_TASK_SESSION"),
    ("legacy", "FOLLOWUP_PARENT_LEGACY_UNBOUND"),
    ("nonterminal", "FOLLOWUP_PARENT_NOT_EXECUTED"),
    ("writable", "FOLLOWUP_PARENT_PROFILE_FORBIDDEN"),
    ("attachment", "FOLLOWUP_PARENT_PROFILE_FORBIDDEN"),
    ("missing-url", "FOLLOWUP_PARENT_CONVERSATION_INVALID"),
    ("tamper-output", "FOLLOWUP_PARENT_ARTIFACT_INVALID"),
])
def test_followup_rejects_foreign_or_nonqualifying_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, code: str
) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)
    if mutation == "foreign":
        monkeypatch.setenv("CODEX_THREAD_ID", FOREIGN)
    elif mutation == "tamper-output":
        layout.output_path.write_text("different bytes", encoding="utf-8")
    else:
        state = runner.STATE.load_state(layout.state_path)
        if mutation == "legacy":
            state["originating_task"] = {"schema": "codex.chatgpt.oracle-task-owner/v1", "source_thread_id": None, "binding": "legacy-unbound"}
            state["ownership"]["source_thread_id"] = None
            state["ownership"]["binding"] = "legacy-unbound"
        elif mutation == "nonterminal":
            state["status"] = "running"
            state["terminal_harvested"] = False
        elif mutation == "writable":
            state["transport"] = "pro-devspace"
        elif mutation == "attachment":
            state["transport"] = "pro-attachment-only"
        elif mutation == "missing-url":
            state["oracle"].pop("conversation_url", None)
        runner.STATE.write_json_atomic(layout.state_path, state)

    with pytest.raises(runner.OracleRunError) as exc:
        runner.followup_run(layout.run_dir, mission_path=mission, round_key="round-1", dry_run=True)

    assert exc.value.code == code


def test_followup_duplicate_round_and_new_conversation_are_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)
    receipt_path = layout.run_dir / "followup-rounds" / "round-1.json"
    receipt_path.parent.mkdir()
    receipt_path.write_text("{}", encoding="utf-8")
    with pytest.raises(runner.OracleRunError) as duplicate:
        runner.followup_run(layout.run_dir, mission_path=mission, round_key="round-1", dry_run=True)
    assert duplicate.value.code == "FOLLOWUP_ROUND_DUPLICATE"
    receipt_path.unlink()

    original_receipt = runner.STATE.proven_browser_identity_receipt
    parent_dir = layout.run_dir

    def fake_execute(manifest_path, **kwargs):
        child_run = Path(json.loads(Path(manifest_path).read_text(encoding="utf-8"))["run_root"]) / "followup-child-0001"
        child_run.mkdir(parents=True)
        (child_run / "state.json").write_text(
            json.dumps({"schema": "codex.chatgpt.oracle-run-state/v1", "oracle": {}}), encoding="utf-8"
        )
        return {"ok": True, "run_dir": str(child_run)}

    def fake_receipt(state_path):
        if Path(state_path).parent == parent_dir:
            return original_receipt(state_path)
        return {"payload": {"conversation_url": "https://chatgpt.com/c/a-different-conversation"}}

    monkeypatch.setattr(runner, "execute_run", fake_execute)
    monkeypatch.setattr(runner.STATE, "proven_browser_identity_receipt", fake_receipt)
    with pytest.raises(runner.OracleRunError) as mismatch:
        runner.followup_run(
            layout.run_dir, mission_path=mission, round_key="round-2", run_id="followup-child-0001"
        )
    assert mismatch.value.code == "FOLLOWUP_CONVERSATION_IDENTITY_UNVERIFIED"
    assert (layout.run_dir / "followup-rounds" / "round-2.result.json").is_file()


@pytest.mark.parametrize("state_fields", [
    {"status": "complete", "session_authority": "terminal", "terminal_harvested": True, "task_outcome": "executed"},
    {"status": "attention_required", "session_authority": "terminal", "terminal_harvested": True, "task_outcome": "blocked"},
    {"status": "failed", "session_authority": "submitted_unknown", "terminal_harvested": False, "task_outcome": "pending"},
])
def test_followup_non_pre_submit_outcomes_always_seal_a_reverifiable_result_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state_fields: dict
) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)
    original_receipt = runner.STATE.proven_browser_identity_receipt

    def fake_execute(manifest_path, **kwargs):
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        child_run = Path(payload["run_root"]) / payload["run_id"]
        child_run.mkdir(parents=True)
        child_state = {"schema": "codex.chatgpt.oracle-run-state/v1", "run_id": payload["run_id"], "oracle": {}, **state_fields}
        (child_run / "state.json").write_text(json.dumps(child_state), encoding="utf-8")
        return {"ok": state_fields["task_outcome"] == "executed", "run_dir": str(child_run)}

    def fake_receipt(state_path):
        if Path(state_path).parent == layout.run_dir:
            return original_receipt(state_path)
        return {"sha256": "c" * 64, "payload": {"conversation_url": "https://chatgpt.com/c/exact-parent-conversation"}}

    monkeypatch.setattr(runner, "execute_run", fake_execute)
    monkeypatch.setattr(runner.STATE, "proven_browser_identity_receipt", fake_receipt)
    result = runner.followup_run(
        layout.run_dir, mission_path=mission, round_key=f"round-{state_fields['task_outcome']}",
        run_id=f"followup-{state_fields['task_outcome']}-0001",
    )

    receipt = Path(result["followup_round_result_receipt"]["path"])
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["conversation_binding"]["identity_status"] == "same-exact-conversation"
    assert payload["child"]["task_outcome"] == state_fields["task_outcome"]
    assert payload["child"]["output"]["present"] is False


def test_followup_missing_child_browser_receipt_is_uncertain_and_locks_only_the_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)
    original_receipt = runner.STATE.proven_browser_identity_receipt

    def fake_execute(manifest_path, **kwargs):
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        child_run = Path(payload["run_root"]) / payload["run_id"]
        child_run.mkdir(parents=True)
        (child_run / "state.json").write_text(json.dumps({
            "schema": "codex.chatgpt.oracle-run-state/v1", "run_id": payload["run_id"], "oracle": {},
            "status": "failed", "session_authority": "submitted_unknown", "terminal_harvested": False,
            "task_outcome": "pending",
        }), encoding="utf-8")
        return {"ok": False, "run_dir": str(child_run)}

    def fake_receipt(state_path):
        return original_receipt(state_path) if Path(state_path).parent == layout.run_dir else None

    monkeypatch.setattr(runner, "execute_run", fake_execute)
    monkeypatch.setattr(runner.STATE, "proven_browser_identity_receipt", fake_receipt)
    with pytest.raises(runner.OracleRunError) as exc:
        runner.followup_run(layout.run_dir, mission_path=mission, round_key="round-absence", run_id="followup-absence-0001")

    assert exc.value.code == "FOLLOWUP_CONVERSATION_IDENTITY_UNVERIFIED"
    child_state = json.loads((layout.run_dir.parent / "followup-absence-0001" / "state.json").read_text(encoding="utf-8"))
    assert child_state["status"] == "attention_required"
    assert (layout.run_dir / "followup-rounds" / "round-absence.result.json").is_file()
