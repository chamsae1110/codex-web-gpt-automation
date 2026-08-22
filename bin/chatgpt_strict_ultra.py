from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


CONTRACT_SCHEMA = "codex.chatgpt.strict-ultra-contract/v1"
DEPENDENCY_SCHEMA = "codex.chatgpt.strict-ultra-dependencies/v1"
AUTHORITY_SCHEMA = "codex.chatgpt.strict-ultra-authority/v1"
GOVERNOR_SCHEMA = "codex.chatgpt.research-governor/v1"
GATE_SCHEMA = "codex.chatgpt.strict-local-gate-result/v1"
LEDGER_SCHEMA = "codex.chatgpt.workflow-identity-ledger/v1"
AUDIT_SCHEMA = "codex.chatgpt.strict-ultra-workflow-audit/v1"


class StrictUltraError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise StrictUltraError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise StrictUltraError(f"non-finite JSON number is forbidden: {value}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StrictUltraError(f"strict JSON unavailable: {path}") from exc
    if not isinstance(value, dict):
        raise StrictUltraError(f"JSON object required: {path}")
    return value


def _exact(value: dict[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise StrictUltraError(f"{label} keyset mismatch; missing={missing}; extra={extra}")


def _inside(root: Path, raw: Any, *, exists: bool) -> Path:
    candidate = Path(str(raw or "")).expanduser()
    if not candidate.is_absolute():
        raise StrictUltraError("strict-ultra artifact paths must be absolute")
    if candidate.is_symlink():
        raise StrictUltraError(f"strict-ultra artifact must not be a symlink: {candidate}")
    path = candidate.resolve(strict=exists)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise StrictUltraError(f"strict-ultra artifact outside project: {path}") from exc
    if exists and path.is_symlink():
        raise StrictUltraError(f"strict-ultra artifact must not be a symlink: {path}")
    return path


def _hash(value: Any, label: str) -> str:
    text = str(value or "").casefold()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise StrictUltraError(f"{label} must be SHA-256 hex")
    return text


def _load_bound(root: Path, raw_path: Any, expected: Any, label: str) -> tuple[Path, dict[str, Any]]:
    path = _inside(root, raw_path, exists=True)
    if sha256(path) != _hash(expected, f"{label}_sha256"):
        raise StrictUltraError(f"{label} hash mismatch")
    return path, load_json(path)


def load_contract(root: Path, raw_path: Any, expected_sha256: Any) -> dict[str, Any]:
    path, contract = _load_bound(root, raw_path, expected_sha256, "strict_ultra_contract")
    _exact(contract, {
        "schema", "dependency_manifest_path", "dependency_manifest_sha256",
        "authority_manifest_path", "authority_manifest_sha256",
        "research_governor_path", "research_governor_sha256",
        "identity_ledger_path", "workflow_audit_path", "local_gate_receipt_path",
    }, "strict-ultra contract")
    if contract["schema"] != CONTRACT_SCHEMA:
        raise StrictUltraError(f"strict-ultra contract schema must be {CONTRACT_SCHEMA}")

    dependency_path, dependencies = _load_bound(
        root, contract["dependency_manifest_path"], contract["dependency_manifest_sha256"], "dependency_manifest"
    )
    _exact(dependencies, {"schema", "artifacts"}, "dependency manifest")
    if dependencies["schema"] != DEPENDENCY_SCHEMA or not isinstance(dependencies["artifacts"], list):
        raise StrictUltraError("invalid dependency manifest")
    if not dependencies["artifacts"]:
        raise StrictUltraError("dependency manifest must bind at least one artifact")
    seen_roles: set[str] = set()
    normalized_dependencies: list[dict[str, str]] = []
    for item in dependencies["artifacts"]:
        if not isinstance(item, dict):
            raise StrictUltraError("dependency artifact must be an object")
        _exact(item, {"role", "path", "sha256"}, "dependency artifact")
        role = str(item["role"] or "").strip()
        if not role or role in seen_roles:
            raise StrictUltraError("dependency artifact roles must be nonempty and unique")
        seen_roles.add(role)
        artifact = _inside(root, item["path"], exists=True)
        digest = _hash(item["sha256"], "dependency artifact sha256")
        if sha256(artifact) != digest:
            raise StrictUltraError(f"dependency artifact hash mismatch: {role}")
        normalized_dependencies.append({"role": role, "path": str(artifact), "sha256": digest})

    authority_path, authority = _load_bound(
        root, contract["authority_manifest_path"], contract["authority_manifest_sha256"], "authority_manifest"
    )
    _exact(authority, {
        "schema", "allow_pro", "native_subagents_disabled", "controller",
        "ordinary_web", "pre_workflow_pro", "local_multi_gpt",
    }, "authority manifest")
    if authority["schema"] != AUTHORITY_SCHEMA:
        raise StrictUltraError("invalid authority manifest schema")
    if authority["allow_pro"] is not False or authority["native_subagents_disabled"] is not True:
        raise StrictUltraError("strict-ultra requires allow_pro=false and native_subagents_disabled=true")
    role_keys = {"enabled", "model", "reasoning_effort", "advisory_only", "binding_sha256"}
    for name in ("controller", "ordinary_web", "pre_workflow_pro", "local_multi_gpt"):
        role = authority[name]
        if not isinstance(role, dict):
            raise StrictUltraError(f"authority role must be an object: {name}")
        _exact(role, role_keys, f"authority role {name}")
        if not isinstance(role["enabled"], bool) or not isinstance(role["advisory_only"], bool):
            raise StrictUltraError(f"authority role booleans invalid: {name}")
        if role["enabled"] and (not str(role["model"]).strip() or not str(role["reasoning_effort"]).strip()):
            raise StrictUltraError(f"enabled authority role lacks model/effort: {name}")
        binding = str(role["binding_sha256"] or "")
        if binding:
            _hash(binding, f"{name}.binding_sha256")
    if not authority["ordinary_web"]["enabled"] or authority["ordinary_web"]["advisory_only"]:
        raise StrictUltraError("ordinary_web must be enabled and non-advisory")
    if authority["pre_workflow_pro"]["enabled"] and not authority["pre_workflow_pro"]["advisory_only"]:
        raise StrictUltraError("pre-workflow Pro must remain advisory-only")
    if authority["local_multi_gpt"]["enabled"] and not authority["local_multi_gpt"]["advisory_only"]:
        raise StrictUltraError("Local Multi GPT must remain advisory-only")

    governor_path, governor = _load_bound(
        root, contract["research_governor_path"], contract["research_governor_sha256"], "research_governor"
    )
    _exact(governor, {
        "schema", "advisory_only", "admitted", "settled", "new_measured", "repair",
        "blocked", "unexecuted", "diversity", "opportunity_cost", "recommendation",
    }, "research governor")
    if governor["schema"] != GOVERNOR_SCHEMA or governor["advisory_only"] is not True:
        raise StrictUltraError("Research Governor must be advisory-only")
    for key in ("admitted", "settled", "new_measured", "repair", "blocked", "unexecuted"):
        if type(governor[key]) is not int or governor[key] < 0:
            raise StrictUltraError(f"Research Governor {key} must be a nonnegative integer")
    for key in ("diversity", "opportunity_cost"):
        if type(governor[key]) not in {int, float} or not math.isfinite(governor[key]):
            raise StrictUltraError(f"Research Governor {key} must be finite")

    return {
        "contract_path": path,
        "contract_sha256": sha256(path),
        "dependency_manifest_path": dependency_path,
        "dependency_manifest_sha256": sha256(dependency_path),
        "dependencies": normalized_dependencies,
        "authority_manifest_path": authority_path,
        "authority_manifest_sha256": sha256(authority_path),
        "authority": authority,
        "research_governor_path": governor_path,
        "research_governor_sha256": sha256(governor_path),
        "governor": governor,
        "identity_ledger_path": _inside(root, contract["identity_ledger_path"], exists=False),
        "workflow_audit_path": _inside(root, contract["workflow_audit_path"], exists=False),
        "local_gate_receipt_path": _inside(root, contract["local_gate_receipt_path"], exists=False),
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def sync_identity_ledger(config: dict[str, Any], state: dict[str, Any]) -> None:
    strict = config.get("strict_ultra")
    if not strict:
        return
    path: Path = strict["identity_ledger_path"]
    if path.exists() and path.is_symlink():
        raise StrictUltraError("identity ledger must not be a symlink")
    entries: list[dict[str, Any]] = []
    if path.is_file():
        current = load_json(path)
        _exact(current, {"schema", "workflow_id", "entries"}, "identity ledger")
        if current["schema"] != LEDGER_SCHEMA or current["workflow_id"] != config["workflow_id"]:
            raise StrictUltraError("identity ledger binding mismatch")
        if not isinstance(current["entries"], list):
            raise StrictUltraError("identity ledger entries must be a list")
        entries = current["entries"]
        entry_keys = {
            "sequence", "previous_sha256", "event_sha256", "workflow_id", "stage", "run_id",
            "slug", "conversation", "recovery", "attempt", "status", "entry_sha256",
        }
        previous = "0" * 64
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise StrictUltraError("identity ledger entry must be an object")
            _exact(entry, entry_keys, "identity ledger entry")
            if entry["sequence"] != index or entry["previous_sha256"] != previous:
                raise StrictUltraError("identity ledger sequence or chain mismatch")
            identity_fields = {
                key: entry[key]
                for key in ("workflow_id", "stage", "run_id", "slug", "conversation", "recovery", "attempt", "status")
            }
            event_sha = hashlib.sha256(
                json.dumps(identity_fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if entry["event_sha256"] != event_sha:
                raise StrictUltraError("identity ledger event hash mismatch")
            claimed = entry["entry_sha256"]
            recalculated = hashlib.sha256(
                json.dumps(
                    {key: value for key, value in entry.items() if key != "entry_sha256"},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            if claimed != recalculated:
                raise StrictUltraError("identity ledger entry hash mismatch")
            previous = claimed
    run_state: dict[str, Any] = {}
    run_dir = Path(str(state.get("oracle_run_dir") or ""))
    if run_dir.is_absolute() and (run_dir / "state.json").is_file():
        try:
            run_state = load_json(run_dir / "state.json")
        except StrictUltraError:
            run_state = {}
    oracle = run_state.get("oracle") if isinstance(run_state.get("oracle"), dict) else {}
    identity = {
        "workflow_id": config["workflow_id"],
        "stage": state.get("current_stage") or state.get("next_stage"),
        "run_id": state.get("oracle_run_id") or state.get("current_attempt_id") or run_state.get("run_id"),
        "slug": state.get("oracle_slug") or oracle.get("slug"),
        "conversation": state.get("conversation_url") or oracle.get("conversation_url"),
        "recovery": (state.get("recovery") or {}).get("status") if isinstance(state.get("recovery"), dict) else None,
        "attempt": state.get("current_attempt_id"),
        "status": state.get("status"),
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    event_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if not entries or entries[-1].get("event_sha256") != event_sha:
        previous = entries[-1]["entry_sha256"] if entries else "0" * 64
        entry = {"sequence": len(entries), "previous_sha256": previous, "event_sha256": event_sha, **identity}
        entry["entry_sha256"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        entries.append(entry)
    write_json_atomic(path, {"schema": LEDGER_SCHEMA, "workflow_id": config["workflow_id"], "entries": entries})


def validate_gate_receipt(config: dict[str, Any], stdout: str, bound_path: Path) -> dict[str, Any]:
    try:
        receipt = json.loads(stdout, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except (json.JSONDecodeError, StrictUltraError) as exc:
        raise StrictUltraError("strict local gate must emit one strict JSON receipt") from exc
    if not isinstance(receipt, dict):
        raise StrictUltraError("strict local gate receipt must be an object")
    _exact(receipt, {"schema", "status", "opened_path", "opened_sha256", "validator"}, "local gate receipt")
    expected_sha = sha256(bound_path)
    if (
        receipt["schema"] != GATE_SCHEMA
        or receipt["status"] != "PASS"
        or Path(str(receipt["opened_path"])).resolve() != bound_path.resolve()
        or receipt["opened_sha256"] != expected_sha
        or not str(receipt["validator"] or "").strip()
    ):
        raise StrictUltraError("local gate did not prove it opened the bound artifact")
    return receipt


def write_workflow_audit(config: dict[str, Any], state: dict[str, Any], gate: dict[str, Any]) -> Path:
    strict = config["strict_ultra"]
    ledger = strict["identity_ledger_path"]
    if not ledger.is_file():
        raise StrictUltraError("identity ledger missing at final audit")
    multi_results: list[dict[str, Any]] = []
    for record in state.get("records") or []:
        result = record.get("result") if isinstance(record, dict) else None
        if isinstance(result, dict) and result.get("schema") == "codex.chatgpt.oracle-multi-result/v2":
            multi_results.append({
                "parent_id": result.get("parent_id"),
                "waves": result.get("waves") or [],
                "lanes": result.get("lanes") or [],
                "barrier_status": result.get("barrier_status"),
                "apply_status": result.get("apply_status"),
                "merger": result.get("merger") or {},
            })
    audit = {
        "schema": AUDIT_SCHEMA,
        "workflow_id": config["workflow_id"],
        "manifest_sha256": config["manifest_sha256"],
        "contract_sha256": strict["contract_sha256"],
        "dependency_manifest_sha256": strict["dependency_manifest_sha256"],
        "authority_manifest_sha256": strict["authority_manifest_sha256"],
        "research_governor_sha256": strict["research_governor_sha256"],
        "identity_ledger_sha256": sha256(ledger),
        "model_telemetry": {
            name: strict["authority"][name]
            for name in ("controller", "ordinary_web", "pre_workflow_pro", "local_multi_gpt")
        },
        "research_governor": strict["governor"],
        "multi_runs": multi_results,
        "local_gate": gate,
        "final_verifier": {"status": "PASS", "output_path": state.get("final_output_path")},
    }
    write_json_atomic(strict["workflow_audit_path"], audit)
    return strict["workflow_audit_path"]
