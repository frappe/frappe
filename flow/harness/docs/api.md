# API

Flow runs durable agent sessions. Use `Agent` when Python owns the process, or the HTTP API when a client connects to the daemon. Both use the same session log and event types.

## Python

```python
from flow.agent import Agent

agent = Agent(model="mock", cwd=".")

async for event in agent.run("Summarize this project"):
    if event.type == "text_delta":
        print(event.text, end="", flush=True)
```

`Agent(config=None, *, data_dir="~/.flow/server", **overrides)` creates one session. `model` may be a model name or an injected `Model` instance.

| Method | Use |
| --- | --- |
| `run(message, before_tool_call=..., after_tool_call=...)` | Start a turn and yield events until it ends or pauses. |
| `resume(answers, approval_seq=..., ...)` | Continue a paused approval batch. |
| `compact(instructions=None)` | Replace older context with a durable summary. |
| `abort()` | Ask the active run to stop; returns whether one was active. |
| `await rewind(target_seq)` | Move the active conversation branch back to an earlier entry. |
| `await set_model(model, credential_id=None)` | Choose the model for later turns. Not available with an injected model. |

`Agent.session` exposes the lower-level `Session` API. `run` and `resume` hooks are local Python callbacks; they are not part of the HTTP API.

## HTTP basics

Start the daemon with `flow serve`. Requests and responses are JSON unless noted. If a token is configured (`FLOW_AUTH_TOKEN`, or a file named by `FLOW_AUTH_TOKEN_FILE`), send `Authorization: Bearer <token>` to API routes; `/healthz` does not require it. The default daemon binds to loopback.

`flow serve --profile deployed` hardens a daemon that fronts a remote client: it refuses to start without auth (even on a unix socket); sessions may only compose `read_file` and `grep` (an explicit request for anything else is a 400); a session `callback_url` may only target a host listed in `FLOW_CALLBACK_HOSTS` (none configured means client callbacks are refused); and everything outside the core session verbs answers `403 {"detail": "disabled by server policy"}` — all of `/fs/*`, the session file diff, `/models` and `/providers*`, and the extension and skill routes. It also skips `~/.flow/extensions` (explicit `--extension` paths still load); answers `413` to request bodies over 32 MiB; and appends one JSONL row per sensitive call (any mutation, and every 401/403) to `<data_dir>/audit.jsonl` — timestamp, method, path, status, and site, never bodies. The default profile (`local`) changes nothing. Individual switches of either profile can be overridden with `FLOW_POLICY`, a JSON object of policy fields (e.g. `{"skills_api": true, "tool_allowlist": ["read_file", "grep", "bash"]}`) applied on top of the profile.

One daemon can serve many sites (a Frappe bench): point `FLOW_TENANTS_FILE` at a JSON file mapping each site to its bearer token, e.g. `{"site1.localhost": {"token": "…", "allowed_roots": ["/path/to/site1"]}}`. A request's token names its site, and every route then acts only on that site's sessions — stored under `data_dir/tenants/<site>`, so two sites can even reuse a session id. A site's `allowed_roots` fence its cwds and paths (omitted, it inherits the daemon-wide roots). Mutually exclusive with the single-token variables.

`POST /sessions` accepts a `SessionConfig`. Important fields are:

- `model`, `credential_id`, and optional `reasoning_effort` (`off` through `max`);
- `cwd`, `tools`, `client_tools`, and `auto_approve` (default: `false`);
- `system_prompt` for a complete prompt override, or `system_preamble`, `system_suffix`, and `system_append` for composition;
- `skills_enabled`, `skill_paths`, and compaction settings.

The server resolves credentials and prompt context itself; do not send API keys, provider URLs, or tokens in session or run requests. The one exception is a policy opt-in for clients that manage credentials themselves (the deployed profile turns it on, since e.g. Frappe resolves credentials per site): `api_key` and an optional `api_base` may then be sent on session create and on `POST /sessions/{sid}/model`, and replace the daemon's credential resolution for that session. On set-model the pair is replaced as a unit — sending either field replaces both, sending neither keeps the stored pair. The key persists with the session (owner-only files) and is redacted to `***` in every API response. When the policy switch is off (the default), a request carrying these fields is a 400.

## Service and provider routes

| Route | Purpose |
| --- | --- |
| `GET /healthz` | Returns `{"ok": true}`. |
| `GET /models` | Lists models available to configured providers and non-fatal discovery errors. |
| `GET /providers` | Lists built-in and custom providers plus their setup state. |
| `POST /providers/custom` | Saves an OpenAI-compatible endpoint: `name`, `base_url`, `models`, optional `api_key`. |
| `POST /providers/{id}/api-key` | Stores an API key. |
| `DELETE /providers/{id}` | Removes a stored provider or custom-endpoint credential. |
| `POST /providers/{id}/oauth/start` | Starts browser OAuth and returns an authorization URL. |
| `GET /providers/{id}/oauth/status` | Reads OAuth progress. |
| `POST /providers/{id}/oauth/complete` | Completes OAuth with `{"callback_url": "..."}`. |
| `POST /fs/pick` | Opens a native folder picker when the daemon host supports one. |

## Session routes

| Route | Purpose |
| --- | --- |
| `POST /sessions` | Creates a session from `SessionConfig`; returns its id and redacted config. |
| `GET /sessions` | Lists known sessions, newest first. |
| `GET /sessions/{sid}` | Returns state, config, effective model, title, context information, and image support. |
| `DELETE /sessions/{sid}` | Permanently deletes an idle session and its attachments. |
| `GET /sessions/{sid}/skills` | Returns the session's skill catalog and diagnostics. |
| `GET /sessions/{sid}/extensions` | Returns loaded server extensions and diagnostics. |
| `POST /extensions/reload` | Re-imports all extensions and returns the fresh info payload. |
| `POST /skills` | Previews the skills a supplied `SessionConfig` would discover. |
| `PATCH /sessions/{sid}/config` | Currently updates `{"auto_approve": true|false}`. |
| `POST /sessions/{sid}/model` | Sets `model`, optional `credential_id`, and optional `reasoning_effort`. With the inline-credentials policy on, also accepts `api_key`/`api_base`. |
| `POST /sessions/{sid}/rewind` | Moves the active branch to `{"target_seq": N}`; `0` means an empty conversation. |
| `POST /sessions/{sid}/compact` | Runs manual compaction; the optional body is `{"instructions": "..."}`. |

## Running a session

`POST /sessions/{sid}/run` takes `{"message": "...", "attachments": ["id"]}`. A blank message is allowed only with attachments. By default it starts in the background and returns `{"status": "started"}`. A message sent during an active run becomes steering and returns `{"status": "steered"}`.

Add `?wait=true` to `run`, `resume`, or `compact` to wait for completion. The response includes the terminal `reason`, final `output`, per-operation token `usage`, and any pending approval batch.

| Route | Purpose |
| --- | --- |
| `POST /sessions/{sid}/resume` | Continues a pause with `{"approval_seq": N, "answers": {"call-id": "Approve"}}`. Answers must cover exactly the pending calls. Use `Deny` or other text to reject or redirect. |
| `POST /sessions/{sid}/abort` | Stops an active run and drops uncommitted steering. |
| `POST /sessions/{sid}/cancel_pending` | Cancels every unanswered approval call and returns the session to idle. |
| `POST /sessions/{sid}/attachments` | Multipart upload with one or more `files` fields. Only supported images are accepted and normalized. |
| `DELETE /sessions/{sid}/attachments` | Removes unclaimed uploaded attachments: `{"attachments": ["id"]}`. |

Most invalid session states return `409`; unknown sessions return `404`.

## Entries and streaming

`GET /sessions/{sid}/entries` returns durable log entries. `path=active` is the current branch and is a full snapshot only. `path=all` includes abandoned branches and accepts `since=N`.

`GET /sessions/{sid}/stream?since=N` is an SSE feed. It first replays durable entries after `N`, then streams live events. Reconnect with the last durable `seq`. Without `follow=true`, the stream closes at a run boundary. With `follow=true`, it stays open across idle periods and sends `: keepalive` comments.

Durable events have a monotonic `seq`; live preview events such as `text_delta` do not. Render durable `assistant_message` and `tool_result` events as the source of truth, using deltas only for temporary output.
