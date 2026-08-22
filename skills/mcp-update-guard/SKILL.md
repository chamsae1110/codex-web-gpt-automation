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
      only explicit user opt-in selects new qualified Pro with `GPT-5.6 Sol` at
      the Pro effort and read-only DevSpace for design, advice, or review. A
      regular `GPT-5.6` `extra-high` DevSpace stage performs file mutations and
      commands. Explicit `pro-attachment` remains a separate read-only
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
- Classify before repairing. Run
  `python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_diagnose.py" --summary-only`
  and fix the largest bucket rather than the newest report. A `pre-submit-*`
  bucket proves no web submission occurred and is safe to retry; a
  `post-submit-*` bucket requires exact-slug recovery and never a replacement
  submission.
- Treat `safe_for_fresh_run: false` as binding. Do not resubmit, stop, or close
  another session's work while repairing code.

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
