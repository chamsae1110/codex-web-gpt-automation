# Legacy goal-supervisor architecture

This document name is preserved for compatibility. The former
CodexPro/agbrowse goal-supervisor submission path is frozen and cannot start
new work.

New comprehensive work uses the Oracle comprehensive workflow. Regular stages
default to the highest supported non-Pro tier through DevSpace; an optional new
Pro stage requires explicit opt-in and uses full-access DevSpace for
mission-owned agentic work, including mutations, commands/tests, network, and
browser/CDP verification. Explicit `pro-attachment` remains a separate
read-only immutable-evidence route. Persisted `pro-devspace-readonly` records
retain their exact original recovery semantics; other
existing persisted legacy state may still be recovered by its exact runner.

See [GLOBAL_CHATGPT_ROUTING.md](GLOBAL_CHATGPT_ROUTING.md).

The exact frozen inventory and its boundary are listed in
[FROZEN_LEGACY.md](FROZEN_LEGACY.md).
