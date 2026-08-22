from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
SPEC = importlib.util.spec_from_file_location(
    "codex_web_gpt_onboarding_test", ROOT / "bin" / "codex_web_gpt_onboarding.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_orders_the_complete_first_install_without_secrets(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    plan = module.onboarding_plan(
        provider="tailscale",
        registration_url="https://host.tailnet.ts.net/mcp",
        roots=[str(project)],
    )
    assert plan["product"] == "Codex Web GPT Automation"
    assert plan["app_name"] == "codex"
    assert [stage["id"] for stage in plan["stages"]] == [
        "01_install",
        "02_stable_endpoint",
        "03_devspace_init",
        "04_reboot_service",
        "05_endpoint_check",
        "06_oracle_login",
        "06b_local_network_access",
        "07_chatgpt_app",
        "08_final_gate",
    ]
    dumped = json.dumps(plan)
    assert "owner_token" not in dumped.casefold()
    assert "--browser-manual-login" in dumped
    assert "DEVSPACE_OAUTH_SCOPES" in dumped


@pytest.mark.parametrize(
    ("provider", "url", "error"),
    [
        ("tailscale", "https://example.com/mcp", "TAILSCALE_STABLE_TS_NET_URL_REQUIRED"),
        ("cloudflare", "https://random.trycloudflare.com/mcp", "CLOUDFLARE_NAMED_TUNNEL_REQUIRED"),
        ("custom", "http://example.com/mcp", "PUBLIC_HTTPS_MCP_URL_REQUIRED"),
        ("custom", "https://example.com/not-mcp", "PUBLIC_MCP_URL_MUST_END_IN_MCP"),
        ("custom", "https://user:secret@example.com/mcp", "PUBLIC_MCP_URL_MUST_NOT_CONTAIN_CREDENTIALS_OR_QUERY"),
    ],
)
def test_unstable_or_unsafe_endpoint_fails_closed(
    tmp_path: Path, provider: str, url: str, error: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(module.OnboardingError, match=error):
        module.onboarding_plan(provider=provider, registration_url=url, roots=[str(project)])


def test_status_requires_exact_root_order_and_bootstrap_match(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    codex_home = tmp_path / ".codex"
    devspace_home = tmp_path / ".devspace"
    (codex_home / "config").mkdir(parents=True)
    devspace_home.mkdir()
    (devspace_home / "config.json").write_text(
        json.dumps({"allowedRoots": [str(project)]}), encoding="utf-8"
    )
    (codex_home / "config" / "codexpro-devspace-bootstrap.json").write_text(
        json.dumps({"roots": [str(project)]}), encoding="utf-8"
    )
    (codex_home / "chatgpt-workspace.json").write_text(
        json.dumps({"app_name": "codex"}), encoding="utf-8"
    )
    healthy = lambda _url: {"ok": True, "status": 401, "expected": 401}
    status = module.readiness_status(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(project)],
        codex_home=codex_home,
        devspace_home=devspace_home,
        http_probe=healthy,
        oracle_profile_dir=tmp_path / "browser-profile",
        local_network_policy_probe=lambda: {"enabled": True},
    )
    assert status["checks"]["exact_roots_configured"] is True
    assert status["checks"]["bootstrap_matches_config"] is True

    child = project / "child"
    child.mkdir()
    mismatch = module.readiness_status(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(child)],
        codex_home=codex_home,
        devspace_home=devspace_home,
        http_probe=healthy,
        oracle_profile_dir=tmp_path / "browser-profile",
        local_network_policy_probe=lambda: {"enabled": True},
    )
    assert mismatch["checks"]["exact_roots_configured"] is False
    assert mismatch["ready"] is False


def test_configure_app_name_is_atomic_and_contains_only_public_name(tmp_path: Path) -> None:
    target = module.configure_app_name(codex_home=tmp_path, app_name="dongju")
    assert json.loads(target.read_text(encoding="utf-8")) == {"app_name": "dongju"}
    assert not list(tmp_path.glob("*.tmp"))


def test_plan_status_and_cli_share_the_same_arbitrary_app_name(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    plan = module.onboarding_plan(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(project)],
        app_name="dongju",
    )
    assert plan["app_name"] == "dongju"
    assert "--app-name dongju" in plan["stages"][-1]["command"]

    codex_home = tmp_path / ".codex"
    devspace_home = tmp_path / ".devspace"
    (codex_home / "config").mkdir(parents=True)
    devspace_home.mkdir()
    (devspace_home / "config.json").write_text(
        json.dumps({"allowedRoots": [str(project)]}), encoding="utf-8"
    )
    (codex_home / "config" / "codexpro-devspace-bootstrap.json").write_text(
        json.dumps({"roots": [str(project)]}), encoding="utf-8"
    )
    module.configure_app_name(codex_home=codex_home, app_name="dongju")
    status = module.readiness_status(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(project)],
        app_name="dongju",
        codex_home=codex_home,
        devspace_home=devspace_home,
        http_probe=lambda _url: {"ok": True, "status": 401},
        oracle_profile_dir=tmp_path / "browser-profile",
        local_network_policy_probe=lambda: {"enabled": True},
    )
    assert status["checks"]["app_name_matches_expected"] is True
    assert status["expected_app_name"] == "dongju"


def test_status_fails_closed_without_persistent_local_network_grant(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    codex_home = tmp_path / ".codex"
    devspace_home = tmp_path / ".devspace"
    profile = tmp_path / "browser-profile"
    (codex_home / "config").mkdir(parents=True)
    devspace_home.mkdir()
    profile.mkdir()
    (profile / "marker").write_text("signed-in", encoding="utf-8")
    (devspace_home / "config.json").write_text(json.dumps({"allowedRoots": [str(project)]}))
    (codex_home / "config" / "codexpro-devspace-bootstrap.json").write_text(
        json.dumps({"roots": [str(project)]})
    )
    (codex_home / "chatgpt-workspace.json").write_text(json.dumps({"app_name": "codex"}))
    status = module.readiness_status(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(project)],
        codex_home=codex_home,
        devspace_home=devspace_home,
        http_probe=lambda _url: {"ok": True, "status": 401},
        oracle_profile_dir=profile,
        local_network_policy_probe=lambda: {"enabled": False},
    )
    assert status["checks"]["oracle_profile_initialized"] is True
    assert status["checks"]["chatgpt_local_network_allowed"] is False
    assert status["ready"] is False


def test_seed_profile_local_network_grant_is_accepted(tmp_path: Path) -> None:
    profile = tmp_path / "browser-profile"
    preferences = profile / "Default" / "Preferences"
    preferences.parent.mkdir(parents=True)
    preferences.write_text(
        json.dumps(
            {
                "profile": {
                    "content_settings": {
                        "exceptions": {
                            "local_network": {
                                "https://chatgpt.com:443,*": {"setting": 1}
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    assert module.browser_profile_local_network_allowed(profile) is True
    assert module.browser_profile_local_network_allowed(tmp_path / "missing") is False


@pytest.mark.parametrize("value", ["", "@dongju", "bad/name", "bad\\name", "bad\nname"])
def test_app_name_validation_fails_closed(value: str) -> None:
    with pytest.raises(module.OnboardingError, match="APP_NAME_INVALID"):
        module.normalize_app_name(value)


def _wizard_environment(tmp_path: Path, *, ready: bool) -> dict[str, object]:
    project = tmp_path / "project"
    project.mkdir()
    codex_home = tmp_path / ".codex"
    devspace_home = tmp_path / ".devspace"
    profile = tmp_path / "browser-profile"
    (codex_home / "config").mkdir(parents=True)
    (codex_home / "receipts").mkdir(parents=True)
    devspace_home.mkdir()
    profile.mkdir()
    (profile / "marker").write_text("signed-in", encoding="utf-8")
    (codex_home / "receipts" / "codexpro-automation-1.json").write_text("{}", encoding="utf-8")
    if ready:
        (devspace_home / "config.json").write_text(
            json.dumps({"allowedRoots": [str(project)]}), encoding="utf-8"
        )
        (codex_home / "config" / "codexpro-devspace-bootstrap.json").write_text(
            json.dumps({"roots": [str(project)]}), encoding="utf-8"
        )
        (codex_home / "chatgpt-workspace.json").write_text(
            json.dumps({"app_name": "codex"}), encoding="utf-8"
        )
    return {
        "project": project,
        "codex_home": codex_home,
        "devspace_home": devspace_home,
        "profile": profile,
        "probes": {
            "http_probe": (lambda _url: {"ok": True, "status": 401}) if ready else (lambda _url: {"ok": False, "status": None}),
            "oracle_profile_dir": profile,
            "local_network_policy_probe": (lambda: {"enabled": bool(ready)}),
        },
    }


def test_start_persists_resumable_state_without_secrets(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    state = module.start_onboarding(
        provider="tailscale",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
        hostname_discovery=lambda: "device.tailnet.ts.net",
    )
    assert state["registration_url"] == "https://device.tailnet.ts.net/mcp"
    assert list(state["stages"]) == list(module.STAGE_IDS)
    persisted = module.state_path(codex_home=environment["codex_home"])
    assert persisted.is_file()
    dumped = persisted.read_text(encoding="utf-8").casefold()
    for banned in ("password", "secret", "token", "cookie"):
        assert banned not in dumped


def test_non_tailscale_start_requires_an_explicit_stable_url(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    with pytest.raises(module.OnboardingError, match="PUBLIC_HTTPS_MCP_URL_REQUIRED"):
        module.start_onboarding(
            provider="custom",
            roots=[str(environment["project"])],
            codex_home=environment["codex_home"],
        )


def test_next_returns_one_stage_and_never_skips_ahead(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert step["done"] is False
    assert step["current_stage"] == "02_stable_endpoint"
    assert step["completion_state"] == "installed"
    assert step["pending_stages"][0] == "02_stable_endpoint"


def test_user_confirmation_alone_cannot_complete_a_stage(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    rejected = module.confirm_stage(
        "07_chatgpt_app",
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert rejected["accepted"] is False
    assert rejected["reason"] == "STAGE_OUT_OF_ORDER_EARLIER_STAGE_PENDING"
    assert rejected["blocking_stage"] in module.STAGE_IDS
    reloaded = module.load_state(codex_home=environment["codex_home"])
    assert reloaded["stages"]["07_chatgpt_app"]["status"] == "pending"


def test_final_gate_requires_recorded_non_pro_exact_root_read(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    before = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert before["current_stage"] == "08_final_gate"
    assert before["completion_state"] == "awaiting_verification"

    module.record_final_gate(
        read_ok=True,
        root=str(environment["project"]),
        evidence="regular oracle listed the exact root",
        listing=["AGENTS.md"],
        codex_home=environment["codex_home"],
    )
    after = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        language="ko",
        **environment["probes"],
    )
    assert after["done"] is True
    assert after["completion_state"] == "verified"
    assert after["completion_label"] == "전체 설치 및 실제 프로젝트 연결 검증 완료"


def test_final_gate_rejects_a_root_outside_the_allowed_list(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(module.OnboardingError, match="FINAL_GATE_ROOT_NOT_IN_ALLOWED_ROOTS"):
        module.record_final_gate(
            read_ok=True,
            root=str(other),
            evidence="wrong root",
            codex_home=environment["codex_home"],
        )


def test_next_before_start_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(module.OnboardingError, match="ONBOARDING_NOT_STARTED"):
        module.next_step(codex_home=tmp_path / ".codex")


def test_chatgpt_stage_exposes_both_ui_paths_and_triage(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    (environment["codex_home"] / "chatgpt-workspace.json").unlink()
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        language="ko",
        **environment["probes"],
    )
    assert step["current_stage"] == "07_chatgpt_app"
    assert step["needs_user_action"] is True
    assert step["confirm_command"] == "onboard.py confirm 07_chatgpt_app"
    assert any("플러그인" in path for path in step["chatgpt_ui_paths"])
    assert any("앱" in path for path in step["chatgpt_ui_paths"])
    assert len(step["missing_create_button_triage"]) == 4


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({"CODEX_ONBOARDING_LANG": "ko"}, "ko"),
        ({"CODEX_ONBOARDING_LANG": "en"}, "en"),
        ({"LANG": "ko_KR.UTF-8"}, "ko"),
        ({"LC_ALL": "en_US.UTF-8"}, "en"),
        ({"LANG": "Korean_Korea.949"}, "ko"),
    ],
)
def test_language_follows_the_environment_locale(environment: dict[str, str], expected: str) -> None:
    assert module.resolve_language(None, environment) == expected


def test_explicit_language_wins_and_unknown_values_fail_closed() -> None:
    assert module.resolve_language("en", {"CODEX_ONBOARDING_LANG": "ko"}) == "en"
    with pytest.raises(module.OnboardingError, match="ONBOARDING_LANGUAGE_UNSUPPORTED"):
        module.resolve_language("fr", {})


@pytest.mark.parametrize("language", ["ko", "en"])
def test_every_stage_has_readable_instructions_in_both_languages(tmp_path: Path, language: str) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    state = module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    for stage_id in module.STAGE_IDS:
        instructions = module.stage_instructions(stage_id, state, language)
        assert instructions
        assert all(line.strip() for line in instructions)
        assert "No instructions found" not in instructions[0]
        assert "찾을 수 없습니다" not in instructions[0]


@pytest.mark.parametrize(("language", "needle"), [("ko", "현재 상태"), ("en", "Current state")])
def test_render_step_is_human_readable_per_language(tmp_path: Path, language: str, needle: str) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        language=language,
        **environment["probes"],
    )
    rendered = module.render_step(step)
    assert needle in rendered
    assert step["current_stage"] in rendered
    assert "{" not in rendered


def test_pending_stages_never_skip_an_unverified_middle_stage(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    start = module.STAGE_IDS.index(step["current_stage"])
    assert step["pending_stages"] == list(module.STAGE_IDS[start:])


@pytest.mark.parametrize("evidence", ["", "too short"])
def test_final_gate_rejects_empty_or_too_short_evidence_without_completion(
    tmp_path: Path, evidence: str
) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )

    with pytest.raises(module.OnboardingError, match="FINAL_GATE_EVIDENCE_INSUFFICIENT"):
        module.record_final_gate(
            read_ok=True,
            root=str(environment["project"]),
            evidence=evidence,
            listing=["README.md"],
            codex_home=environment["codex_home"],
        )

    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert step["done"] is False
    assert step["current_stage"] == "08_final_gate"


def test_final_gate_rejects_empty_or_whitespace_only_listing(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )

    with pytest.raises(module.OnboardingError, match="FINAL_GATE_EVIDENCE_INSUFFICIENT"):
        module.record_final_gate(
            read_ok=True,
            root=str(environment["project"]),
            evidence="The exact project directory was listed.",
            listing=["", "   "],
            codex_home=environment["codex_home"],
        )


def test_valid_final_gate_record_completes_onboarding_and_stores_listing_sample(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )

    recorded = module.record_final_gate(
        read_ok=True,
        root=str(environment["project"]),
        evidence="The exact project directory was listed.",
        listing=["README.md", "bin", "tests"],
        codex_home=environment["codex_home"],
    )
    assert recorded["listing_sample"] == ["README.md", "bin", "tests"]

    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert step["done"] is True
    assert step["completion_state"] == "verified"


def test_final_gate_listing_sample_is_capped_at_ten_entries(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    listing = [f"entry-{index}" for index in range(15)]

    recorded = module.record_final_gate(
        read_ok=True,
        root=str(environment["project"]),
        evidence="The exact project directory was listed.",
        listing=listing,
        codex_home=environment["codex_home"],
    )

    assert recorded["listing_sample"] == listing[:10]


def test_final_gate_rejects_non_regular_non_pro_transport(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )

    with pytest.raises(
        module.OnboardingError, match="FINAL_GATE_TRANSPORT_MUST_BE_REGULAR_NON_PRO_ORACLE"
    ):
        module.record_final_gate(
            read_ok=True,
            root=str(environment["project"]),
            evidence="The exact project directory was listed.",
            listing=["README.md"],
            transport="pro-devspace",
            codex_home=environment["codex_home"],
        )


def test_final_gate_failure_can_be_recorded_without_minimum_evidence(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )

    recorded = module.record_final_gate(
        read_ok=False,
        root=str(environment["project"]),
        evidence="",
        codex_home=environment["codex_home"],
    )
    assert recorded["read_ok"] is False
    assert recorded["listing_sample"] == []

    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert step["done"] is False
    assert step["current_stage"] == "08_final_gate"


def test_confirm_stage_rejects_out_of_order_confirmation(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    (environment["codex_home"] / "chatgpt-workspace.json").write_text(
        json.dumps({"app_name": "codex"}), encoding="utf-8"
    )
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )

    rejected = module.confirm_stage(
        "07_chatgpt_app",
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert rejected["accepted"] is False
    assert rejected["reason"] == "STAGE_OUT_OF_ORDER_EARLIER_STAGE_PENDING"
    assert rejected["blocking_stage"] in module.STAGE_IDS[: module.STAGE_IDS.index("07_chatgpt_app")]
    reloaded = module.load_state(codex_home=environment["codex_home"])
    assert reloaded["stages"]["07_chatgpt_app"]["status"] == "pending"


def test_confirm_stage_in_order_missing_evidence_has_no_blocking_stage(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )

    rejected = module.confirm_stage(
        "02_stable_endpoint",
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    assert rejected["accepted"] is False
    assert rejected["reason"] == "STAGE_CONFIRMATION_NOT_PROVEN_BY_EVIDENCE"
    assert rejected["blocking_stage"] is None


@pytest.mark.parametrize(
    ("mutation", "case"),
    [
        (lambda state: state.pop("provider"), "missing-provider"),
        (lambda state: state.__setitem__("registration_url", "   "), "blank-registration-url"),
        (lambda state: state.pop("allowed_roots"), "missing-allowed-roots"),
        (lambda state: state.__setitem__("allowed_roots", []), "empty-allowed-roots"),
        (lambda state: state["stages"].__setitem__("01_install", "done"), "non-dict-stage"),
    ],
)
def test_load_state_rejects_corrupt_on_disk_state(tmp_path: Path, mutation: object, case: str) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    path = module.state_path(codex_home=environment["codex_home"])
    state = json.loads(path.read_text(encoding="utf-8"))
    mutation(state)
    path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(module.OnboardingError, match="ONBOARDING_STATE_CORRUPT"):
        module.load_state(codex_home=environment["codex_home"])


def test_load_state_backfills_missing_stage_defaults(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    path = module.state_path(codex_home=environment["codex_home"])
    state = json.loads(path.read_text(encoding="utf-8"))
    stage = state["stages"]["01_install"]
    for name in ("status", "verified_at", "evidence"):
        stage.pop(name)
    path.write_text(json.dumps(state), encoding="utf-8")

    module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )
    reloaded = module.load_state(codex_home=environment["codex_home"])
    assert {"status", "verified_at", "evidence"}.issubset(reloaded["stages"]["01_install"])


def _final_gate_record(root: Path, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "read_ok": True,
        "root": str(root),
        "evidence": "The exact project directory was listed.",
        "listing_sample": ["README.md"],
        "recorded_at": "2026-08-22T00:00:00Z",
        "transport": "regular-non-pro-oracle",
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize(
    "tampered_record",
    [
        lambda _environment, _tmp_path: {"read_ok": True},
        lambda environment, _tmp_path: _final_gate_record(environment["project"], listing_sample=[]),
        lambda environment, _tmp_path: _final_gate_record(environment["project"], evidence="too short"),
        lambda environment, _tmp_path: _final_gate_record(environment["project"], transport="pro-devspace"),
        lambda _environment, tmp_path: _final_gate_record(tmp_path / "outside-allowed-roots"),
        lambda environment, _tmp_path: _final_gate_record(environment["project"], recorded_at=""),
        lambda environment, _tmp_path: _final_gate_record(
            environment["project"], listing_sample=[" ", "\t"]
        ),
    ],
)
def test_next_rejects_tampered_final_gate_evidence_on_disk(
    tmp_path: Path, tampered_record: object
) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    state_file = module.state_path(codex_home=environment["codex_home"])
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["stages"]["08_final_gate"]["evidence"] = tampered_record(environment, tmp_path)
    state_file.write_text(json.dumps(state), encoding="utf-8")

    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )

    assert step["done"] is False
    assert step["current_stage"] == "08_final_gate"


def test_honest_recorded_final_gate_still_completes_after_read_time_validation(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    module.record_final_gate(
        read_ok=True,
        root=str(environment["project"]),
        evidence="The exact project directory was listed.",
        listing=["README.md"],
        codex_home=environment["codex_home"],
    )

    step = module.next_step(
        codex_home=environment["codex_home"],
        devspace_home=environment["devspace_home"],
        **environment["probes"],
    )

    assert step["done"] is True
    assert step["completion_state"] == "verified"


def test_final_gate_receipt_distinguishes_honest_and_tampered_evidence(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=True)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    module.record_final_gate(
        read_ok=True,
        root=str(environment["project"]),
        evidence="The exact project directory was listed.",
        listing=["README.md"],
        codex_home=environment["codex_home"],
    )
    honest = module.load_state(codex_home=environment["codex_home"])

    assert module._final_gate_receipt(environment["codex_home"], honest) == honest["stages"]["08_final_gate"]["evidence"]

    honest["stages"]["08_final_gate"]["evidence"] = _final_gate_record(
        environment["project"], listing_sample=[]
    )
    assert module._final_gate_receipt(environment["codex_home"], honest) is None


def test_load_state_reports_wrong_schema_as_corrupt(tmp_path: Path) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=environment["codex_home"],
    )
    state_file = module.state_path(codex_home=environment["codex_home"])
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["schema"] = "wrong-schema"
    state_file.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(module.OnboardingError, match="ONBOARDING_STATE_CORRUPT"):
        module.load_state(codex_home=environment["codex_home"])


def test_load_state_reports_absent_file_as_not_started(tmp_path: Path) -> None:
    with pytest.raises(module.OnboardingError, match="ONBOARDING_NOT_STARTED"):
        module.load_state(codex_home=tmp_path / ".codex")


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--lang", "en", "next"], "en"),
        (["--lang=ko", "next"], "ko"),
        (["next"], None),
        (["--lang", "fr", "next"], None),
    ],
)
def test_global_language_flag_recovers_only_supported_values(
    arguments: list[str], expected: str | None
) -> None:
    assert module._global_language_flag(arguments) == expected


def test_cli_start_existing_state_requires_reset_and_corrupt_state_can_be_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    environment = _wizard_environment(tmp_path, ready=False)
    codex_home = tmp_path / ".codex"
    offline_probe = lambda _url: {"ok": False, "status": None}
    real_next_step = module.next_step
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(module, "probe_http", offline_probe)
    monkeypatch.setattr(
        module,
        "next_step",
        lambda *, language=None: real_next_step(
            codex_home=codex_home,
            devspace_home=environment["devspace_home"],
            http_probe=offline_probe,
            oracle_profile_dir=environment["profile"],
            local_network_policy_probe=lambda: {"enabled": False},
            language=language,
        ),
    )
    start_arguments = [
        "start",
        "--provider",
        "custom",
        "--public-url",
        "https://mcp.example.com/mcp",
        "--root",
        str(environment["project"]),
    ]
    module.start_onboarding(
        provider="custom",
        registration_url="https://mcp.example.com/mcp",
        roots=[str(environment["project"])],
        codex_home=codex_home,
    )

    assert module.main(start_arguments) == 2
    assert "ONBOARDING_ALREADY_STARTED" in capsys.readouterr().out

    state_file = module.state_path(codex_home=codex_home)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state.pop("provider")
    state_file.write_text(json.dumps(state), encoding="utf-8")

    assert module.main(start_arguments) == 2
    assert "ONBOARDING_STATE_CORRUPT" in capsys.readouterr().out

    (codex_home / "receipts" / "codexpro-automation-1.json").unlink()
    assert module.main([*start_arguments, "--reset"]) != 2
    assert "01_install" in capsys.readouterr().out
