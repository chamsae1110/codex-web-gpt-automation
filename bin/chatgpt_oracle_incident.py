#!/usr/bin/env python
"""Single-owner incident packet contract for Oracle automation repairs.

A project session that hits an automation defect must hand over a bounded
incident packet: the exact run directory, the classified failure bucket, and
the evidence that supports it.  It must not patch automation sources itself.
Cross-session patching is what previously produced duplicate fixes, conflicting
state rules, and repairs aimed at the wrong layer.

This module is read-only with respect to run state: it validates and renders
packets, and never mutates a run, a browser, or a web session.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

BIN = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module unavailable: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


DIAGNOSE = _load("oracle_incident_diagnose", BIN / "chatgpt_oracle_diagnose.py")
STATE = DIAGNOSE.STATE

LEGACY_SCHEMA = "codex.chatgpt.oracle-incident/v1"
SCHEMA = "codex.chatgpt.oracle-incident/v2"
OPERATIONAL_INSTRUCTION_SCHEMA = "codex.chatgpt.oracle-operational-instruction/v1"

# Exactly one role may edit automation sources.
MAINTENANCE_OWNER = "automation-maintenance-session"
REPORTER_ROLE = "project-session"

REQUIRED_FIELDS = (
    "schema",
    "run_dir",
    "bucket",
    "signature",
    "reporter_role",
    "repair_owner",
)

V2_REQUIRED_FIELDS = (
    "run_owner_source_thread_id",
    "evaluated_from_thread",
    "target_source_thread_id",
    "ownership_scope",
    "operational_instruction",
)


class IncidentError(RuntimeError):
    def __init__(self, code: str, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence or {}

    def envelope(self) -> dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": str(self), "evidence": self.evidence}}


def _report_identity(state: dict[str, Any]) -> tuple[str | None, str | None, str]:
    owner = STATE.source_thread_id_from_state(state)
    evaluator = STATE.current_source_thread_id()
    if evaluator is None:
        raise IncidentError(
            "INCIDENT_EVALUATED_FROM_THREAD_REQUIRED",
            "a v2 incident report requires the exact evaluating Codex task ID",
            {"run_id": state.get("run_id"), "owner_source_thread_id": owner},
        )
    if owner is None:
        scope = "legacy-unbound"
    elif evaluator == owner:
        scope = "same-task"
    else:
        scope = "foreign-task"
    return owner, evaluator, scope


def _operational_instruction(
    state: dict[str, Any],
    *,
    lifecycle: str,
    owner: str | None,
    evaluator: str | None,
    scope: str,
) -> dict[str, Any]:
    """Describe who may act without granting cross-task recovery authority."""
    run_id = str(state.get("run_id") or "")
    oracle = state.get("oracle") if isinstance(state.get("oracle"), dict) else {}
    slug = str(oracle.get("slug") or oracle.get("session_locator") or "")
    if lifecycle == "complete":
        action = "none"
        reason = "exact-run-already-terminal"
        executable = False
    elif owner is None:
        action = "none"
        reason = "legacy-run-has-no-task-recovery-authority"
        executable = False
    elif evaluator != owner:
        action = "route-to-owner-task"
        reason = "foreign-task-must-not-operate-on-exact-run"
        executable = False
    else:
        action = "inspect-owned-exact-run"
        reason = "owner-task-must-recheck-current-state-before-any-operation"
        executable = True
    return {
        "schema": OPERATIONAL_INSTRUCTION_SCHEMA,
        "evaluated_from_thread": evaluator,
        "target_source_thread_id": owner,
        "ownership_scope": scope,
        "run_id": run_id,
        "slug": slug,
        "action": action,
        "reason": reason,
        "executable_by_evaluated_thread": executable,
        "fresh_state_check_required": action == "inspect-owned-exact-run",
    }


def build_packet(run_dir: Path, *, reporter_role: str = REPORTER_ROLE) -> dict[str, Any]:
    """Build one incident packet from persisted run evidence only."""
    if reporter_role != REPORTER_ROLE:
        raise IncidentError(
            "INCIDENT_REPORTER_ROLE_INVALID",
            f"an incident packet is reported by {REPORTER_ROLE}",
            {"reporter_role": reporter_role},
        )
    directory = run_dir.expanduser().resolve(strict=True)
    state_path = directory / "state.json"
    if not state_path.is_file():
        raise IncidentError(
            "INCIDENT_RUN_STATE_MISSING",
            "an incident packet requires the exact persisted run state",
            {"run_dir": str(directory)},
        )
    state = STATE.load_state(state_path)
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), dict) else {}
    output_path = Path(str(artifacts.get("output") or (directory / "output.md")))
    verdict = DIAGNOSE.classify_run(
        state,
        stdout_text=DIAGNOSE._read_text(directory / "stdout.log"),
        has_output=DIAGNOSE._output_is_nonempty(output_path),
        transcript_text=DIAGNOSE._read_text(directory / "transcript.md"),
        output_text=DIAGNOSE._read_text(output_path),
        user_confirmed_no_submission=(
            STATE.proven_user_confirmed_no_submission(state_path) is not None
        ),
        pre_submit_host_failure=STATE.proven_pre_submit_host_failure(state_path),
        pre_submit_session_absence=STATE.proven_pre_submit_session_absence(state_path),
    )
    lifecycle = STATE.resolve_lifecycle(
        state, output_is_present=DIAGNOSE._output_is_nonempty(output_path)
    )
    owner_thread, evaluated_from_thread, ownership_scope = _report_identity(state)
    bucket = str(verdict["bucket"])
    project_root = Path(str(state.get("project_root") or "")).expanduser().resolve(strict=True)
    owners = (
        STATE.unresolved_project_sessions(
            directory.parent,
            project_root,
            exclude_run_id=str(state.get("run_id") or ""),
            source_thread_id=owner_thread,
        )
        if owner_thread is not None
        else []
    )
    recursive_authority = STATE.proven_recursive_self_observation_fresh_run_authority(
        state_path
    )
    recursive_fresh_safe = (
        str(verdict["signature"]) == "post-submit-recursive-self-observation"
        and recursive_authority is not None
        and not owners
    )
    return {
        "schema": SCHEMA,
        "run_dir": str(directory),
        "project_root": str(state.get("project_root") or ""),
        "bucket": bucket,
        "signature": str(verdict["signature"]),
        "lifecycle": str(lifecycle["lifecycle"]),
        "authority_source": str(lifecycle["authority_source"]),
        "conversation_url": str((state.get("oracle") or {}).get("conversation_url") or "")
        if isinstance(state.get("oracle"), dict)
        else "",
        "reporter_role": reporter_role,
        "repair_owner": MAINTENANCE_OWNER,
        "reporter_may_edit_automation_sources": False,
        "run_owner_source_thread_id": owner_thread,
        "evaluated_from_thread": evaluated_from_thread,
        "target_source_thread_id": owner_thread,
        "ownership_scope": ownership_scope,
        "operational_instruction": _operational_instruction(
            state,
            lifecycle=str(lifecycle["lifecycle"]),
            owner=owner_thread,
            evaluator=evaluated_from_thread,
            scope=ownership_scope,
        ),
        # Only a proven pre-submit failure is safe to retry: nothing reached the
        # composer, so a fresh run cannot duplicate a live web submission.
        "safe_for_fresh_run": (
            ownership_scope == "same-task"
            and (
                (bucket in {DIAGNOSE.PRE_SUBMIT_HOST, DIAGNOSE.PRE_SUBMIT_UI} and not owners)
                or recursive_fresh_safe
            )
        ),
        "unresolved_owners": owners,
        "fresh_run_authority": recursive_authority,
        "remediation": DIAGNOSE.REMEDIATION.get(bucket, ""),
        "evidence_paths": sorted(
            str(path)
            for path in (
                state_path,
                directory / "stdout.log",
                directory / "stderr.log",
                output_path,
            )
            if path.is_file()
        ),
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Reject a packet that is malformed or claims cross-session repair rights."""
    if not isinstance(packet, dict):
        raise IncidentError("INCIDENT_PACKET_INVALID", "an incident packet must be one JSON object")
    missing = [field for field in REQUIRED_FIELDS if not str(packet.get(field) or "").strip()]
    if missing:
        raise IncidentError(
            "INCIDENT_PACKET_INCOMPLETE",
            "an incident packet requires the exact run, bucket, signature, and ownership fields",
            {"missing": missing},
        )
    if packet.get("schema") not in {LEGACY_SCHEMA, SCHEMA}:
        raise IncidentError(
            "INCIDENT_SCHEMA_INVALID",
            f"incident schema must be {LEGACY_SCHEMA} or {SCHEMA}",
        )
    if packet.get("bucket") not in DIAGNOSE.BUCKETS:
        raise IncidentError(
            "INCIDENT_BUCKET_UNKNOWN",
            "an incident packet must carry a classified bucket from the diagnosis report",
            {"bucket": packet.get("bucket")},
        )
    if packet.get("repair_owner") != MAINTENANCE_OWNER:
        raise IncidentError(
            "INCIDENT_REPAIR_OWNER_INVALID",
            f"automation repairs are owned only by {MAINTENANCE_OWNER}",
            {"repair_owner": packet.get("repair_owner")},
        )
    if packet.get("reporter_may_edit_automation_sources") is not False:
        raise IncidentError(
            "INCIDENT_REPORTER_SCOPE_INVALID",
            "a reporting project session must not edit automation sources",
        )
    if not isinstance(packet.get("evidence_paths"), list) or not packet["evidence_paths"]:
        raise IncidentError(
            "INCIDENT_EVIDENCE_MISSING",
            "an incident packet requires at least one existing evidence path",
        )
    if packet.get("schema") == LEGACY_SCHEMA:
        if "operational_instruction" in packet:
            raise IncidentError(
                "INCIDENT_LEGACY_OPERATION_FORBIDDEN",
                "a legacy v1 incident packet is evidence-only and cannot carry an operational instruction",
            )
        return packet
    if packet.get("schema") == SCHEMA:
        missing_v2 = [field for field in V2_REQUIRED_FIELDS if field not in packet]
        if missing_v2:
            raise IncidentError(
                "INCIDENT_ROUTING_INCOMPLETE",
                "a v2 incident packet requires an explicit evaluation and target task routing contract",
                {"missing": missing_v2},
            )
        owner = packet.get("run_owner_source_thread_id")
        evaluator = packet.get("evaluated_from_thread")
        target = packet.get("target_source_thread_id")
        scope = str(packet.get("ownership_scope") or "")
        instruction = packet.get("operational_instruction")
        if not isinstance(instruction, dict):
            raise IncidentError(
                "INCIDENT_OPERATIONAL_INSTRUCTION_INVALID",
                "the operational instruction must be one object",
            )
        if (
            instruction.get("schema") != OPERATIONAL_INSTRUCTION_SCHEMA
            or target != owner
            or instruction.get("target_source_thread_id") != target
            or instruction.get("evaluated_from_thread") != evaluator
            or instruction.get("ownership_scope") != scope
            or instruction.get("run_id") != Path(str(packet["run_dir"])).name
        ):
            raise IncidentError(
                "INCIDENT_OPERATIONAL_INSTRUCTION_MISMATCH",
                "the operational instruction must remain bound to the exact evaluator, owner task, and run",
            )
        if STATE.SOURCE_THREAD_ID_RE.fullmatch(str(evaluator or "")) is None:
            raise IncidentError(
                "INCIDENT_EVALUATED_FROM_THREAD_INVALID",
                "evaluated_from_thread must be one exact Codex task UUID",
            )
        if owner is not None and STATE.SOURCE_THREAD_ID_RE.fullmatch(str(owner)) is None:
            raise IncidentError(
                "INCIDENT_TARGET_SOURCE_THREAD_INVALID",
                "target_source_thread_id must be one exact owner task UUID or null for a legacy-unbound run",
            )
        if scope not in {"same-task", "foreign-task", "legacy-unbound"}:
            raise IncidentError(
                "INCIDENT_OWNERSHIP_SCOPE_INVALID",
                "ownership_scope must be same-task, foreign-task, or legacy-unbound",
            )
        expected_scope = (
            "legacy-unbound"
            if owner is None
            else "same-task"
            if owner == evaluator
            else "foreign-task"
        )
        if scope != expected_scope:
            raise IncidentError(
                "INCIDENT_OWNERSHIP_SCOPE_INVALID",
                "ownership_scope must be derived exactly from the owner and evaluator task IDs",
                {"expected": expected_scope, "actual": scope},
            )
        lifecycle = str(packet.get("lifecycle") or "")
        if lifecycle == "complete":
            expected_instruction = (
                "none",
                "exact-run-already-terminal",
                False,
                False,
            )
        elif scope == "legacy-unbound":
            expected_instruction = (
                "none",
                "legacy-run-has-no-task-recovery-authority",
                False,
                False,
            )
        elif scope == "foreign-task":
            expected_instruction = (
                "route-to-owner-task",
                "foreign-task-must-not-operate-on-exact-run",
                False,
                False,
            )
        else:
            expected_instruction = (
                "inspect-owned-exact-run",
                "owner-task-must-recheck-current-state-before-any-operation",
                True,
                True,
            )
        actual_instruction = (
            instruction.get("action"),
            instruction.get("reason"),
            instruction.get("executable_by_evaluated_thread"),
            instruction.get("fresh_state_check_required"),
        )
        if actual_instruction != expected_instruction:
            raise IncidentError(
                (
                    "INCIDENT_TERMINAL_OPERATION_FORBIDDEN"
                    if lifecycle == "complete"
                    else "INCIDENT_OPERATIONAL_ACTION_INVALID"
                ),
                "the operational action must match the exact lifecycle and task ownership scope",
                {"expected": expected_instruction, "actual": actual_instruction},
            )
    return packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or validate one Oracle incident packet.")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report")
    report.add_argument("--run-dir", type=Path, required=True)
    check = commands.add_parser("validate")
    check.add_argument("--packet", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "report":
            packet = validate_packet(build_packet(args.run_dir))
        else:
            packet = validate_packet(
                json.loads(args.packet.expanduser().resolve(strict=True).read_text(encoding="utf-8"))
            )
    except IncidentError as error:
        print(json.dumps(error.envelope(), ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"ok": True, "packet": packet}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
