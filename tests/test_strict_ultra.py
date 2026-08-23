from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def strict_fixture(tmp_path: Path, *, legacy_alias: bool = False) -> tuple[Path, dict[str, Path]]:
    mission = tmp_path / "mission.md"
    mission.write_text("Plan a bounded change.", encoding="utf-8")
    dependency = tmp_path / "dependency.txt"
    dependency.write_text("bound\n", encoding="utf-8")
    dependencies = write(tmp_path / "dependencies.json", {
        "schema": "codex.chatgpt.strict-ultra-dependencies/v1",
        "artifacts": [{"role": "mission-input", "path": str(dependency), "sha256": digest(dependency)}],
    })
    role = {
        "enabled": True,
        "model": "gpt-5.6",
        "reasoning_effort": "extra-high",
        "advisory_only": False,
        "binding_sha256": "",
    }
    authority = write(tmp_path / "authority.json", {
        "schema": "codex.chatgpt.strict-ultra-authority/v1",
        "allow_pro": False,
        "native_subagents_disabled": True,
        "controller": {**role, "model": "gpt-5.6-sol", "reasoning_effort": "high"},
        "ordinary_web": role,
        "pre_workflow_pro": {**role, "enabled": False, "advisory_only": True},
        "local_multi_gpt": {**role, "enabled": False, "advisory_only": True},
    })
    governor = write(tmp_path / "governor.json", {
        "schema": "codex.chatgpt.research-governor/v1",
        "advisory_only": True,
        "admitted": 2,
        "settled": 1,
        "new_measured": 1,
        "repair": 0,
        "blocked": 0,
        "unexecuted": 1,
        "diversity": 0.75,
        "opportunity_cost": 0.25,
        "recommendation": "continue",
    })
    contract = write(tmp_path / "strict-ultra.json", {
        "schema": "codex.chatgpt.strict-ultra-contract/v1",
        "dependency_manifest_path": str(dependencies),
        "dependency_manifest_sha256": digest(dependencies),
        "authority_manifest_path": str(authority),
        "authority_manifest_sha256": digest(authority),
        "research_governor_path": str(governor),
        "research_governor_sha256": digest(governor),
        "identity_ledger_path": str(tmp_path / "workflow" / "identity-ledger.json"),
        "workflow_audit_path": str(tmp_path / "workflow" / "audit.json"),
        "local_gate_receipt_path": str(tmp_path / "workflow" / "local-gate.json"),
    })
    manifest_value = {
        "schema": "codex.chatgpt.oracle-comprehensive/v1",
        "workflow_id": "a" * 32,
        "project_root": str(tmp_path),
        "workflow_dir": str(tmp_path / "workflow"),
        "initial_mission_path": str(mission),
        "workflow_profile": "strict-ultra" if legacy_alias else "ultra-gpt",
        "initial_stage": "plan",
        "max_stages": 5,
        "allow_pro": False,
        "app_name": "DevSpace",
        "model": "gpt-5.6",
        "local_gate_command": [
            "validator", "--path", "{artifact_path}", "--sha256", "{artifact_sha256}",
        ],
    }
    if legacy_alias:
        manifest_value.update({
            "strict_ultra_contract_path": str(contract),
            "strict_ultra_contract_sha256": digest(contract),
        })
    else:
        manifest_value["closed_audit"] = {
            "contract_path": str(contract),
            "contract_sha256": digest(contract),
        }
    manifest = write(tmp_path / "workflow.json", manifest_value)
    return manifest, {
        "mission": mission, "dependency": dependency, "dependencies": dependencies,
        "authority": authority, "governor": governor, "contract": contract,
    }


def test_ultra_gpt_closed_audit_is_hash_bound_and_dry_runnable(tmp_path: Path) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module("strict_ultra_comprehensive_test", ROOT / "bin" / "chatgpt_oracle_comprehensive.py")
    manifest, _ = strict_fixture(tmp_path)
    config = comprehensive.load_manifest(manifest)
    assert config["workflow_profile"] == "ultra-gpt"
    assert config["workflow_profile_canonical"] == "ultra-gpt"
    assert config["workflow_profile_legacy_alias"] is False
    assert config["closed_audit_enabled"] is True
    assert config["allow_pro"] is False
    assert config["strict_ultra"]["authority"]["native_subagents_disabled"] is True

    def preview(path: Path, *, dry_run: bool):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["model"] == "gpt-5.6"
        return {"ok": True}

    result = comprehensive.run_workflow(manifest, dry_run=True, oracle_execute=preview)
    assert result["ok"] is True
    assert result["workflow_profile"] == "ultra-gpt"
    assert result["closed_audit_enabled"] is True
    assert result["warnings"] == []


def test_legacy_strict_ultra_profile_is_compatibility_alias(tmp_path: Path) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module("strict_ultra_legacy_alias_test", ROOT / "bin" / "chatgpt_oracle_comprehensive.py")
    manifest, _ = strict_fixture(tmp_path, legacy_alias=True)
    config = comprehensive.load_manifest(manifest)
    assert config["workflow_profile"] == "strict-ultra"
    assert config["workflow_profile_canonical"] == "ultra-gpt"
    assert config["workflow_profile_legacy_alias"] is True
    assert config["closed_audit_enabled"] is True

    result = comprehensive.run_workflow(
        manifest,
        dry_run=True,
        oracle_execute=lambda _path, *, dry_run: {"ok": dry_run},
    )
    assert result["ok"] is True
    assert result["workflow_profile_canonical"] == "ultra-gpt"
    assert result["warnings"] == [
        "strict-ultra is a deprecated input alias; use ultra-gpt with closed_audit"
    ]


def test_ordinary_ultra_gpt_does_not_enable_closed_audit(tmp_path: Path) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module("ordinary_ultra_gpt_no_audit_test", ROOT / "bin" / "chatgpt_oracle_comprehensive.py")
    manifest, _ = strict_fixture(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value.pop("closed_audit")
    value["local_gate_command"] = ["validator", "--ordinary"]
    write(manifest, value)
    config = comprehensive.load_manifest(manifest)
    assert config["workflow_profile"] == "ultra-gpt"
    assert config["closed_audit_enabled"] is False
    assert "strict_ultra" not in config


def test_closed_audit_contract_keyset_is_fail_closed(tmp_path: Path) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module("closed_audit_keyset_test", ROOT / "bin" / "chatgpt_oracle_comprehensive.py")
    manifest, _ = strict_fixture(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["closed_audit"] = {"contract_path": value["closed_audit"]["contract_path"]}
    write(manifest, value)
    with pytest.raises(comprehensive.WorkflowError, match="KEYSET_MISMATCH"):
        comprehensive.load_manifest(manifest)

    value["closed_audit"] = None
    write(manifest, value)
    with pytest.raises(comprehensive.WorkflowError, match="must be an object"):
        comprehensive.load_manifest(manifest)


def test_closed_audit_rejects_extra_keys_tamper_duplicates_and_nonfinite(tmp_path: Path) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module("strict_ultra_closed_test", ROOT / "bin" / "chatgpt_oracle_comprehensive.py")
    strict = load_module("strict_ultra_contract_test", ROOT / "bin" / "chatgpt_strict_ultra.py")
    manifest, paths = strict_fixture(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["unknown"] = True
    write(manifest, value)
    with pytest.raises(comprehensive.WorkflowError, match="EXTRA_KEYS"):
        comprehensive.load_manifest(manifest)

    paths["dependency"].write_text("tampered\n", encoding="utf-8")
    with pytest.raises(strict.StrictUltraError, match="artifact hash mismatch"):
        strict.load_contract(tmp_path, paths["contract"], digest(paths["contract"]))

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
    with pytest.raises(strict.StrictUltraError, match="duplicate JSON key"):
        strict.load_json(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(strict.StrictUltraError, match="non-finite"):
        strict.load_json(nonfinite)


def test_identity_ledger_gate_and_closed_workflow_audit(tmp_path: Path) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module("strict_ultra_audit_comprehensive_test", ROOT / "bin" / "chatgpt_oracle_comprehensive.py")
    strict = load_module("strict_ultra_audit_test", ROOT / "bin" / "chatgpt_strict_ultra.py")
    manifest, paths = strict_fixture(tmp_path)
    config = comprehensive.load_manifest(manifest)
    strict.sync_identity_ledger(config, {
        "status": "running", "current_stage": "web-multi", "current_attempt_id": "attempt-1",
    })
    strict.sync_identity_ledger(config, {
        "status": "complete", "current_stage": "final-web-gate", "current_attempt_id": "attempt-2",
    })
    ledger = strict.load_json(config["strict_ultra"]["identity_ledger_path"])
    assert [entry["sequence"] for entry in ledger["entries"]] == [0, 1]
    assert ledger["entries"][1]["previous_sha256"] == ledger["entries"][0]["entry_sha256"]
    tampered = {**ledger, "entries": [dict(item) for item in ledger["entries"]]}
    tampered["entries"][0]["status"] = "forged"
    write(config["strict_ultra"]["identity_ledger_path"], tampered)
    with pytest.raises(strict.StrictUltraError, match="event hash mismatch"):
        strict.sync_identity_ledger(config, {"status": "complete"})
    strict.write_json_atomic(config["strict_ultra"]["identity_ledger_path"], ledger)

    gate_receipt = {
        "schema": "codex.chatgpt.strict-local-gate-result/v1",
        "status": "PASS",
        "opened_path": str(paths["governor"]),
        "opened_sha256": digest(paths["governor"]),
        "validator": "strict-governor-validator/v1",
    }
    validated = strict.validate_gate_receipt(config, json.dumps(gate_receipt), paths["governor"])
    assert validated["status"] == "PASS"
    with pytest.raises(strict.StrictUltraError, match="did not prove"):
        strict.validate_gate_receipt(
            config, json.dumps({**gate_receipt, "opened_sha256": "0" * 64}), paths["governor"]
        )

    state = {
        "records": [{
            "result": {
                "schema": "codex.chatgpt.oracle-multi-result/v2",
                "parent_id": "parent",
                "waves": [{"index": 0, "lane_ids": ["a", "b", "c"]}, {"index": 1, "lane_ids": ["d", "e"]}],
                "lanes": [{"id": name, "ok": True} for name in "abcde"],
                "barrier_status": "all-lanes-terminal",
                "apply_status": "complete",
                "merger": {"ok": True},
            }
        }],
        "final_output_path": str(paths["mission"]),
    }
    audit_path = strict.write_workflow_audit(config, state, gate_receipt)
    audit = strict.load_json(audit_path)
    assert audit["schema"] == "codex.chatgpt.strict-ultra-workflow-audit/v1"
    assert [len(wave["lane_ids"]) for wave in audit["multi_runs"][0]["waves"]] == [3, 2]
    assert audit["model_telemetry"]["ordinary_web"]["model"] == "gpt-5.6"
    assert audit["research_governor"]["advisory_only"] is True


def test_terminal_finalizer_binds_audit_to_final_identity_ledger(tmp_path: Path) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module(
        "strict_ultra_finalizer_comprehensive_test",
        ROOT / "bin" / "chatgpt_oracle_comprehensive.py",
    )
    strict = load_module("strict_ultra_finalizer_test", ROOT / "bin" / "chatgpt_strict_ultra.py")
    manifest, paths = strict_fixture(tmp_path)
    config = comprehensive.load_manifest(manifest)
    config["_review_policy"] = comprehensive._review_policy_from_history(config)
    gate = {
        "schema": "codex.chatgpt.strict-local-gate-result/v1",
        "status": "PASS",
        "opened_path": str(paths["governor"]),
        "opened_sha256": digest(paths["governor"]),
        "validator": "strict-governor-validator/v1",
    }
    state_path = tmp_path / "workflow" / "workflow-state.json"
    result = comprehensive._finalize_complete_workflow(
        state_path,
        config,
        {
            "schema": comprehensive.STATE_SCHEMA,
            "status": "complete",
            "workflow_id": config["workflow_id"],
            "manifest_sha256": config["manifest_sha256"],
            "records": [],
            "final_output_path": str(paths["mission"]),
        },
        gate,
    )

    ledger_path = config["strict_ultra"]["identity_ledger_path"]
    audit_path = config["strict_ultra"]["workflow_audit_path"]
    audit = strict.load_json(audit_path)
    stored = strict.load_json(state_path)
    assert audit["identity_ledger_sha256"] == digest(ledger_path)
    assert result["workflow_audit_sha256"] == digest(audit_path)
    assert stored["workflow_audit_sha256"] == digest(audit_path)
    assert len(strict.load_json(ledger_path)["entries"]) == 1


def test_terminal_finalizer_audit_failure_keeps_recoverable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    os.environ["CODEX_ORACLE_STATE_ROOT"] = str(tmp_path.parent / f"{tmp_path.name}-state")
    comprehensive = load_module(
        "strict_ultra_finalizer_failure_comprehensive_test",
        ROOT / "bin" / "chatgpt_oracle_comprehensive.py",
    )
    strict = load_module("strict_ultra_finalizer_failure_test", ROOT / "bin" / "chatgpt_strict_ultra.py")
    manifest, paths = strict_fixture(tmp_path)
    config = comprehensive.load_manifest(manifest)
    config["_review_policy"] = comprehensive._review_policy_from_history(config)
    state_path = tmp_path / "workflow" / "workflow-state.json"
    prepared = {
        "schema": comprehensive.STATE_SCHEMA,
        "status": "awaiting_receipt",
        "workflow_id": config["workflow_id"],
        "manifest_sha256": config["manifest_sha256"],
        "records": [],
    }
    comprehensive._write_workflow_state(state_path, config, prepared)
    gate = {
        "schema": "codex.chatgpt.strict-local-gate-result/v1",
        "status": "PASS",
        "opened_path": str(paths["governor"]),
        "opened_sha256": digest(paths["governor"]),
        "validator": "strict-governor-validator/v1",
    }
    complete = {
        **prepared,
        "status": "complete",
        "final_output_path": str(paths["mission"]),
    }
    real_writer = comprehensive.STRICT_ULTRA.write_workflow_audit

    def fail_audit(*args, **kwargs):
        raise comprehensive.STRICT_ULTRA.StrictUltraError("simulated audit write failure")

    monkeypatch.setattr(comprehensive.STRICT_ULTRA, "write_workflow_audit", fail_audit)
    with pytest.raises(comprehensive.WorkflowError, match="simulated audit write failure"):
        comprehensive._finalize_complete_workflow(state_path, config, complete, gate)
    assert strict.load_json(state_path)["status"] == "awaiting_receipt"

    monkeypatch.setattr(comprehensive.STRICT_ULTRA, "write_workflow_audit", real_writer)
    result = comprehensive._finalize_complete_workflow(state_path, config, complete, gate)
    ledger_path = config["strict_ultra"]["identity_ledger_path"]
    audit = strict.load_json(config["strict_ultra"]["workflow_audit_path"])
    assert result["status"] == "complete"
    assert strict.load_json(state_path)["status"] == "complete"
    assert audit["identity_ledger_sha256"] == digest(ledger_path)
    assert len(strict.load_json(ledger_path)["entries"]) == 2
