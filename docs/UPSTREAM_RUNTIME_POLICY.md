# Upstream runtime policy

Oracle and DevSpace use a **newest validated stable** policy.

- Official npm `latest` is detected within six hours and becomes a candidate immediately.
- Candidates never auto-install, auto-promote, restart services, open ChatGPT, or touch projects.
- Promotion requires the published archive integrity, exact package tree and patch hashes,
  Node syntax, focused compatibility tests, an Oracle no-submission canary, DevSpace local/public
  health and large-read/root canaries, Windows and macOS CI, review, and a normal release.
- The promoted `current` is the only default for new work. The previous verified version is
  retained as last-known-good (LKG) for rollback and exact historical recovery only.
- Existing Oracle runs always retain their recorded version, command, task ownership, browser
  identity, and conversation. Promotion never rewrites historical authority.

The machine-readable source of truth is [`upstream-runtime-policy.json`](../upstream-runtime-policy.json).
The scheduled GitHub workflow compares it with official npm metadata and maintains one
`Upstream runtime drift` issue. A human-reviewed compatibility release closes that issue.

Current runtime contract:

| Runtime | Current | Rollback LKG |
| --- | --- | --- |
| Oracle | `0.18.0` | `0.17.1` |
| DevSpace | `1.0.7` | `1.0.4` |

This policy intentionally optimizes for fast upstream bug/UI fixes without executing an
unreviewed moving `latest` tag on a user's machine.
