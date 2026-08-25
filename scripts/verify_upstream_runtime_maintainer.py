from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any, Sequence


SCHEMA = "codex.web-gpt.upstream-runtime-maintainer-automation/v1"
TASK_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,}$", re.IGNORECASE)


class MaintainerAutomationError(RuntimeError):
    pass


def verify(contract_path: Path, automation_path: Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    automation = tomllib.loads(automation_path.read_text(encoding="utf-8"))
    if contract.get("schema") != SCHEMA:
        raise MaintainerAutomationError("MAINTAINER_CONTRACT_SCHEMA_INVALID")
    for key in ("id", "name", "kind", "status", "rrule", "notification_policy", "prompt"):
        if automation.get(key) != contract.get(key):
            raise MaintainerAutomationError(f"MAINTAINER_AUTOMATION_{key.upper()}_MISMATCH")
    if contract.get("downstream_registration") is not False:
        raise MaintainerAutomationError("MAINTAINER_DOWNSTREAM_REGISTRATION_MUST_BE_FALSE")
    if contract.get("target_thread_policy") != "current-maintainer-task":
        raise MaintainerAutomationError("MAINTAINER_TARGET_THREAD_POLICY_INVALID")
    target = automation.get("target_thread_id")
    if not isinstance(target, str) or not TASK_ID_RE.fullmatch(target):
        raise MaintainerAutomationError("MAINTAINER_TARGET_THREAD_INVALID")
    if automation.get("version") != 1:
        raise MaintainerAutomationError("MAINTAINER_AUTOMATION_VERSION_INVALID")
    return {
        "ok": True,
        "automation_id": automation["id"],
        "target_thread_id": target,
        "rrule": automation["rrule"],
        "downstream_registration": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the host Codex upstream-runtime maintainer heartbeat")
    parser.add_argument("--contract", type=Path, default=Path(__file__).resolve().parents[1] / "upstream-runtime-maintainer-automation.json")
    parser.add_argument("--automation-toml", type=Path, default=Path.home() / ".codex" / "automations" / "validate-upstream-runtime-drift" / "automation.toml")
    args = parser.parse_args(argv)
    try:
        result = verify(args.contract.expanduser().resolve(), args.automation_toml.expanduser().resolve())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, MaintainerAutomationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
