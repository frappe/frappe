# Architecture

Flow is a durable coding-agent service. The daemon, embedded `Agent`, TUI, and web UI all use the same session model.

```text
client or Agent
       │
       ▼
Session ── commits ──► JSONL log ──► Transcript
  │          │              │
  │          └──────────────┴──► SSE subscribers
  ▼
agent loop ──► model ──► tools
```

## Ownership

The agent loop yields events. `Session` is the only writer: it appends durable events, updates the transcript, and publishes events to subscribers. Keep new persistence or client-visible state in that commit path.

The loop owns model calls, tool execution, confirmation pauses, steering, retries, and compaction. It does not write files or manage subscribers. Provider adapters own provider-specific request formats, authentication refresh, and retry behavior.

A sub-agent the `subagent` tool starts is a second loop the session drives inside the same run: its events go through the same commit path, tagged with the child's id, and an approval it pauses for is answered through `resume` while the session stays running.

## Events and state

`flow_harness.events` is the shared wire contract.

- Durable events are append-only JSONL rows with a monotonic `seq`: messages, tool results, approval requests, model changes, compactions, run endings, errors, and rewinds.
- Live-only events are display hints: text/thinking deltas, tool-start notifications, retry progress, compaction progress, and generated titles. While a run is active, `Session` retains its provisional assistant events in memory so a newly attached client can rebuild the preview; the terminal durable assistant message supersedes them.

Every event carries an optional `subagent_id`, the id of the `subagent` call whose child produced it. A transcript folds only the rows of the agent it belongs to; another agent's rows just advance the leaf.

The `Transcript` reducer rebuilds state from the active log branch and updates it incrementally during a run. It holds the provider-facing messages, unresolved tool calls, pending approvals, model selection, and context usage. A session is `running` while its task is alive, `paused` while an approval remains, and otherwise `idle`.

## Branches, repair, and compaction

Every durable entry points to its parent. `rewind` moves the active leaf; later entries form a new branch without deleting the old one. The active-path view is what the model and normal clients see. The all-path view is for history and recovery.

If a process stops after an assistant tool call but before its result, Flow commits error results before accepting newer work. This keeps the provider transcript valid after restart. A run the process stopped in is then ended with a `run_error` and a `run_ended` of reason `error`, so clients stop showing it as running.

Compaction creates a durable summary entry. The original entries remain in the log, but the transcript replaces the compacted portion with a synthetic summary message. Compaction can be requested explicitly or run automatically near the model context limit and after one context-overflow recovery attempt.

## Session creation

`SessionStore` validates the working directory, discovers skills, selects built-in and extension tools, builds the system prompt once, and creates private per-session files for the log, metadata, skills catalog, and attachments.

The prompt is either a verbatim `system_prompt` or a composed prompt containing the active tools, a pointer to Flow's own docs and examples, optional suffix, global and project `AGENTS.md` files, skill index, working directory, and final append text. Prompt text is fixed at session creation; skill instructions are read when a skill is invoked. The catalog is fixed too, except that explicitly invoking a skill added later records it.

## Tools and safety boundaries

Built-in, extension, and client-side tools are combined into one model-facing schema list. The confirmation gate is durable: a gated call emits an approval event and pauses, so any client can resume after reconnect or restart.

`FLOW_ALLOWED_ROOTS` fences session directories and path-taking built-ins. It is not an operating-system sandbox: `bash` still has the daemon process's permissions. Extensions are also trusted Python code and run with those permissions.

## Clients

The HTTP server exposes session operations and SSE. SSE replays durable rows from a cursor, then any retained provisional preview, and finally new live events. Subscriber queues are bounded, so slow clients reconnect instead of growing server memory.

The Textual TUI is a separate client package. Its reducer and stream client use the same events as the server, and it never imports server internals. The Vue web UI is served by the daemon but uses the HTTP API as well.

## Invariants

- Persist a durable event before publishing it to clients.
- One operation at a time per session: input during a run is steering, and a paused run is resumed or cancelled before anything else starts.
- Keep credential secrets, attachment bytes, and provider-specific opaque state out of user-visible fields.

## Code map

| Area | Main modules | Responsibility |
| --- | --- | --- |
| Event contract | `events.py` | Typed durable and live events. |
| Lifecycle | `session/session.py` | Run admission, commit, state, cancellation, rewind, and settlement. |
| Stored state | `session/log.py`, `session/transcript.py`, `session/store.py` | JSONL storage, active-branch reduction, and session files. |
| Prompt and skills | `session/prompt.py`, `session/skills.py` | Prompt composition, skill discovery, and invocation expansion. |
| Sub-agents | `session/subagents.py` | Child agents run inside a session's run. |
| Agent behavior | `agent/loop.py`, `agent/compaction.py` | Model/tool loop, confirmations, steering, and compaction. |
| Embedded API | `agent/agent.py` | The `Agent` facade over one session. |
| Models | `model/` | Provider adapters, credentials, discovery, and reasoning parameters. |
| Tools | `tools/`, `extensions/` | Built-in and bundled tools, schemas, extensions, and client-tool callbacks. |
| HTTP | `server/app.py`, `server/routes/` | Thin API and SSE boundary over sessions; policy, tenants, audit, and the Redis sink sit beside it. |
| Clients | `flow_tui/`, `ui/` | Textual and Vue presentations of the API. |
