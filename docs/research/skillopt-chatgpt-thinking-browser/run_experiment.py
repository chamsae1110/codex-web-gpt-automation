#!/usr/bin/env python3
"""Run a pinned ChatGPT browser-skill SkillOpt experiment in isolation.

The authoritative source skill is copied below .codex-tmp. Even a staged,
accepted proposal targets only that copy; this runner never adopts and never
writes the repository source or the installed global skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROFILE_FILES = {
    "thinking": (HERE / "config.v1.json", HERE / "tasks.v1.json"),
    "pro": (HERE / "config.pro.v1.json", HERE / "tasks.pro.v1.json"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_head(skillopt_repo: Path, expected: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(skillopt_repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    actual = proc.stdout.strip().casefold()
    if actual != expected.casefold():
        raise SystemExit(
            f"SkillOpt source mismatch: expected {expected}, found {actual}. "
            "Review and repin the selected profile config before running."
        )
    return actual


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skillopt-repo", required=True, type=Path)
    parser.add_argument("--profile", choices=tuple(PROFILE_FILES), default="thinking")
    parser.add_argument("--backend", choices=("mock", "codex"), default="mock")
    parser.add_argument("--model", default="")
    parser.add_argument("--codex-path", default="")
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument(
        "--allow-provider-calls",
        action="store_true",
        help="required for the codex backend; dry-run still spends provider calls",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="stage an accepted proposal inside the isolated work root",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path, tasks_path = PROFILE_FILES[args.profile]
    spec = json.loads(config_path.read_text(encoding="utf-8"))
    if args.backend != "mock" and not args.allow_provider_calls:
        raise SystemExit(
            "Refusing real backend without --allow-provider-calls; SkillOpt dry-run "
            "suppresses mutation, not provider spend."
        )

    skillopt_repo = args.skillopt_repo.expanduser().resolve(strict=True)
    expected_commit = spec["skillopt_commit"]
    actual_commit = pinned_head(skillopt_repo, expected_commit)
    sys.path.insert(0, str(skillopt_repo))

    from skillopt_sleep.config import DEFAULTS, SleepConfig
    from skillopt_sleep.cycle import run_sleep_cycle
    from skillopt_sleep.tasks_file import load_tasks_file

    source_skill = (ROOT / spec["target_skill_path"]).resolve(strict=True)
    tasks, metadata = load_tasks_file(str(tasks_path))
    if metadata.get("reviewed") is not True:
        raise SystemExit("Refusing an unreviewed SkillOpt tasks file")

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    work_root = (
        args.work_root.expanduser().resolve()
        if args.work_root
        else ROOT / ".codex-tmp" / f"skillopt-{args.profile}" / run_id
    )
    if work_root == ROOT or ROOT not in work_root.parents:
        raise SystemExit("work root must be a contained directory below the repository")
    candidate_dir = work_root / "candidate" / source_skill.parent.name
    candidate_dir.mkdir(parents=True, exist_ok=False)
    candidate_skill = candidate_dir / "SKILL.md"
    shutil.copy2(source_skill, candidate_skill)

    settings = dict(spec["settings"])
    settings.update(
        {
            "backend": args.backend,
            "optimizer_backend": args.backend,
            "target_backend": args.backend,
            "model": args.model,
            "optimizer_model": args.model,
            "target_model": args.model,
            "codex_path": args.codex_path,
            "projects": "invoked",
            "invoked_project": str(work_root),
            "target_skill_path": str(candidate_skill),
            "state_dir": str(work_root / "state"),
            "claude_home": str(work_root / "claude"),
            "evidence_log": True,
            "progress": True,
            "auto_adopt": False,
        }
    )
    data = dict(DEFAULTS)
    data.update(settings)
    cfg = SleepConfig(data=data)
    outcome = run_sleep_cycle(cfg, seed_tasks=tasks, dry_run=not args.stage)
    report = outcome.report
    payload = {
        "schema": "codex-web-gpt-automation.skillopt-run.v1",
        "profile": args.profile,
        "skillopt_commit": actual_commit,
        "backend": args.backend,
        "model": args.model,
        "dry_run": not args.stage,
        "work_root": str(work_root),
        "source_skill": str(source_skill),
        "source_skill_sha256": sha256(source_skill),
        "candidate_copy": str(candidate_skill),
        "candidate_copy_sha256": sha256(candidate_skill),
        "n_tasks": report.n_tasks,
        "baseline_score": report.baseline_score,
        "candidate_score": report.candidate_score,
        "gate_no_regression": report.gate_no_regression,
        "gate_action": report.gate_action,
        "accepted": report.accepted,
        "staging_dir": outcome.staging_dir,
        "adopted": outcome.adopted,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if outcome.adopted:
        raise RuntimeError("invariant violated: experiment runner must never adopt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
