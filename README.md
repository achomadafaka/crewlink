# crewlink

Local mailbox and wake-up bridge between Claude Code and Codex sessions working on the same project.
Standard library plus `websockets`. Nothing leaves the machine.

## Config

One JSON file per crew. `CREWLINK_CONFIG` selects it; default `~/.config/crewlink/crew.json`.

| key | meaning | default |
|---|---|---|
| `claude` | Claude session role names (first = lead, gets queue alarms) | required |
| `gpt` | Codex session role names (first = primary endpoint) | required |
| `command` | installed command name | `crewlink` |
| `state_dir` | mailbox, routes, sockets | `~/.cache/<command>` |
| `service` | systemd user unit the session hook starts | `<command>-bridge.service` |
| `project_root` | hook only injects the inbox for sessions under this path | `~` |
| `header` | text prefixed to the injected inbox | generic |

Examples: `examples/two-agents.json`, `examples/sniper.json`.

## Install

```sh
python3 crewlink/install.py --config ~/.config/crewlink/crew.json   # writes ~/.local/bin/<command>
python3 crewlink/install.py --config ... --rollback                 # previous release
```

The installer never starts services.

## Add a crew to a new project

Each project gets its own command, mailbox and service, so crews never see each other.

1. Write `~/.config/crewlink/<project>.json` (start from `examples/two-agents.json`). Pick a unique `command`, set `project_root`.
2. Install: `python3 crewlink/install.py --config ~/.config/crewlink/<project>.json`
3. Service: copy `examples/bridge.service` to `~/.config/systemd/user/<command>-bridge.service`, replace `<command>`, then
   `systemctl --user daemon-reload && systemctl --user enable --now <command>-bridge.service`
4. Hooks: add one SessionStart entry per client. Each command only acts inside its own `project_root`, so several entries can sit side by side.
   - Claude, `~/.claude/settings.json`: `<command> session-start --client claude`
   - Codex, `~/.codex/hooks.json`: `<command> session-start --client codex`
5. In each Codex session: `<command> register --role <name>`. Claude sessions are matched by session title or name.

## Update after a code change

```sh
python3 -m pytest tests -q
python3 crewlink/install.py --config ~/.config/crewlink/<project>.json
systemctl --user restart <command>-bridge.service
```

## Use

```sh
<command> send --from Lead --to Builder --message-file note.txt
<command> read --to Lead
<command> register --role Builder        # inside a Codex session
<command> health --from Builder --to Lead
```

## Tests

```sh
python3 -m pytest tests -q
```
