from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "chatgpt_chrome_local_network_test", ROOT / "bin" / "chatgpt_chrome_local_network.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_exact_origin_is_required() -> None:
    assert module.policy_contains_origin({"1": "https://chatgpt.com"}) is True
    assert module.policy_contains_origin({"1": "https://chatgpt.com/"}) is True
    assert module.policy_contains_origin({"1": "https://evilchatgpt.com"}) is False
    assert module.policy_contains_origin({"1": "*"}) is False


def test_new_entry_preserves_sparse_existing_names() -> None:
    assert module.next_policy_value_name({"1": "https://example.com", "3": "https://other.example"}) == "2"


def test_permission_denial_returns_bounded_manual_fallback(monkeypatch, capsys) -> None:
    def denied(**_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(module, "enable_policy", denied)
    assert module.main(["enable"]) == 2
    output = capsys.readouterr().out
    assert "CHROME_POLICY_WRITE_DENIED" in output
    assert "dedicated Oracle browser profile" in output
