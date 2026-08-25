# Optional Local Multi-GPT

Local Multi-GPT is an optional, read-only advisory lane derived from
[`hehee9/multi-gpt`](https://github.com/hehee9/multi-gpt) at commit
`4f5e130fe12f9841eb956c69d8316871c4e955f7`. It runs a Planner, independent
Solvers, Refiners, a Merger/Judge loop, and an Organizer through local
`codex exec` children.

It is intentionally not part of the default install. On the first interactive
install, the installer asks:

```text
Local Multi-GPT도 설치할까요? [y/N]
```

Pressing Enter selects **No**. CI and other non-interactive installs also skip
it unless the opt-in flag is present.

## Install choices

Windows interactive install:

```powershell
.\install.ps1
```

Windows explicit or unattended opt-in:

```powershell
.\install.ps1 -EnableLocalMultiGpt
```

Portable lifecycle:

```bash
python3 install.py --enable-local-multi-gpt
```

The opt-in installs the skill and MCP server together, selects a Codex CLI that
can parse the active `config.toml` **and** accept the exact Luna Max override,
registers the `multi_gpt` stdio MCP, and records the exact CLI path in the MCP
environment. Re-running the setup after a Codex Desktop update safely refreshes
that path only when the existing registration still owns this exact server.
Unrelated registrations remain a conflict. This prevents a removed or older
CLI from silently weakening or breaking the execution contract.

Restart Codex after the first registration. Then verify:

```powershell
python "$env:USERPROFILE\.codex\bin\codex_local_multi_gpt_setup.py" doctor
```

The execution contract is fixed to `gpt-5.6-luna` with reasoning effort
`max`. Before a job is persisted, the MCP runs a no-model-call configuration
canary with those exact values. It fails closed with
`LUNA_MAX_UNSUPPORTED_BY_CODEX_CLI` if the registered CLI cannot accept them,
and every stage still receives the same explicit model and effort arguments.
The MCP refuses other overrides before the canary or child creation. It is
advisory only: it is not release approval or deterministic verification.

## Upstream provenance

To keep a separate pristine upstream checkout for audit or comparison:

```powershell
$source = Join-Path $env:LOCALAPPDATA 'Codex\Sources\multi-gpt'
git clone https://github.com/hehee9/multi-gpt.git $source
git -C $source checkout 4f5e130fe12f9841eb956c69d8316871c4e955f7
```

The runtime installed by this repository includes compatibility hardening and
must remain source-controlled here. Do not overwrite it in place with an
unreviewed upstream file.
