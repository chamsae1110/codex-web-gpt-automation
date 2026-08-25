# Versioning and releases

Codex Web GPT Automation follows [Semantic Versioning](https://semver.org/) as
`MAJOR.MINOR.PATCH`.

## What changes the number?

- **MAJOR** — an incompatible public CLI, manifest, schema, state, or lifecycle
  contract change without an automatic compatibility path
- **MINOR** — a backward-compatible mode, platform, installer capability,
  workflow, or substantial user-facing documentation/branding release
- **PATCH** — a backward-compatible defect, compatibility patch, safety
  tightening, or documentation correction

Frozen legacy schema strings and receipt IDs do not change just to match the
product version. Their stability is part of rollback and exact recovery.

## Version sources of truth

One release must use the same version in all of these places:

1. `package.json`
2. root package entry in `package-lock.json`
3. `install-manifest.json`
4. newest entry in `docs/CHANGELOG.md`
5. annotated Git tag `vMAJOR.MINOR.PATCH`
6. GitHub Release title `vMAJOR.MINOR.PATCH`

The source files are authoritative before publication. A tag or GitHub Release
must not be created until the exact commit passes both Windows and macOS CI.

## Release flow

An upstream Oracle or DevSpace stable release is detected by the scheduled
read-only drift workflow. Promotion is a reviewed release change: validate the
candidate, update `upstream-runtime-policy.json`, retain the prior current as
rollback LKG, and complete the normal release/install gates. Never execute the
moving npm `latest` tag directly.

The watcher reports and assigns the candidate; it never mutates a host. A
separate scheduled Codex maintainer automation owns validation, promotion,
publication, installation, and the one safe-window restart. Its required CI is
the independent test authority, and all-gates success is standing approval for
a stable patch/minor promotion. Major or breaking changes, permission/OAuth
changes, patch conflicts, failed canaries, and ambiguous evidence require
explicit user approval. Detection is due in six hours, validation starts within
24 hours, and a clean promotion targets 48 hours; those service levels never
authorize bypassing a gate.

1. Choose the SemVer impact and update the three machine-readable sources.
2. Add a user-oriented changelog entry.
3. Run focused tests, the fast gate, portability, package/link checks, and the
   complete contract suite required by [Release Checklist](RELEASE_CHECKLIST.md).
4. Commit and push public-safe source to `main`.
5. Require successful Windows, macOS, and Linux CI for that commit.
6. Create the annotated tag from the same commit.
7. Let the tag-push publication workflow validate the annotated tag and create
   the non-draft GitHub Release.
8. Verify the peeled remote tag commit, GitHub Release tag,
   `releases/latest`, release workflow, release badge, and downloadable source
   archives independently.
9. On the maintainer host, install the published bytes through the lifecycle
   installer, verify receipt/source parity and both doctors, then restart the
   managed DevSpace service once only if the final install requires it and no
   active or uncertain foreign Oracle run can be disrupted.

Changing the four source version fields completes only release preparation.
Commit, push, or branch CI does not mean a release was published. If any
publication verification is unavailable, report the release as incomplete.

Do not reuse a published version. If release publication fails after a tag is
public, correct the release metadata or publish the next patch; do not move the
tag to different bytes.
