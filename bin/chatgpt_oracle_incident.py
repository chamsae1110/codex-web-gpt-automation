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

SCHEMA = "codex.chatgpt.oracle-incident/v1"
WORKFLOW_STATE_SCHEMA = "codex.chatgpt.oracle-comprehensive-state/v1"
MISSING_LAYOUT_PRE_SUBMIT_SCHEMA = "codex.chatgpt.oracle-missing-layout-pre-submit/v1"

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


class IncidentError(RuntimeError):
    def __init__(self, code: str, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence or {}

    def envelope(self) -> dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": str(self), "evidence": self.evidence}}


def _validate_reporter_role(reporter_role: str) -> None:
    if reporter_role != REPORTER_ROLE:
        raise IncidentError(
            "INCIDENT_REPORTER_ROLE_INVALID",
            f"an incident packet is reported by {REPORTER_ROLE}",
            {"reporter_role": reporter_role},
        )


def build_packet(run_dir: Path, *, reporter_role: str = REPORTER_ROLE) -> dict[str, Any]:
    """Build one incident packet from persisted run evidence only."""
    _validate_reporter_role(reporter_role)
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
        user_confirmed_no_submission=(
            STATE.proven_user_confirmed_no_submission(state_path) is not None
        ),
        pre_submit_host_failure=STATE.proven_pre_submit_host_failure(state_path),
        pre_submit_session_absence=STATE.proven_pre_submit_session_absence(state_path),
    )
    lifecycle = STATE.resolve_lifecycle(
        state, output_is_present=DIAGNOSE._output_is_nonempty(output_path)
    )
    bucket = str(verdict["bucket"])
    project_root = Path(str(state.get("project_root") or "")).expanduser().resolve(strict=True)
    owners = STATE.unresolved_project_sessions(
        directory.parent,
        project_root,
        exclude_run_id=str(state.get("run_id") or ""),
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
        # Only a proven pre-submit failure is safe to retry: nothing reached the
        # composer, so a fresh run cannot duplicate a live web submission.
        "safe_for_fresh_run": (
            bucket in {DIAGNOSE.PRE_SUBMIT_HOST, DIAGNOSE.PRE_SUBMIT_UI} and not owners
        ),
        "unresolved_owners": owners,
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


def build_missing_layout_packet(
    workflow_state_path: Path,
    *,
    reporter_role: str = REPORTER_ROLE,
) -> dict[str, Any]:
    """Build an incident packet for a settled attempt whose layout never existed."""
    _validate_reporter_role(reporter_role)
    path = workflow_state_path.expanduser().resolve(strict=True)
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IncidentError(
            "INCIDENT_WORKFLOW_STATE_INVALID",
            "the comprehensive workflow state is not valid UTF-8 JSON",
            {"workflow_state_path": str(path)},
        ) from exc
    if not isinstance(workflow, dict) or workflow.get("schema") != WORKFLOW_STATE_SCHEMA:
        raise IncidentError(
            "INCIDENT_WORKFLOW_STATE_INVALID",
            f"workflow state schema must be {WORKFLOW_STATE_SCHEMA}",
            {"workflow_state_path": str(path)},
        )
    records = workflow.get("records") if isinstance(workflow.get("records"), list) else []
    settlement = next(
        (
            record
            for record in reversed(records)
            if isinstance(record, dict)
            and record.get("settlement") == "oracle-layout-not-created-pre-submit"
        ),
        None,
    )
    proof = settlement.get("settlement_proof") if isinstance(settlement, dict) else None
    if (
        not isinstance(proof, dict)
        or proof.get("schema") != MISSING_LAYOUT_PRE_SUBMIT_SCHEMA
        or proof.get("kind") != "oracle-layout-not-created"
        or proof.get("safe_for_fresh_run") is not True
        or str(proof.get("workflow_id") or "") != str(workflow.get("workflow_id") or "")
        or str(proof.get("attempt_id") or "") != str(settlement.get("run_id") or "")
        or str(proof.get("run_dir") or "") != str(settlement.get("run_dir") or "")
    ):
        raise IncidentError(
            "INCIDENT_MISSING_LAYOUT_PROOF_INVALID",
            "workflow state lacks an exact missing-layout pre-submit settlement proof",
            {"workflow_state_path": str(path)},
        )
    run_dir = Path(str(proof["run_dir"])).expanduser()
    manifest_path = Path(str(proof.get("oracle_manifest_path") or "")).expanduser()
    if not run_dir.is_absolute() or run_dir.exists() or run_dir.is_symlink():
        raise IncidentError(
            "INCIDENT_MISSING_LAYOUT_PROOF_INVALID",
            "the settled Oracle run directory must remain absent",
            {"run_dir": str(run_dir)},
        )
    try:
        manifest_path = manifest_path.resolve(strict=True)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        project_root = Path(str(manifest.get("project_root") or "")).expanduser().resolve(strict=True)
    except (OSError, UnicodeDecodeError, TypeError, json.JSONDecodeError) as exc:
        raise IncidentError(
            "INCIDENT_MISSING_LAYOUT_BINDING_INVALID",
            "the settled attempt's Oracle manifest binding is unavailable",
            {"oracle_manifest_path": str(manifest_path)},
        ) from exc
    attempt_id = str(proof["attempt_id"])
    if (
        not isinstance(manifest, dict)
        or str(manifest.get("run_id") or "") != attempt_id
        or not project_root.is_dir()
    ):
        raise IncidentError(
            "INCIDENT_MISSING_LAYOUT_BINDING_INVALID",
            "the settled attempt does not match its Oracle manifest",
            {"oracle_manifest_path": str(manifest_path), "attempt_id": attempt_id},
        )
    owners = STATE.unresolved_project_sessions(
        run_dir.resolve().parent,
        project_root,
        exclude_run_id=attempt_id,
    )
    return {
        "schema": SCHEMA,
        "run_dir": str(run_dir.resolve()),
        "project_root": str(project_root),
        "bucket": DIAGNOSE.PRE_SUBMIT_HOST,
        "signature": "oracle-layout-not-created-pre-submit",
        "lifecycle": "pre_submit_settled",
        "authority_source": "workflow-settlement-proof",
        "conversation_url": "",
        "reporter_role": reporter_role,
        "repair_owner": MAINTENANCE_OWNER,
        "reporter_may_edit_automation_sources": False,
        "safe_for_fresh_run": not owners,
        "unresolved_owners": owners,
        "remediation": DIAGNOSE.REMEDIATION.get(DIAGNOSE.PRE_SUBMIT_HOST, ""),
        "evidence_paths": [str(path), str(manifest_path)],
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
    if packet.get("schema") != SCHEMA:
        raise IncidentError("INCIDENT_SCHEMA_INVALID", f"incident schema must be {SCHEMA}")
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
    return packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or validate one Oracle incident packet.")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report")
    source = report.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-dir", type=Path)
    source.add_argument("--workflow-state", type=Path)
    check = commands.add_parser("validate")
    check.add_argument("--packet", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "report":
            packet = validate_packet(
                build_packet(args.run_dir)
                if args.run_dir is not None
                else build_missing_layout_packet(args.workflow_state)
            )
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
