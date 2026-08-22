# Legacy comprehensive workflow v4

The former CodexPro/agbrowse v4 workflow is exact recovery-only. It must not be
used to start a new comprehensive run.

New comprehensive work uses `codex.chatgpt.oracle-comprehensive/v1`. Regular
stages use Oracle plus DevSpace, optional Web Multi uses independent Oracle
sessions, and an optional explicitly authorized new Pro stage uses exact-root
read-only DevSpace for design, advice, or review. Regular `GPT-5.6`
`extra-high` stages own mutations and commands. Explicit `pro-attachment`
remains a separate read-only immutable-evidence route; persisted legacy
`pro-devspace` write records retain their exact recovery semantics. Each web stage authors the next
semantic mission while the host validates immutable hashes and performs the
final deterministic gate.

See [GLOBAL_CHATGPT_ROUTING.md](GLOBAL_CHATGPT_ROUTING.md).

The exact frozen inventory and its boundary are listed in
[FROZEN_LEGACY.md](FROZEN_LEGACY.md).
