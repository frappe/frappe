# Rebuild notes

This file describes the current boundaries after the rebuild. It is not a future implementation plan. For external behavior, use [api.md](api.md); for the full design, use [architecture.md](architecture.md).

## Core rules

1. The agent loop yields events; `Session` commits them.
2. Durable JSONL events are the source of truth. The transcript is a reducer, not a second database.
3. Provider-specific protocol, authentication refresh, and retries stay in the model layer.
4. HTTP, TUI, and embedded Python are clients of the same session behavior.
5. Tool confirmation is a durable pause, not a client-only dialog.

## Code map

| Area | Main modules | Responsibility |
| --- | --- | --- |
| Event contract | `events.py` | Typed durable and live events. |
| Lifecycle | `session/session.py` | Run admission, commit, state, cancellation, rewind, and settlement. |
| Stored state | `session/log.py`, `session/transcript.py`, `session/store.py` | JSONL storage, active-branch reduction, and session files. |
| Prompt and skills | `session/prompt.py`, `session/skills.py` | Prompt composition, skill discovery, and invocation expansion. |
| Agent behavior | `agent/loop.py`, `agent/compaction.py` | Model/tool loop, confirmations, steering, and compaction. |
| Models | `model/` | Provider adapters, credentials, discovery, and reasoning parameters. |
| Tools | `tools/`, `extensions/` | Built-ins, schemas, extensions, and client-tool callbacks. |
| HTTP | `server/app.py` | Thin API and SSE boundary over sessions. |
| Clients | `flow_tui/`, `ui/` | Textual and Vue presentations of the API. |

## Invariants to preserve

- Persist a durable event before publishing it to clients.
- Use the active log branch when constructing model context.
- Do not start a second operation in a running or paused session unless the session API explicitly supports it. Mid-run user input is steering; a paused run must be resumed or cancelled.
- Close unresolved tool calls with results before accepting a later turn.
- Treat deltas as temporary. A durable assistant message or tool result is the canonical rendered state.
- Never put credential secrets, attachment bytes, or provider-specific opaque state into user-visible fields.

When changing any of these rules, update the reducer, session behavior, API/SSE clients, and tests together.
