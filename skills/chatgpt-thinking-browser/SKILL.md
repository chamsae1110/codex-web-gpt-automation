---
name: chatgpt-thinking-browser
description: Run new ChatGPT direct, plan, review, edit, and orchestrator work through Oracle plus the manually registered DevSpace workspace app, honoring an explicit host-level regular or Pro default; use legacy agbrowse only to recover an exact persisted old run.
---

# Regular ChatGPT through Oracle + DevSpace

Read `chatgpt-question-designer` first when shaping a new mission.

For new work, create one absolute UTF-8 mission file inside the project and
resolve the requested mode through:

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_dispatch.py" --mode <direct|plan|review|edit|orchestrator> --project-root C:\project --mission-path C:\project\mission.md --manifest-output C:\project\.ai-bridge\oracle.json --dry-run
```

Remove `--dry-run` only for an explicitly authorized live web run. The runtime
sends the configured app mention (default `@codex`) plus the absolute mission path. It never attaches files,
opens ChatGPT settings, inspects/selects/deletes an app, or falls back to
agbrowse, Playwright, in-app Browser, or Chrome.

`orchestrator` is a single web submission that carries the orchestrator
ownership contract: that one GPT session owns delegated exploration, code
authoring, tests, and internal parallel lanes, and its answer is the result.
It has no stages, no stage receipts, and no local gate. Do not confuse it with
comprehensive mode, which is a multi-stage workflow owned by
`chatgpt-pro-plan-handoff` and `bin/chatgpt_oracle_comprehensive.py`.
Comprehensive mode runs `orchestrator`-equivalent work as its implementation
stage, so it contains this mode rather than competing with it.

Choose `orchestrator` when the goal and approach are already settled and one
authorized execution pass should finish the work at the lowest cost. Choose
comprehensive mode when the plan itself needs an independent review stage,
when Pro or Web Multi must participate, or when completion must be proven by a
deterministic local gate.

CodexPro is frozen for new work. Never mention it in a new mission, probe its
endpoint, repair/register/delete its app, or use it as a DevSpace fallback.

Without a host override, Oracle explicitly selects `GPT-5.6 Sol` and
`extra-high`, verifies the visible `Extra High` tier before prompt send, and
records both in Oracle evidence. When the user has explicitly persisted
`regular_web_mode: pro` in `%USERPROFILE%\.codex\chatgpt-workspace.json`, every
new direct, plan, review, edit, orchestrator, comprehensive, and Web Multi
session instead selects `GPT-5.6 Sol` with the visible `Pro` choice. Deep
Research remains its separate research mode. The exact 0.17.1
compatibility layer is hash-gated and fails closed on an unknown version or
third-party file. Never invent xhigh or silently downgrade.

On the current Power-slider UI, Oracle verifies `Power 4 of 5` for regular
`extra-high` and `Power 5 of 5` for the visible `Pro` choice. Both use the
verified `GPT-5.6 Sol` model. `heavy` is only Oracle's internal compatibility
token for Pro, never a claimed UI label.

## Decision and evidence gates

Apply these gates in order. A later gate never repairs a failed earlier gate.

| Observation | Required action | Never do |
| --- | --- | --- |
| The exact project root is absent from current DevSpace `allowedRoots` | Stop before Oracle/browser creation and route to read-only `chatgpt-workspace-setup` diagnosis | Substitute a parent, child, similarly named, active, or shell-visible root |
| The selected model or visible Power value is missing or mismatched before prompt send | Fail closed as pre-submit; preserve the evidence and do not send the prompt | Infer the value, silently downgrade, or switch app/transport |
| Oracle returns nonzero or times out after submission is true or uncertain | Keep project ownership and recover only the recorded exact slug with `live` or `harvest` | Submit the mission again or create a replacement conversation |
| Output is empty, stale, or not proven fresh for this run | Keep the run attention-required and harvest the same slug | Treat a UI completion label, old output, or exit code alone as success |
| A Pro DevSpace run ends with `TASK_OUTCOME: NOT_EXECUTED` | Accept it only as terminal non-execution; a fresh retry is allowed only when the runtime releases the lock and reuses identical mission bytes and SHA-256 | Loop retries, change the mission, manipulate app settings, or attach the mission |

Before reporting success, retain evidence for the exact root, requested mode,
selected model, visible Power value, recorded slug, submission state, and fresh
output path. Regular completion requires exit zero plus fresh nonempty output.
When the resolved transport is Pro DevSpace, successful execution additionally
requires exactly one terminal `TASK_OUTCOME: EXECUTED` marker under the runtime's
v1 footer rules. `NOT_EXECUTED` and `BLOCKED` are terminal evidence, not success.

Keep the high-risk blacklist compact and absolute: no ordinary attachments, no
ChatGPT app/settings automation, no root substitution, no shared manual profile,
no duplicate submission, and no new CodexPro or agbrowse run. Cosmetic wording
changes never justify weakening one of these controls.

Every new run copies the manually signed-in Oracle profile into a throwaway
per-run profile and asks Oracle to hide its owned window. This isolates
different projects: one completed run cannot close another run's live Chrome.
Do not replace this with the shared manual-login profile.

Control state and final Oracle output are host-only below
`%USERPROFILE%\.codex\state\chatgpt-oracle`. Complete requires exit zero and
fresh nonempty host output. Recovery uses the stored slug:

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_run.py" recover --run-dir C:\exact\host-run --action harvest
```

Recovery never restarts/resubmits and never downgrades durable COMPLETE. If the
persisted CDP endpoint died, Oracle may launch a bounded recovery browser from
the run's recorded profile seed and open only that slug's exact persisted
conversation URL for harvest. It must not use a prompt or create a replacement
conversation. Session authority is monotonic: a later `running` observation
cannot downgrade `terminal_observed`. That disagreement remains
attention-required with the same project lock; a later exact terminal harvest
with fresh nonempty output settles it to COMPLETE.

For an already persisted agbrowse run only, use its exact legacy
`chatgpt_agbrowse_run.py --observe-run|--recover-run <run-dir>` command. Do not
create a new agbrowse run.
