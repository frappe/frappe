# TUI

This file documents the Textual client.

## Start it

```bash
flow tui             # private local daemon and a new TUI session
flow tui -c          # continue the newest session for this directory
flow attach          # connect to the configured long-lived daemon
flow attach --session <id>
```

`flow` starts a private, authenticated Unix-socket daemon and shuts it down when the TUI exits. `flow attach` starts nothing; its daemon and sessions continue after the TUI closes. The private-daemon mode is POSIX-only.

New TUI sessions use the current directory, the saved model preference (or `FLOW_MODEL`), the TUI prompt suffix, and `auto_approve: true`.

## Conversation behavior

The TUI receives SSE with reconnect and durable-sequence deduplication. It renders streaming text, thinking, tool calls, retries, errors, and durable transcript entries. Durable assistant messages replace streamed previews; tool results merge into their matching tool call.

- Enter submits a message. Enter during a run sends steering.
- Alt+Enter queues a message until the current run ends.
- Ctrl+J inserts a newline.
- Up and Down browse prompt history.
- Escape aborts an active run. Ctrl+C aborts a run or quits when idle; Ctrl+D quits.
- Ctrl+T shows or hides thinking. Ctrl+O expands or collapses tool output.
- Ctrl+X then Ctrl+E opens the draft in `$VISUAL` or `$EDITOR`. The editor must block, such as `code -w`.

## Commands

Commands are available as slash commands and through Ctrl+P.

| Command | Purpose |
| --- | --- |
| `/model [name]` | Choose a catalog model or set a supplied model name. |
| `/effort [default|off|minimal|low|medium|high|xhigh|max]` | Set reasoning effort. |
| `/abort` | Abort the active run. |
| `/rewind [seq]` | Rewind the active branch. Without a sequence, it removes the latest user message and puts it back in the composer. |
| `/new` or `/clear` | Start a new session. |
| `/resume [id]` | Switch to another session. |
| `/reload` | Reload server extensions; new tools apply from the next run. |
| `/editor` | Edit the draft externally. |
| `/help` and `/quit` | Show commands or exit. |

Skills from the session catalog also appear in the command palette. Choosing one inserts `/skill:<name>` into the composer.

## Current limits

The server supports attachment uploads, manual compaction, and approval resume, but this TUI does not yet provide controls for them. In particular, an attached session paused for approval must be resumed or cancelled through another HTTP client. Use the web UI or API when image attachments or approval decisions are needed.
