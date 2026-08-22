from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_portable_lifecycle_is_exact_inverse(tmp_path: Path) -> None:
    module = load("portable_lifecycle_test", ROOT / "bin" / "codexpro_lifecycle.py")
    codex_home = tmp_path / "codex"
    prior = codex_home / "bin" / "chatgpt_oracle_state.py"
    prior.parent.mkdir(parents=True)
    prior.write_bytes(b"user-owned-before\n")

    plan = module.install(ROOT, codex_home, dry_run=True)
    assert plan["ok"] and "bin/codexpro_harness.py" in plan["files"]
    assert not (codex_home / "receipts").exists()

    installed = module.install(ROOT, codex_home)
    assert installed["ok"] and installed["count"] > 120
    receipt = Path(installed["receipt"])
    assert module.doctor(codex_home)["status"] == "PASS"

    rolled_back = module.rollback(codex_home, receipt)
    assert rolled_back == {"ok": True, "status": "COMPLETE", "receipt": str(receipt), "conflicts": []}
    assert prior.read_bytes() == b"user-owned-before\n"
    assert not (codex_home / "bin" / "codexpro_harness.py").exists()


def test_portable_rollback_preserves_modified_managed_file(tmp_path: Path) -> None:
    module = load("portable_lifecycle_conflict_test", ROOT / "bin" / "codexpro_lifecycle.py")
    codex_home = tmp_path / "codex"
    installed = module.install(ROOT, codex_home)
    managed = codex_home / "bin" / "codexpro_harness.py"
    managed.write_text("user changed\n", encoding="utf-8")

    result = module.rollback(codex_home, Path(installed["receipt"]))

    assert result["ok"] is False
    assert any(item["path"] == "bin/codexpro_harness.py" for item in result["conflicts"])
    assert managed.read_text(encoding="utf-8") == "user changed\n"


def test_portable_receipt_rejects_external_backup(tmp_path: Path) -> None:
    module = load("portable_lifecycle_forgery_test", ROOT / "bin" / "codexpro_lifecycle.py")
    codex_home = tmp_path / "codex"
    receipt = codex_home / "receipts" / "codexpro-automation-forged.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({"schema": module.RECEIPT_SCHEMA, "backup": str(tmp_path / "outside"), "files": []}), encoding="utf-8")

    try:
        module.rollback(codex_home, receipt)
    except module.LifecycleError as exc:
        assert "backup must be owned" in str(exc)
    else:
        raise AssertionError("forged receipt was accepted")


def test_optional_component_prompt_follows_korean_and_english_locale() -> None:
    module = load("portable_lifecycle_locale_test", ROOT / "bin" / "codexpro_lifecycle.py")
    optional = json.loads((ROOT / "install-manifest.json").read_text(encoding="utf-8"))["optional_components"]["local_multi_gpt"]

    assert module.localized_optional_prompt(optional, {"LANG": "ko_KR.UTF-8"}) == optional["prompt_ko"]
    assert module.localized_optional_prompt(optional, {"LANG": "en_US.UTF-8"}) == optional["prompt_en"]
    assert module.localized_optional_prompt(optional, {"CODEX_ONBOARDING_LANG": "ko"}) == optional["prompt_ko"]


def test_optional_component_prompt_uses_system_ui_locale(monkeypatch) -> None:
    module = load("portable_lifecycle_system_locale_test", ROOT / "bin" / "codexpro_lifecycle.py")
    optional = json.loads((ROOT / "install-manifest.json").read_text(encoding="utf-8"))["optional_components"]["local_multi_gpt"]
    for name in ("CODEX_ONBOARDING_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(module.locale_module, "getlocale", lambda: ("ko_KR", "UTF-8"))

    assert module.localized_optional_prompt(optional) == optional["prompt_ko"]

    monkeypatch.setenv("CODEX_ONBOARDING_LANG", "en")
    assert module.localized_optional_prompt(optional) == optional["prompt_en"]
