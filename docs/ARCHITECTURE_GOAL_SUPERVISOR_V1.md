# Legacy goal-supervisor architecture

This document name is preserved for compatibility. The former
CodexPro/agbrowse goal-supervisor submission path is frozen and cannot start
new work.

New comprehensive work uses the Oracle comprehensive workflow. Regular stages
default to the highest supported non-Pro tier through DevSpace; an optional new
Pro stage requires explicit opt-in and uses read-only DevSpace for design,
advice, or review. A regular `GPT-5.6` `extra-high` stage performs file
mutations and commands. Explicit `pro-attachment` remains a separate read-only
immutable-evidence route. Persisted legacy `pro-devspace` write records retain
their exact original recovery semantics; other
existing persisted legacy state may still be recovered by its exact runner.

See [GLOBAL_CHATGPT_ROUTING.md](GLOBAL_CHATGPT_ROUTING.md).

The exact frozen inventory and its boundary are listed in
[FROZEN_LEGACY.md](FROZEN_LEGACY.md).
