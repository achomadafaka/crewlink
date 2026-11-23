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

The installer never starts services. Unit file (`~/.config/systemd/user/<command>-bridge.service`):

```ini
[Service]
ExecStart=%h/.local/bin/<command> serve --saved-context
Restart=always
```

Session hooks (Claude `~/.claude/settings.json` SessionStart, Codex `~/.codex/hooks.json`):

```
<command> session-start --client claude
<command> session-start --client codex
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
