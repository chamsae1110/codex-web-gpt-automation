# SkillOpt experiments for ChatGPT browser skills

This directory is a reviewed, public-safe experiment contract for improving
`skills/chatgpt-thinking-browser/SKILL.md` and
`skills/chatgpt-pro-browser/SKILL.md`. It was derived from Microsoft
SkillOpt `main` at commit `bdfdc30a8e17309c06cdbe8449f01bdecc120203`
on 2026-08-22.

## What this does

- `tasks.v1.json` provides 24 policy-decision scenarios: 12 train, 6
  validation, and 6 held-out adversarial tests.
- `tasks.pro.v1.json` provides 18 standalone-Pro scenarios: 8 train, 5
  validation, and 5 held-out adversarial tests.
- `config.v1.json` pins the source revision and the conservative settings that
  must govern a regular/host-Pro candidate run; `config.pro.v1.json` owns the
  standalone-Pro profile.
- `run_experiment.py` applies those settings without reading or changing the
  user's global SkillOpt configuration. It copies the source skill below
  `.codex-tmp` and can stage only against that isolated copy.
- Repository tests validate the schema, judge checks, split isolation, target
  path, and non-adoption controls without contacting a model provider.

The scenarios test routing and recovery decisions. They do not prove browser,
DevSpace, Oracle, filesystem, or provider behavior. Runtime tests and a fresh
`dev` canary remain mandatory before adoption.

## Safety contract

1. Use the pinned SkillOpt source checkout, not PyPI 0.2.0. The required
   multi-skill and reviewed-adoption safeguards landed after 0.2.0.
2. Run the Windows multiline-prompt regression tests before any Codex-backed
   experiment. Microsoft fixed the `.CMD` newline truncation in PR #205, but a
   local canary still guards the installed Codex path.
3. Treat `dry-run` as mutation control, not spend control. A real backend still
   makes provider calls.
4. Never target `%USERPROFILE%\.codex\skills` directly. Copy the source skill
   to an isolated experiment directory and stage there.
5. Keep `gate_mode=on`, `gate_no_regression=true`, `edit_budget=2`,
   `evolve_memory=false`, and `auto_adopt=false`.
6. Do not let train responses, optimizer notes, or candidate text enter the
   held-out test prompts. The final test measure is read-only.
7. A candidate needs strict validation improvement, zero per-task validation
   regressions, and zero held-out safety regressions before normal repository
   tests and live-runtime verification begin.

## Deterministic preflight

From a pinned SkillOpt source checkout:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pytest -p no:cacheprovider `
  tests/test_gate.py `
  tests/test_gate_no_regression.py `
  tests/test_codex_cli_prompt_stdin.py `
  tests/test_codex_optimizer_backend.py -q
```

Validate this repository's scenario contract:

```powershell
python -m pytest -p no:cacheprovider `
  tests/test_skillopt_chatgpt_thinking_research.py `
  tests/test_global_gpt_browser_policy.py -q
```

Run the provider-free integration check from this repository:

```powershell
python docs/research/skillopt-chatgpt-thinking-browser/run_experiment.py `
  --skillopt-repo "$env:LOCALAPPDATA\Codex\Sources\SkillOpt"

python docs/research/skillopt-chatgpt-thinking-browser/run_experiment.py `
  --profile pro `
  --skillopt-repo "$env:LOCALAPPDATA\Codex\Sources\SkillOpt"
```

The JSON result must report the pinned commit, `backend: mock`,
`gate_no_regression: true`, `adopted: false`, and matching source/candidate
hashes. The mock score is deliberately not a quality claim.

For a separately authorized real experiment, select `--profile thinking` or
`--profile pro`, then add `--backend codex`, an explicitly verified model when
required, and `--allow-provider-calls`. Add `--stage` only when an accepted
proposal should be written into the isolated work root for review. The source
and installed skill are never adoption targets.

An offline SkillOpt plumbing check may use `--backend mock`; it performs no
provider calls and should not be interpreted as a quality score. A real
Codex-backed run is a separately authorized experiment because 24 scenarios,
baseline/candidate gates, reflection, and final held-out scoring can consume
many model calls.

## Adoption gate

An accepted proposal is still only a candidate. Inspect its diff, run focused
tests, `scripts/run_fast_gate.py`, lifecycle dry-run, installation parity, and a
fresh exact-root `dev` canary. Install only verified source bytes through the
repository lifecycle. Commit and publish public-safe changes only after those
gates pass.
