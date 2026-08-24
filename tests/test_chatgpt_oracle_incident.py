from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "chatgpt_oracle_incident.py"
DEFAULT_EVALUATOR = "99999999-9999-4999-8999-999999999999"


@pytest.fixture(autouse=True)
def _exact_evaluating_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_THREAD_ID", DEFAULT_EVALUATOR)


def load():
    name = "chatgpt_oracle_incident_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_run(
    root: Path,
    run_id: str,
    *,
    status: str,
    stdout: str = "",
    output: str | None = None,
    session_authority: str = "",
    terminal_harvested: bool = False,
    source_thread_id: str | None = None,
) -> Path:
    run_dir = root / "projects" / "projectkey" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    project_root = root / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "output.md"
    if output is not None:
        output_path.write_text(output, encoding="utf-8")
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    transcript_path = run_dir / "transcript.md"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    transcript_path.write_text(output or stdout, encoding="utf-8")
    state = {
        "schema": "codex.chatgpt.oracle-run-state/v1",
        "status": status,
        "run_id": run_id,
        "project_root": str(project_root),
        "session_authority": session_authority,
        "terminal_harvested": terminal_harvested,
        "task_outcome": "blocked" if output and "TASK_OUTCOME: BLOCKED" in output else "",
        "artifacts": {"output": str(output_path), "transcript": str(transcript_path), "stdout": str(stdout_path), "stderr": str(stderr_path)},
        "oracle": {"slug": "oracle-project-abc", "conversation_url": "https://chatgpt.com/c/exact"},
    }
    if source_thread_id is not None:
        state["ownership"] = {
            "schema": "codex.chatgpt.oracle-task-owner/v1",
            "source_thread_id": source_thread_id,
        }
        state["originating_task"] = {
            "schema": "codex.chatgpt.oracle-task-owner/v1",
            "source_thread_id": source_thread_id,
        }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return run_dir


def test_packet_carries_exact_run_bucket_and_evidence(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(
        tmp_path,
        "a" * 8,
        status="failed",
        stdout="ERROR: ChatGPT app mention was not confirmed in the composer.\n",
        source_thread_id=DEFAULT_EVALUATOR,
    )

    packet = module.validate_packet(module.build_packet(run_dir))

    assert packet["schema"] == "codex.chatgpt.oracle-incident/v2"
    assert packet["run_dir"] == str(run_dir.resolve())
    assert packet["bucket"] == "pre-submit-ui-contract"
    assert packet["signature"] == "app-mention-not-confirmed"
    assert packet["conversation_url"] == "https://chatgpt.com/c/exact"
    assert packet["evaluated_from_thread"] == DEFAULT_EVALUATOR
    assert packet["target_source_thread_id"] == DEFAULT_EVALUATOR
    assert packet["safe_for_fresh_run"] is True
    assert str(run_dir / "state.json") in packet["evidence_paths"]


def test_bound_packet_routes_only_to_exact_owner_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load()
    owner = "11111111-1111-4111-8111-111111111111"
    foreign = "22222222-2222-4222-8222-222222222222"
    run_dir = write_run(
        tmp_path,
        "owned-run",
        status="running",
        session_authority="submitted_unknown",
        source_thread_id=owner,
    )
    monkeypatch.setenv("CODEX_THREAD_ID", foreign)

    packet = module.validate_packet(module.build_packet(run_dir))

    assert packet["run_owner_source_thread_id"] == owner
    assert packet["evaluated_from_thread"] == foreign
    assert packet["target_source_thread_id"] == owner
    assert packet["ownership_scope"] == "foreign-task"
    assert packet["operational_instruction"] == {
        "schema": "codex.chatgpt.oracle-operational-instruction/v1",
        "evaluated_from_thread": foreign,
        "target_source_thread_id": owner,
        "ownership_scope": "foreign-task",
        "run_id": "owned-run",
        "slug": "oracle-project-abc",
        "action": "route-to-owner-task",
        "reason": "foreign-task-must-not-operate-on-exact-run",
        "executable_by_evaluated_thread": False,
        "fresh_state_check_required": False,
    }


def test_v2_build_requires_exact_evaluating_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load()
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    run_dir = write_run(tmp_path, "unscoped", status="failed", stdout="ERROR: unknown\n")

    with pytest.raises(module.IncidentError) as exc:
        module.build_packet(run_dir)
    assert exc.value.code == "INCIDENT_EVALUATED_FROM_THREAD_REQUIRED"


def test_legacy_v1_packet_is_evidence_only(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(tmp_path, "legacy", status="failed", stdout="ERROR: unknown\n")
    packet = module.build_packet(run_dir)
    packet["schema"] = module.LEGACY_SCHEMA
    for field in module.V2_REQUIRED_FIELDS:
        packet.pop(field, None)
    packet.pop("run_owner_source_thread_id", None)

    assert module.validate_packet(packet)["schema"] == module.LEGACY_SCHEMA
    packet["operational_instruction"] = {"action": "recover"}
    with pytest.raises(module.IncidentError) as exc:
        module.validate_packet(packet)
    assert exc.value.code == "INCIDENT_LEGACY_OPERATION_FORBIDDEN"


def test_terminal_packet_never_emits_recovery_instruction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load()
    owner = "11111111-1111-4111-8111-111111111111"
    monkeypatch.setenv("CODEX_THREAD_ID", owner)
    run_dir = write_run(
        tmp_path,
        "terminal-run",
        status="attention_required",
        output="answer\nTASK_OUTCOME: EXECUTED\n",
        session_authority="terminal",
        terminal_harvested=True,
        source_thread_id=owner,
    )

    packet = module.validate_packet(module.build_packet(run_dir))

    assert packet["lifecycle"] == "complete"
    assert packet["ownership_scope"] == "same-task"
    assert packet["operational_instruction"]["target_source_thread_id"] == owner
    assert packet["operational_instruction"]["action"] == "none"
    assert packet["operational_instruction"]["reason"] == "exact-run-already-terminal"
    assert packet["operational_instruction"]["executable_by_evaluated_thread"] is False
    assert packet["operational_instruction"]["fresh_state_check_required"] is False


def test_foreign_evaluator_gets_no_action_for_terminal_harvested_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load()
    owner = "11111111-1111-4111-8111-111111111111"
    foreign = "22222222-2222-4222-8222-222222222222"
    monkeypatch.setenv("CODEX_THREAD_ID", foreign)
    run_dir = write_run(
        tmp_path,
        "foreign-terminal",
        status="attention_required",
        output="answer\nTASK_OUTCOME: EXECUTED\n",
        session_authority="terminal",
        terminal_harvested=True,
        source_thread_id=owner,
    )

    packet = module.validate_packet(module.build_packet(run_dir))

    assert packet["evaluated_from_thread"] == foreign
    assert packet["target_source_thread_id"] == owner
    assert packet["ownership_scope"] == "foreign-task"
    assert packet["lifecycle"] == "complete"
    assert packet["operational_instruction"]["action"] == "none"
    assert packet["operational_instruction"]["executable_by_evaluated_thread"] is False
    assert packet["safe_for_fresh_run"] is False
    assert packet["unresolved_owners"] == []


def test_unresolved_owners_are_evaluated_from_run_owner_task_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load()
    owner = "11111111-1111-4111-8111-111111111111"
    foreign = "22222222-2222-4222-8222-222222222222"
    monkeypatch.setenv("CODEX_THREAD_ID", owner)
    reported = write_run(
        tmp_path,
        "reported",
        status="failed",
        stdout="ERROR: ChatGPT app mention was not confirmed in the composer.\n",
        source_thread_id=owner,
    )
    same_task = write_run(
        tmp_path,
        "same-task",
        status="running",
        session_authority="submitted_unknown",
        source_thread_id=owner,
    )
    write_run(
        tmp_path,
        "foreign-task",
        status="running",
        session_authority="submitted_unknown",
        source_thread_id=foreign,
    )

    packet = module.build_packet(reported)

    assert packet["evaluated_from_thread"] == owner
    assert [item["run_id"] for item in packet["unresolved_owners"]] == [same_task.name]
    assert packet["unresolved_owners"][0]["source_thread_id"] == owner


def test_v2_validation_rejects_cross_task_recovery_instruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load()
    owner = "11111111-1111-4111-8111-111111111111"
    foreign = "22222222-2222-4222-8222-222222222222"
    monkeypatch.setenv("CODEX_THREAD_ID", foreign)
    run_dir = write_run(
        tmp_path,
        "foreign-owned",
        status="running",
        session_authority="submitted_unknown",
        source_thread_id=owner,
    )
    packet = module.build_packet(run_dir)
    packet["operational_instruction"]["action"] = "recover --action live"

    with pytest.raises(module.IncidentError) as exc:
        module.validate_packet(packet)
    assert exc.value.code == "INCIDENT_OPERATIONAL_ACTION_INVALID"


def test_v2_validation_rejects_unknown_ownership_scope(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(tmp_path, "unknown-scope", status="failed", stdout="ERROR: unknown\n")
    packet = module.build_packet(run_dir)
    packet["ownership_scope"] = "project-wide"
    packet["operational_instruction"]["ownership_scope"] = "project-wide"

    with pytest.raises(module.IncidentError) as exc:
        module.validate_packet(packet)
    assert exc.value.code == "INCIDENT_OWNERSHIP_SCOPE_INVALID"


@pytest.mark.parametrize(
    ("owner", "scope"),
    [
        (None, "foreign-task"),
        ("11111111-1111-4111-8111-111111111111", "legacy-unbound"),
    ],
)
def test_v2_validation_rejects_impossible_owner_scope_pairs(
    tmp_path: Path, owner: str | None, scope: str
) -> None:
    module = load()
    run_dir = write_run(
        tmp_path,
        "bad-owner-scope",
        status="failed",
        stdout="ERROR: unknown\n",
        source_thread_id=owner,
    )
    packet = module.build_packet(run_dir)
    packet["ownership_scope"] = scope
    packet["operational_instruction"]["ownership_scope"] = scope

    with pytest.raises(module.IncidentError) as exc:
        module.validate_packet(packet)
    assert exc.value.code == "INCIDENT_OWNERSHIP_SCOPE_INVALID"


def test_version_resolution_prelaunch_incident_is_safe_to_retry(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(
        tmp_path,
        "v" * 8,
        status="attention_required",
        source_thread_id=DEFAULT_EVALUATOR,
    )
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["pre_submit_failure"] = {
        "code": "ORACLE_VERSION_RESOLUTION_PRELAUNCH_FAILED",
        "output_absent": True,
        "conversation_url_absent": True,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    packet = module.build_packet(run_dir)

    assert packet["bucket"] == "pre-submit-host-environment"
    assert packet["signature"] == "oracle-version-resolution-prelaunch-timeout"
    assert packet["safe_for_fresh_run"] is True


def test_model_switcher_pre_submit_incident_is_safe_to_retry(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(
        tmp_path,
        "m" * 8,
        status="attention_required",
        source_thread_id=DEFAULT_EVALUATOR,
    )
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["session_authority"] = "pre_submit"
    state["pre_submit_failure"] = {
        "code": "ORACLE_MODEL_SWITCHER_PRE_SUBMIT_FAILED",
        "output_absent": True,
        "conversation_url_absent": True,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    packet = module.build_packet(run_dir)

    assert packet["bucket"] == "pre-submit-ui-contract"
    assert packet["signature"] == "model-option-label-missing"
    assert packet["safe_for_fresh_run"] is True


def test_version_compatibility_drift_incident_is_safe_to_retry(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(
        tmp_path,
        "c" * 8,
        status="failed",
        source_thread_id=DEFAULT_EVALUATOR,
    )
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["oracle"] = {"resolved_version": "unresolved"}
    state["session_authority"] = "pre_submit"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (run_dir / "stderr.log").write_text(
        "version resolution failed: Oracle compatibility is validated only for the tested version\n",
        encoding="utf-8",
    )

    packet = module.build_packet(run_dir)

    assert packet["bucket"] == "pre-submit-host-environment"
    assert packet["signature"] == "oracle-version-resolution-prelaunch-compatibility-drift"
    assert packet["safe_for_fresh_run"] is True


def test_packet_never_marks_fresh_run_safe_while_another_session_owns_project(tmp_path: Path) -> None:
    module = load()
    failed = write_run(
        tmp_path,
        "1" * 8,
        status="failed",
        stdout="ERROR: ChatGPT app mention was not confirmed in the composer.\n",
        source_thread_id=DEFAULT_EVALUATOR,
    )
    owner = write_run(
        tmp_path,
        "2" * 8,
        status="running",
        session_authority="submitted_unknown",
        source_thread_id=DEFAULT_EVALUATOR,
    )

    packet = module.build_packet(failed)

    assert packet["safe_for_fresh_run"] is False
    assert [item["run_id"] for item in packet["unresolved_owners"]] == [owner.name]


def test_reporter_is_never_the_repair_owner(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(tmp_path, "b" * 8, status="failed", stdout="ERROR: unknown\n")

    packet = module.build_packet(run_dir)

    assert packet["reporter_role"] == module.REPORTER_ROLE
    assert packet["repair_owner"] == module.MAINTENANCE_OWNER
    assert packet["reporter_may_edit_automation_sources"] is False


def test_packet_claiming_reporter_repair_rights_is_rejected(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(tmp_path, "c" * 8, status="failed", stdout="ERROR: unknown\n")
    packet = module.build_packet(run_dir)

    packet["reporter_may_edit_automation_sources"] = True
    with pytest.raises(module.IncidentError) as exc:
        module.validate_packet(packet)
    assert exc.value.code == "INCIDENT_REPORTER_SCOPE_INVALID"


def test_packet_reassigning_the_repair_owner_is_rejected(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(tmp_path, "d" * 8, status="failed", stdout="ERROR: unknown\n")
    packet = module.build_packet(run_dir)

    packet["repair_owner"] = "some-other-project-session"
    with pytest.raises(module.IncidentError) as exc:
        module.validate_packet(packet)
    assert exc.value.code == "INCIDENT_REPAIR_OWNER_INVALID"


def test_unclassified_bucket_value_is_rejected(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(tmp_path, "e" * 8, status="failed", stdout="ERROR: unknown\n")
    packet = module.build_packet(run_dir)

    packet["bucket"] = "made-up-bucket"
    with pytest.raises(module.IncidentError) as exc:
        module.validate_packet(packet)
    assert exc.value.code == "INCIDENT_BUCKET_UNKNOWN"


def test_active_run_is_not_marked_safe_for_a_fresh_run(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(
        tmp_path,
        "f" * 8,
        status="running",
        session_authority="submitted_unknown",
        stdout="status=response streaming\n",
    )

    packet = module.build_packet(run_dir)

    assert packet["lifecycle"] == "running"
    assert packet["safe_for_fresh_run"] is False


def test_recursive_self_observation_needs_append_only_user_authority(tmp_path: Path) -> None:
    module = load()
    run_id = "recursive1234"
    slug = "oracle-project-abc"
    output = (
        f"run ID: {run_id}\nexact slug: {slug}\nstatus: running\n"
        "task_outcome: pending\noutput.md absent\n"
        "continue-observing-same-exact-session\nTASK_OUTCOME: BLOCKED\n"
    )
    run_dir = write_run(
        tmp_path,
        run_id,
        status="attention_required",
        output=output,
        session_authority="terminal",
        terminal_harvested=True,
        source_thread_id=DEFAULT_EVALUATOR,
    )
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["oracle"]["slug"] = slug
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = module.build_packet(run_dir)
    assert before["signature"] == "post-submit-recursive-self-observation"
    assert before["safe_for_fresh_run"] is False

    receipt_path = run_dir / "settlements" / "recursive-self-observation-fresh-run.json"
    receipt_path.parent.mkdir()
    receipt_path.write_text(json.dumps({
        "schema": module.STATE.RECURSIVE_SELF_OBSERVATION_SETTLEMENT_SCHEMA,
        "confirmation": module.STATE.USER_AUTHORIZED_FRESH_AFTER_RECURSIVE_SELF_OBSERVATION,
        "reason": "user authorized continued progress",
        "run_id": run_id,
        "project_root": state["project_root"],
        "slug": slug,
        "signature": "post-submit-recursive-self-observation",
        "state_sha256": module.STATE.sha256_file(state_path),
        "output_sha256": module.STATE.sha256_file(run_dir / "output.md"),
        "transcript_sha256": module.STATE.sha256_file(run_dir / "transcript.md"),
        "auto_retry": False,
        "submission_action": "none",
        "authorized_at": "2026-08-21T00:00:00Z",
    }), encoding="utf-8")

    after = module.build_packet(run_dir)
    assert after["safe_for_fresh_run"] is True
    assert after["fresh_run_authority"]["sha256"] == module.STATE.sha256_file(receipt_path)


def test_packet_build_requires_the_exact_persisted_run(tmp_path: Path) -> None:
    module = load()
    empty = tmp_path / "no-run"
    empty.mkdir()

    with pytest.raises(module.IncidentError) as exc:
        module.build_packet(empty)
    assert exc.value.code == "INCIDENT_RUN_STATE_MISSING"


def test_build_is_read_only_for_the_reported_run(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(
        tmp_path,
        "9" * 8,
        status="failed",
        stdout="ERROR: --copy-profile requires rsync on PATH\n",
    )
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }

    module.build_packet(run_dir)

    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert after == before


def test_non_project_reporter_role_is_rejected(tmp_path: Path) -> None:
    module = load()
    run_dir = write_run(tmp_path, "8" * 8, status="failed", stdout="ERROR: unknown\n")

    with pytest.raises(module.IncidentError) as exc:
        module.build_packet(run_dir, reporter_role=module.MAINTENANCE_OWNER)
    assert exc.value.code == "INCIDENT_REPORTER_ROLE_INVALID"
