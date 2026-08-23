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
    meta["browser"]["runtime"]["promptSubmitted"] = True
    meta["browser"]["archive"] = {
        "mode": "auto", "attempted": True, "archived": True, "conversationUrl": url,
    }
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
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
    assert result["round_receipt_plan"]["parent"]["archive_contract"]["was_archived"] is True
    payload = runner._followup_manifest_payload(
        runner.STATE.load_state(layout.state_path), mission_path=mission,
        run_id="followup-archive-plan-0001",
        archive_contract=result["round_receipt_plan"]["parent"]["archive_contract"],
    )
    assert payload["archive"] == "always"


def test_followup_archived_parent_url_mismatch_fails_before_child_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)
    meta_path = Path(os.environ["ORACLE_SESSION_ROOT"]) / layout.slug / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["browser"]["archive"]["conversationUrl"] = "https://chatgpt.com/c/other-conversation"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(runner.OracleRunError) as exc:
        runner.followup_run(layout.run_dir, mission_path=mission, round_key="archive-mismatch", dry_run=True)

    assert exc.value.code == "FOLLOWUP_PARENT_ARCHIVE_IDENTITY_INVALID"
    assert not (layout.run_dir / "followup-rounds").exists()


def test_followup_child_binding_is_append_only_and_exact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)
    plan = runner.followup_run(
        layout.run_dir, mission_path=mission, round_key="bound-round",
        run_id="followup-bound-child-0001", dry_run=True,
    )
    reservation_path = Path(plan["round_receipt_path"])
    reservation_path.parent.mkdir(parents=True)
    reservation_path.write_text(
        json.dumps(plan["round_receipt_plan"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    reservation_sha256 = hashlib.sha256(reservation_path.read_bytes()).hexdigest()
    parent = runner.STATE.load_state(layout.state_path)
    archive_contract = runner._followup_archive_contract(
        parent, "https://chatgpt.com/c/exact-parent-conversation"
    )
    manifest_payload = runner._followup_manifest_payload(
        parent, mission_path=mission, run_id="followup-bound-child-0001",
        archive_contract=archive_contract,
    )
    manifest_payload["run_root"] = str(layout.run_dir.parent)
    manifest = tmp_path / "child.json"
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
    config = runner.STATE.load_manifest(manifest, bind_runtime_task=True)
    child = runner.STATE.create_layout(config, run_id=config.requested_run_id)
    child.run_dir.mkdir()
    expected_port = plan["round_receipt_plan"]["child"]["expected_cdp_port"]
    child.state_path.write_text(json.dumps(runner.STATE.state_payload(
        config, child, status="prepared", resolved_version="oracle 0.17.1", cdp_port=expected_port
    )), encoding="utf-8")
    binding = {
        "schema": "codex.chatgpt.oracle-followup-binding/v1",
        "source_thread_id": OWNER,
        "round_key": "bound-round",
        "reservation_path": str(reservation_path),
        "reservation_sha256": reservation_sha256,
        "parent": plan["round_receipt_plan"]["parent"],
        "child": plan["round_receipt_plan"]["child"],
        "conversation_url": "https://chatgpt.com/c/exact-parent-conversation",
    }

    recorded = runner.STATE.persist_followup_binding(child.state_path, binding)

    assert runner.STATE.proven_followup_binding(child.state_path)["sha256"] == recorded["sha256"]
    binding["round_key"] = "tampered"
    with pytest.raises(runner.STATE.OracleStateError):
        runner.STATE.persist_followup_binding(child.state_path, binding)


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
        child_slug = runner.STATE.oracle_slug(Path(payload["project_root"]), payload["run_id"])
        child_state = {"schema": "codex.chatgpt.oracle-run-state/v1", "run_id": payload["run_id"], "oracle": {"slug": child_slug}, **state_fields}
        (child_run / "state.json").write_text(json.dumps(child_state), encoding="utf-8")
        child_meta = Path(os.environ["ORACLE_SESSION_ROOT"]) / child_slug / "meta.json"
        child_meta.parent.mkdir(parents=True, exist_ok=True)
        child_meta.write_text(json.dumps({"browser": {"archive": {
            "mode": "always", "attempted": True, "archived": True,
            "conversationUrl": "https://chatgpt.com/c/exact-parent-conversation",
        }}}), encoding="utf-8")
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


def test_followup_textarea_absent_requires_harvest_and_owner_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, layout, mission = make_parent(tmp_path, monkeypatch)

    def fake_execute(manifest_path, **kwargs):
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        config = runner.STATE.load_manifest(Path(manifest_path), bind_runtime_task=True)
        child = runner.STATE.create_layout(config, run_id=config.requested_run_id)
        child.run_dir.mkdir()
        child_mission = child.run_dir / "mission.md"
        child_mission.write_bytes(Path(payload["mission_path"]).read_bytes())
        text = (
            f"🧿 oracle 0.17.1 — test\nSession: {child.slug}\nMode: browser foreground\n"
            "Models: 1\nDetach: no\n"
            f"Reattach: oracle session {child.slug}\n"
            "Launching browser mode (target=GPT-5.6 Sol; requested=gpt-5.6-sol) with ~1 tokens.\n"
            "This run can take up to an hour (usually ~10 minutes).\n"
            "ERROR: Prompt textarea did not appear before timeout\n"
            "User error (browser-automation): Prompt textarea did not appear before timeout\n"
        )
        child.stdout_path.write_text(text, encoding="utf-8")
        child.stderr_path.write_bytes(b"")
        child.transcript_path.write_text(text, encoding="utf-8")
        state = runner.STATE.state_payload(
            config, child, status="attention_required", resolved_version="oracle 0.17.1",
            exit_code=1, cdp_port=kwargs["_cdp_port"],
        )
        state.update({
            "session_authority": "submitted_unknown", "transport_status": "failed",
            "task_outcome": "pending", "terminal_harvested": False,
        })
        runner.STATE.write_json_atomic(child.state_path, state)
        runner.STATE.persist_followup_binding(child.state_path, kwargs["_followup_binding"])
        runner.STATE.persist_ownership_receipt(child.state_path, oracle_process_pid=100)
        meta_path = Path(os.environ["ORACLE_SESSION_ROOT"]) / child.slug / "meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        parent_url = kwargs["_followup_binding"]["conversation_url"]
        meta_path.write_text(json.dumps({
            "id": child.slug, "status": "error", "completedAt": "2026-08-23T00:00:00Z", "mode": "browser", "model": "gpt-5.6-sol",
            "browser": {"config": {"resumeConversationUrl": parent_url}},
            "options": {"browserConfig": {"resumeConversationUrl": parent_url}},
            "error": {"category": "browser-automation", "message": "Prompt textarea did not appear before timeout", "details": {"stage": "execute-browser"}},
        }), encoding="utf-8")
        return {"ok": False, "run_dir": str(child.run_dir)}

    monkeypatch.setattr(runner, "execute_run", fake_execute)
    with pytest.raises(runner.OracleRunError):
        runner.followup_run(
            layout.run_dir, mission_path=mission, round_key="textarea-absent",
            run_id="followup-b2d1aed7ba6145db8f2e56c111d4a856",
        )
    child_state = layout.run_dir.parent / "followup-b2d1aed7ba6145db8f2e56c111d4a856" / "state.json"
    assert runner.STATE.bounded_task_owned_prompt_timeout_harvest_evidence(child_state) is not None
    assert runner.STATE._user_confirmable_no_submission_evidence(child_state) is None
    child_slug = runner.STATE.load_state(child_state)["oracle"]["slug"]
    (child_state.parent / "recovery-harvest-stdout.log").write_text(
        f'No live ChatGPT tab matched session "{child_slug}".\n', encoding="utf-8"
    )
    (child_state.parent / "recovery-harvest-stderr.log").write_text(
        "Cannot recover conversation: session metadata has no recoverable ChatGPT conversation URL\n",
        encoding="utf-8",
    )
    assert runner.STATE._user_confirmable_no_submission_evidence(child_state) is not None
    monkeypatch.setenv("CODEX_THREAD_ID", FOREIGN)
    with pytest.raises(runner.STATE.OracleStateError, match="different Codex task"):
        runner.STATE.settle_user_confirmed_no_submission(
            child_state, confirmation="user-confirmed-no-submission", reason="foreign must fail",
        )
    monkeypatch.setenv("CODEX_THREAD_ID", OWNER)
    settled = runner.STATE.settle_user_confirmed_no_submission(
        child_state, confirmation="user-confirmed-no-submission", reason="exact textarea absent",
    )
    assert settled["transport_status"] == "not_submitted_user_confirmed"
    assert runner.STATE.proven_user_confirmed_no_submission(child_state) is not None
    with pytest.raises(runner.OracleRunError) as duplicate:
        runner.followup_run(
            layout.run_dir, mission_path=mission, round_key="textarea-absent", dry_run=True,
        )
    assert duplicate.value.code == "FOLLOWUP_ROUND_DUPLICATE"
    tampered = runner.STATE.load_state(child_state)
    tampered["followup_binding"]["sha256"] = "b" * 64
    runner.STATE.write_json_atomic(child_state, tampered)
    assert runner.STATE.proven_user_confirmed_no_submission(child_state) is None
    assert runner.STATE._legacy_followup_reservation_for_child(child_state) is not None
    assert runner.STATE._followup_no_submission_evidence(
        child_state, require_recovery_evidence=True
    ) is None
