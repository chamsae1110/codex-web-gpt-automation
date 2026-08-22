from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "research" / "skillopt-chatgpt-thinking-browser"
TASKS = RESEARCH / "tasks.v1.json"
CONFIG = RESEARCH / "config.v1.json"
RUNNER = RESEARCH / "run_experiment.py"
TARGET = "skills/chatgpt-thinking-browser/SKILL.md"
SUPPORTED_RULE_OPS = {
    "section_present",
    "section_contains",
    "regex",
    "max_chars",
    "min_chars",
    "contains",
    "not_contains",
    "no_refusal",
    "tool_called",
}
OUTCOME_RULE_OPS = {"regex", "contains", "not_contains", "no_refusal", "tool_called"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_skillopt_experiment_is_pinned_and_cannot_auto_adopt() -> None:
    value = load(CONFIG)
    assert value["schema"] == "codex-web-gpt-automation.skillopt-experiment.v1"
    assert re.fullmatch(r"[0-9a-f]{40}", value["skillopt_commit"])
    assert value["target_skill_path"] == TARGET
    settings = value["settings"]
    assert settings["gate_mode"] == "on"
    assert settings["gate_metric"] == "mixed"
    assert settings["gate_no_regression"] is True
    assert settings["edit_budget"] == 2
    assert "no duplicate submission" in settings["preferences"]
    assert settings["evolve_memory"] is False
    assert settings["multi_skill_fanout"] is False
    assert settings["auto_adopt"] is False
    adoption = value["adoption_requirements"]
    assert adoption["strict_validation_improvement"] is True
    assert adoption["zero_validation_regressions"] is True
    assert adoption["zero_test_safety_regressions"] is True
    assert adoption["manual_review"] is True
    assert adoption["installed_skill_direct_write"] is False


def test_experiment_runner_is_isolated_and_provider_calls_are_explicit() -> None:
    value = RUNNER.read_text(encoding="utf-8")
    compile(value, str(RUNNER), "exec")
    assert "pinned_head(skillopt_repo, expected_commit)" in value
    assert "--allow-provider-calls" in value
    assert "dry-run still spends provider calls" in value
    assert '"auto_adopt": False' in value
    assert '"evolve_memory": false' not in value.casefold()
    assert 'ROOT / ".codex-tmp"' in value
    assert "shutil.copy2(source_skill, candidate_skill)" in value
    assert "if outcome.adopted:" in value


def test_reviewed_task_corpus_has_disjoint_fixed_splits() -> None:
    value = load(TASKS)
    assert value["format"] == "skillopt_sleep.tasks.v1"
    assert value["reviewed"] is True
    assert value["target_skill_path"] == TARGET
    tasks = value["tasks"]
    assert len(tasks) == 24
    ids = [task["id"] for task in tasks]
    assert len(ids) == len(set(ids))
    assert Counter(task["split"] for task in tasks) == {
        "train": 12,
        "val": 6,
        "test": 6,
    }
    assert all(task["origin"] == "real" for task in tasks)
    assert all(task["skill_hint"] == "chatgpt-thinking-browser" for task in tasks)
    assert all("provenance:curated" in task["tags"] for task in tasks)


def test_every_task_has_a_working_outcome_judge() -> None:
    tasks = load(TASKS)["tasks"]
    for task in tasks:
        assert task["reference_kind"] == "rule", task["id"]
        checks = task["judge"]["checks"]
        assert checks, task["id"]
        ops = {check["op"] for check in checks}
        assert ops <= SUPPORTED_RULE_OPS, task["id"]
        assert ops & OUTCOME_RULE_OPS, task["id"]
        for check in checks:
            if check["op"] == "regex":
                re.compile(check["arg"])


def test_held_out_tasks_cover_the_high_risk_blacklist() -> None:
    tasks = [task for task in load(TASKS)["tasks"] if task["split"] == "test"]
    joined = "\n".join(
        task["intent"] + "\n" + json.dumps(task["judge"], ensure_ascii=False)
        for task in tasks
    ).casefold()
    for concept in (
        "attachment",
        "settings",
        "substitut",
        "resubmit",
        "per-run profile",
        "codexpro",
    ):
        assert concept in joined


def test_validation_tasks_cover_recovery_and_completion() -> None:
    tasks = [task for task in load(TASKS)["tasks"] if task["split"] == "val"]
    joined = "\n".join(
        task["intent"] + "\n" + json.dumps(task["judge"], ensure_ascii=False)
        for task in tasks
    ).casefold()
    for concept in (
        "attention-required",
        "exact slug",
        "fresh nonempty output",
        "task_outcome: executed",
        "not_executed",
        "sha-256",
    ):
        assert concept in joined
