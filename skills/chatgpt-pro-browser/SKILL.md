---
name: chatgpt-pro-browser
description: Use for explicitly requested GPT-5.6 Sol Pro work through Oracle, including agentic coding, commands, tests, network and browser/CDP verification, design, advice, review, and bounded follow-up rounds. New qualified Pro uses full-access DevSpace under the mission and project rules.
---

# ChatGPT Pro through Oracle

## Standalone scope

This is the standalone full-access Pro conversation route. It may design,
advise, review, implement, debug, test, inspect live browser state, or complete
another mission-owned task. It owns the complete agentic loop: inspect, plan,
execute, test, inspect the result, adapt, and verify. When implementation is
requested, it does not stop at advice while safe authorized work remains.
After each durable completed answer it returns control to Codex; only an
explicit user request may add another bounded round to that same conversation.
It never invokes `chatgpt-pro-plan-handoff` or Web Multi on its own. If the user
asks for comprehensive mode, use `chatgpt-pro-plan-handoff` instead.

Oracle is the only backend for a new Pro run. There is no new agbrowse,
CodexPro, in-app Browser, custom CDP/Playwright, or `@chrome` fallback.
The GPT-5.6 Pro path excludes agbrowse from creation, dispatch, verification,
and fallback. Keep agbrowse installed only for separate public-web
search/browser QA and exact recovery of an already persisted legacy run.

## Qualified default route

Pro is quota-limited. Invoke this skill only after an explicit user request;
never infer Pro from task difficulty, select it as an automatic upgrade, or use
it as a fallback from regular GPT. Qualified Pro uses Oracle with `GPT-5.6 Sol`
and the explicit `pro` effort token. The latest explicit app selection is
authoritative. `Chat On Steroids Core` keeps the `pro-devspace` transport label
for lifecycle compatibility but attaches to its persistent Prime Chrome at the
configured loopback endpoint/profile, calls Core tools directly, and never asks
for checkout, `open_workspace`, or a workspace id. A DevSpace app selection
retains the ordinary isolated DevSpace route. The mission must bind one
exact absolute project root. After one-time qualification, do not inspect,
register, repair, select, or otherwise verify ChatGPT app/settings state on
each run.

Before the first DevSpace-app Pro submission for a new project, the local runner
must verify that the normalized exact root is equal to or contained by one
DevSpace `allowedRoots` boundary. A deliberately approved parent therefore
covers all of its descendant projects, while a child, a similarly named
sibling, or a path on another drive does not. The web worker must still open
the mission's exact project root; the parent is only a permission boundary and
is never a workspace substitute. The result is cached by exact config hash, so
later questions in the same project do not repeat endpoint/read probes; a
changed config is revalidated. Failure returns
`DEVSPACE_EXACT_ROOT_UNAVAILABLE` before Oracle or a browser is created and
points to the complete root-preserving setup preview.

Pro reads the mission and applicable `AGENTS.md` chain completely. DevSpace uses the
maximum DevSpace capabilities available for that mission; Chat On Steroids Core
uses its directly exposed Core tools at the same exact root: project-file reads
and mutations, shell commands and tests, network access, and browser or Chrome
DevTools/CDP verification. Project-file mutations stay inside the exact root
unless the mission or applicable project rules explicitly authorize a named
outside target. Repository safety rules and explicit approval boundaries for
destructive, credential, account, deployment, publication, purchase, or other
external-state actions remain authoritative. Pro may
not substitute a parent, child, similarly named, active, or shell-boundary
workspace, and may retry only the same root once after a timeout.
Repository safety rules remain authoritative.

The user's explicit request to run Pro is standing authorization for the
ordinary mechanics of that exact mission: launch or attach to the managed
browser, submit the bound prompt, select the configured DevSpace app, approve
the exact named-app use modal with "Remember in this conversation", and perform
mission-owned file, command, test, network, browser, and CDP actions. The runner
records that conversation-scoped approval and must not ask the user again for
those routine actions. This standing authorization does not cover credentials,
account or app-setting changes, destructive cleanup, deployment, publication,
purchases, or another irreversible external action unless the mission
explicitly authorizes it.

For a user-owned loopback Chrome CDP endpoint, use the installed
`.codex/bin/chatgpt_chrome_cdp.mjs` helper when project-native tooling is not
more appropriate. It supports target/version listing, DOM or JavaScript
evaluation, and arbitrary browser- or page-level CDP method calls. Browser
navigation, input, downloads, or state mutation still require the mission and
applicable project rules to authorize them.

## Explicit attachment evidence route

`pro-attachment` remains an explicit, read-only route for immutable/external
evidence or artifacts that DevSpace cannot read. It is never an automatic
fallback from a DevSpace failure. Build only the declared packet, bind every
attachment path and SHA-256, and never infer attachments from prose.

## Preflight and completion

1. Resolve and hash-validate the tested Oracle compatibility contract.
2. Bind the same task-scoped normalized-project mutex used by regular Oracle work.
3. Build a short UTF-8 mission that states the exact root, objective, full
   mission-owned action authority, acceptance checks, and any evidence or
   irreversible-action limitations.
4. Use a fresh Oracle slug and require Oracle model and transport evidence
   before accepting a send.

For an ordinary explicit Pro request, call the live dispatcher directly. It
performs root, manifest, mutex, Oracle-version, and compatibility validation
before creating a browser or submitting a prompt:

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_dispatch.py" --mode pro --project-root <ROOT> --mission-path <MISSION> --manifest-output <MANIFEST>
```

Add `--dry-run` only when previewing a newly changed automation/configuration,
debugging a manifest, or when the user explicitly asks for a preview. Do not
run a routine preview immediately before the same live dispatch. New `pro`
work uses the full-access route selected by the explicit app. For Chat On
Steroids Core, absent, mismatched, or non-loopback persistent browser
configuration fails before submission; it must not fall back to a copied
profile or DevSpace prompt. Attachment work uses only the separate explicit
evidence contract.

## Same-conversation follow-up

When the user explicitly wants continued discussion, do not create a new Pro
conversation and do not loosen the raw Oracle argument allowlist. The exact
parent must be owned by the current Codex task, terminal `EXECUTED`, bound to
`pro-devspace` or a persisted `pro-devspace-readonly` parent, and retain valid
ownership/browser receipts plus the canonical conversation URL. Put the next
mission-owned question or execution step in a UTF-8 mission
inside the same project, then preview the internal lifecycle:

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_run.py" followup --parent-run-dir <TERMINAL_PARENT_RUN_DIR> --mission-path <FOLLOWUP_MISSION> --round-key <UNIQUE_ROUND_KEY> --dry-run
```

The explicit user request for that follow-up is its live send authority. After
the internal validation preview succeeds, remove only `--dry-run` and do not
ask for another routine permission. The
child gets a new Oracle run/slug and dynamic CDP port but must reopen the exact
same ChatGPT conversation. Append-only reservation and result receipts bind
the round mission, child state, output/transcript hashes, task owner, and
conversation identity. Foreign/legacy ownership, a duplicate key, attachment
or writable transport, artifact tamper, missing receipt, or a changed/unproven
conversation fails closed. Never inject raw `--followup`,
`--browser-follow-up`, or `session`; recovery observes only and cannot send a
round; uncertainty never authorizes a replacement prompt.
New DevSpace Pro parents normalize default `archive=auto` to `never`; no user
archive-setting action is required. Explicit `archive=always` is a single-turn
choice. Only historical or explicitly archived parents use the bounded exact
restore-and-rearchive compatibility path.
If restoration fails before the composer, do not harvest. Preserve the exact
child, obtain explicit user no-submission confirmation, and use the runner's
exact `settle-no-submission` path. An older exact no-live/no-URL/no-candidate
harvest pair may be revalidated, but must never be deleted or rewritten.

Completion requires the requested Pro model/effort evidence, exit zero, fresh
nonempty host-only `output.md`, immutable run identity, and a refreshed
transcript. The final nonempty line must also be
`TASK_OUTCOME: EXECUTED|NOT_EXECUTED|BLOCKED`; every citation, footnote, and
Markdown reference definition belongs before it. For bounded compatibility
with provider-rendered answers, the classifier also accepts exactly one marker
followed solely by single-line HTTP(S) Markdown reference definitions. Ordinary
trailing prose or another marker remains `unknown`. A terminal answer that reports
zero callable DevSpace tools or says the mission/root could not be read is
`NOT_EXECUTED`, never successful Pro work. When that exact terminal run is
durably captured, it releases the current task's project ownership and permits at most one
fresh retry with the same mission bytes and SHA-256. If the retry has the same
tool-exposure failure, stop with `attention_required`; do not loop, manipulate
ChatGPT app settings, or switch to attachments automatically. A nonzero exit
after submission is `attention_required`, not proof that the web session
failed.

## Recovery

Recover only the stored exact Oracle run directory and slug. `live` and
`harvest` may observe or collect that same session; they never restart,
resubmit, change route/model/effort, or create a replacement conversation.

When the exact recorded Oracle runtime reports the prompt-not-observed timeout, first run
exact-slug harvest. No live tab plus no recoverable conversation URL remains
submission-uncertain and needs explicit user confirmation before the
hash-bound `settle-no-submission` path can release a standalone qualified-Pro
run. Only then may an explicitly authorized single retry reuse the identical
mission bytes; no output, URL, mismatched hash, conflicting recovery state, or
ordinary trailing browser error may be treated as proof.

If the task-bound failure occurred before a conversation-bound browser receipt
could be sealed, preview the same exact slug with `recover --action harvest
--dry-run`. The preview may use `bounded-prompt-timeout-harvest` only when the
ownership receipt, qualified-Pro profile, the exact recorded Oracle version's zero-turn commit probe,
root composer, dynamic CDP port, isolated profile/target, and absent output/URL
all match. Remove only `--dry-run` for that one prompt-free harvest. `live`, a
foreign task, or any contradictory identity stays blocked. The harvest still
does not unlock the project; the explicit user confirmation command remains
mandatory. A later project-mission edit is acceptable only when the immutable
run copy and task ownership receipt bind the same original mission SHA-256;
legacy-unbound runs do not receive this compatibility path.

The same user-confirmed, fail-closed settlement is available to a
`pro-attachment` run only when the exact recorded Oracle runtime reports the attachment-upload
timeout before prompt submission. It binds every attachment path, size, and
SHA-256; the source and transport mission copies; Oracle locator/version; exact
stdout/transcript and recovery bytes; and the absence of output and a
conversation URL. The user confirmation token is still mandatory. Any changed
attachment, live recovery state, URL, output, or unrecognized error keeps the
current task's project lock. This recovery rule never authorizes an automatic replacement attachment run.

For an already persisted agbrowse Pro run only, former recovery commands remain
available. They must never create a new run.
