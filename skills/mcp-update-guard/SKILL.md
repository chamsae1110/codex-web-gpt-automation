---
name: mcp-update-guard
description: Part of the current Oracle automation path, safely update MCP servers, shared harness helpers, Oracle GPT runners, global skills, plugins, and related automation while preserving local customizations.
---

# MCP update guard

Use this skill for shared/global automation changes. Read the applicable
`AGENTS.md`, identify the authoritative source and installed deployment, and
preserve unrelated local customizations.

## Workflow

1. Classify the exact component and whether the work is an update,
   compatibility repair, policy refresh, or recovery fix.
2. Inspect source Git status and the installed file identity before editing.
   Never overwrite credentials, browser profiles, runtime state, or unrelated
   user changes.
3. For non-trivial GPT automation design or implementation, use the selected
   current GPT workflow only when the user asked for web delegation. Every new
   ChatGPT run uses Oracle:
   - regular modes, Deep Research, comprehensive stages, and Web Multi use
     Oracle plus the manually registered DevSpace app;
    - regular web work defaults to the highest supported non-Pro reasoning tier;
      only explicit user opt-in or a durable explicit Pro preference selects new
      qualified Pro with `GPT-5.6 Sol` at the Pro effort and full-access
      DevSpace. Pro may perform mission-owned file mutations, commands, tests,
      network and browser/CDP verification, and the full agentic coding loop.
      Explicit `pro-attachment` remains a separate read-only
      immutable/external-evidence route and is never an automatic fallback;
      persisted legacy `pro-devspace` write runs retain their exact authority
      only during recovery;
   - CodexPro/agbrowse may be used only for exact recovery of an already
     persisted legacy run and never as a fallback.
4. Prefer small compatibility changes over wholesale replacement. Preserve
   local ports, names, roots, tokens, routing, and hooks unless the task
   explicitly changes them.
5. Batch coherent edits, inspect the final diff once, run focused regression
   tests, then broader tests according to blast radius.
6. Synchronize reusable GPT automation changes to the authoritative
   `codex-web-gpt-automation` source, install the verified bytes, commit with a
   descriptive message, push public-safe changes, and check CI.

## Upstream runtime freshness

Oracle and DevSpace follow the checked-in `upstream-runtime-policy.json`
`newest-validated-stable` contract. Do not keep an older runtime merely because
local patches were originally written for it.

- Treat each official npm `latest` change as an immediate candidate and let the
  read-only scheduled watcher report drift within six hours. The watcher may
  create or update one stable GitHub issue, but it never installs, promotes,
  patches, restarts a service, opens ChatGPT, or changes a project.
- Route that managed issue to the separately scheduled Codex maintainer. It
  owns the validation PR, required cross-platform CI, publication, lifecycle
  install, parity/doctor proof, and one safe-window managed DevSpace restart.
  A routine stable patch/minor has standing approval only after every gate;
  major/breaking, permission/OAuth, patch conflict, failed canary, or ambiguous
  evidence requires explicit user approval. Detection/validation/promotion
  targets are 6/24/48 hours and never weaken a gate.
- The drift issue is a task assignment, not the promotion actor. One
  scheduled Codex maintainer automation owns validation within 24 hours and targets
  promotion within 48 hours when every gate can pass. The owner plus required
  exact-commit CI performs the tests. Stable patch/minor promotion has standing
  approval only after all gates pass; breaking/major, permission/OAuth, patch
  conflict, failed canary, or ambiguous cases require explicit user approval.
- Promote promptly after verifying the published archive integrity and exact
  package tree, rebasing every required local patch with pristine/patched
  hashes, running syntax and focused compatibility checks, proving an Oracle
  no-submission canary and DevSpace health/root/large-read canaries, and passing
  Windows, macOS, and Linux CI on the release commit. A DevSpace canary must prove
  `open_workspace`, a separate mission-file `read` through the same returned
  workspace ID, and a `read_chunk` complete SHA-256 matching the local mission
  bytes; HTTP health, bundled instructions, or workspace-open success alone
  never proves the read route.
- Make the promoted version the explicit default for new work. Retain the prior
  verified version as rollback LKG and exact historical-recovery authority;
  never reinterpret persisted runs or execute a moving unpinned `latest` tag.
- Finalize source and installed bytes before the single required managed
  DevSpace restart. If a foreign live Oracle run could be disrupted, finish the
  GitHub/source gates first and wait for a safe installation window.

## Release completion gate

A version bump is only release metadata preparation. It is never evidence that
GitHub publication completed.

- Treat a change to `package.json`, either root version in
  `package-lock.json`, `install-manifest.json`, or the newest changelog heading
  as release-bearing work.
- Before reporting a release complete, require successful Windows and macOS CI
  for the exact release commit, then create and push the annotated
  `vMAJOR.MINOR.PATCH` tag for that exact commit. The tag-push release workflow
  must finish successfully and create a non-draft GitHub Release.
- Verify all four identities independently: source metadata version, the
  peeled remote tag commit, GitHub Release tag, and GitHub `releases/latest`.
  They must
  name the same version and exact commit. Also verify the lifecycle install
  receipt and source/install byte parity for shipped files.
- If the tag, release workflow, GitHub Release, latest-release pointer, exact CI,
  receipt, or parity cannot be verified, report `release incomplete` with the
  missing gate. Never call a version bump, commit, push, or successful branch CI
  a published release.
- Never move or recreate a published tag. Repair release metadata in place when
  its tag is correct; otherwise publish a new patch version.

## Single repair owner

Automation sources have exactly one repair owner. A project session that hits an
automation defect reports it and stops; it does not edit runners, state, patches,
or their tests. Cross-session patching previously produced duplicate fixes,
conflicting state rules, and repairs aimed at the layer that reported the symptom
instead of the layer that failed.

- Build the handover with
  `python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_incident.py" report --run-dir <exact-run-dir>`.
  The packet carries the exact run directory, the classified bucket, the
  lifecycle verdict with its authority source, and existing evidence paths.
  If comprehensive settlement proves that the planned Oracle layout was never
  created, report from its exact persisted workflow state instead with
  `report --workflow-state <exact-workflow-state.json>`; never fabricate a run
  directory just to satisfy the normal reporter.
  Its v2 routing block must name `evaluated_from_thread`, the exact
  `target_source_thread_id`, run ID, slug, and whether the instruction is
  executable by the evaluating task. Send each target task its own report;
  never broadcast one owner's operational instruction to sibling tasks.
- Re-read exact state immediately before an operational handoff. A terminal,
  harvested run receives `action=none`, including when its local status is
  `attention_required`. A foreign evaluator receives only
  `action=route-to-owner-task` and must not recover, harvest, settle, stop, or
  retry that run.
- Classify before repairing. Run
  `python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_diagnose.py" --summary-only`
  and fix the largest bucket rather than the newest report. Only buckets named
  in `safe_for_fresh_run_buckets` authorize a fresh run. A submit mutex or live
  task owner is `submission-ownership-conflict` and is never retry-safe merely
  because the rejected attempt itself was pre-submit. A post-submit bucket
  requires exact-slug recovery and never a replacement submission.
- Treat `safe_for_fresh_run: false` as binding. Do not resubmit, stop, or close
  another session's work while repairing code.
- Oracle 0.18 persistent attach `ECONNREFUSED` is pre-browser nonexecution only
  when the exact loopback endpoint/profile, process-exited observer, 0.18
  launch transcript, immutable mission/ownership receipt, and complete absence
  of output, conversation URL, browser identity receipt, or prompt-submitted
  evidence all agree. Generic socket failures and recovery disconnects remain
  locked. The owning task must use the hash-bound, append-only
  `settle-prebrowser-attach-nonexecution` command before one fresh run; the
  classifier alone never grants retry authority.
- A terminal DevSpace checkout 502 remains unsafe until the exact terminal
  answer explicitly proves no mission read, command, or file change and the
  user authorizes a new run. Only the same Codex task may write the append-only
  `settle-terminal-devspace-nonexecution` receipt, bound to state, mission,
  output, transcript, stdout, and stderr hashes. Generic BLOCKED output,
  foreign-task adoption, active processes, or live same-task owners remain
  fail-closed. This is explicit new-run authority, never an automatic retry.
- The same receipt may settle an exact app-tools-unavailable terminal answer
  only when it binds the project and configured app, proves that no workspace
  tool was exposed, no alternate connector/shell/web path was attempted, and
  neither the mission nor AGENTS.md was read or modified. Generic tool errors
  and ambiguous nonexecution remain fail-closed. Fresh runs must use the
  persisted registered app name; do not replace it with a recommended default.
- The same receipt may also settle the exact Chat On Steroids Core caller-identity
  preflight refusal only when the terminal answer contains the complete
  `CALLER_IDENTITY_REQUIRED` dormant-worker/browser-extension signature, binds
  the configured Core app and project, and explicitly proves that no local tool,
  project read/change, command, test, alternate app, or fallback path ran. This
  is not a generic identity-error escape hatch: shortened, changed, or ambiguous
  evidence remains unsafe, and only the owning task may append the receipt.
- A separate one-use `settle-terminal-devspace-read-route-refresh` receipt may
  release the first regular qualification canary only after the user manually
  refreshes the configured app tools and the managed post-register procedure is
  ready. The terminal answer must bind the exact app/root/workspace, prove that
  open/read succeeded but `read_chunk` alone was unavailable, and explicitly
  prove that no command or write ran. State, mission, output, transcript,
  stdout, and stderr remain hash-bound. The receipt is same-task, append-only,
  and limited to one fresh probe per task/project; generic BLOCKED answers,
  foreign/live runs, ambiguous command/write evidence, or a repeated exposure
  failure remain fail-closed.

## Safety boundaries

- Do not delete or recreate credential-bearing state during a normal update.
- Do not use resource pressure as authority to block, terminate, downgrade, or
  duplicate user-visible work.
- Do not silently switch Oracle model, reasoning level, transport, or browser
  backend.
- Do not create a new legacy agbrowse/CodexPro run while repairing recovery
  code.
- Stop and report exact dirty files when authoritative persistence, push, or CI
  cannot be completed.

## Report

Report updated components, preserved customizations, focused and broad
verification, installed/source synchronization, commit/push/CI state, rollback
evidence, and any remaining risk. For release-bearing work, separately report
the version, exact commit, remote annotated tag, GitHub Release URL,
`releases/latest` result, release-workflow run, install receipt, and parity.
For any run-specific next action, include `evaluated_from_thread`,
`target_source_thread_id`, exact run ID/slug, and current lifecycle. Omit the
action entirely from reports to non-target tasks; do not reuse identical
operational paragraphs across different task IDs.
