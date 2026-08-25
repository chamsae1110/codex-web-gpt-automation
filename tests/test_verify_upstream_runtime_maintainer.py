from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_upstream_runtime_maintainer.py"
SPEC = importlib.util.spec_from_file_location("verify_upstream_runtime_maintainer", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _contract(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "upstream-runtime-maintainer-automation.json"
    target = tmp_path / "contract.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _automation(tmp_path: Path, contract_path: Path, **changes: object) -> Path:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    values = {
        "version": 1,
        "id": contract["id"],
        "kind": contract["kind"],
        "name": contract["name"],
        "prompt": contract["prompt"],
        "status": contract["status"],
        "rrule": contract["rrule"],
        "notification_policy": contract["notification_policy"],
        "target_thread_id": "019ff05c-bad3-7770-a902-6b1b62588a7d",
    }
    values.update(changes)
    path = tmp_path / "automation.toml"
    lines = []
    for key, value in values.items():
        if isinstance(value, int):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f"{key} = {json.dumps(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_verify_accepts_exact_active_host_heartbeat(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    result = module.verify(contract, _automation(tmp_path, contract))
    assert result["ok"] is True
    assert result["downstream_registration"] is False


@pytest.mark.parametrize("field", ["prompt", "rrule", "status", "notification_policy"])
def test_verify_rejects_contract_drift(tmp_path: Path, field: str) -> None:
    contract = _contract(tmp_path)
    with pytest.raises(module.MaintainerAutomationError, match="MISMATCH"):
        module.verify(contract, _automation(tmp_path, contract, **{field: "changed"}))


def test_verify_rejects_unbound_target_thread(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    with pytest.raises(module.MaintainerAutomationError, match="TARGET_THREAD_INVALID"):
        module.verify(contract, _automation(tmp_path, contract, target_thread_id="latest-project"))
