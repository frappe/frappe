# API

Flow runs durable agent sessions. Use `Agent` when Python owns the process, or the HTTP API when a client connects to the daemon. Both use the same session log and event types.

## Python

```python
from flow_harness.agent import Agent

agent = Agent(model="mock", cwd=".")

async for event in agent.run("Summarize this project"):
    if event.type == "text_delta":
        print(event.text, end="", flush=True)
```

`Agent(config=None, *, data_dir="~/.flow/server", **overrides)` creates one session. `model` may be a model name or an injected `Model` instance.

| Method | Use |
| --- | --- |
| `run(message, before_tool_call=..., after_tool_call=...)` | Start a turn and yield events until it ends or pauses. |
| `resume(answers, approval_seq=..., ...)` | Continue a paused approval batch. A batch a running sub-agent waits on is answered too; its continuation shows in the run's stream. |
| `compact(instructions=None)` | Replace older context with a durable summary. |
| `abort()` | Ask the active run to stop; returns whether one was active. |
| `await rewind(target_seq)` | Move the active conversation branch back to an earlier entry. |
| `await set_model(model, credential_id=None)` | Choose the model for later turns. Not available with an injected model. |

`Agent.session` exposes the lower-level `Session` API. `run` and `resume` hooks are local Python callbacks; they are not part of the HTTP API.

## HTTP basics

Start the daemon with `flow serve`. Requests and responses are JSON unless noted. If a token is configured (`FLOW_AUTH_TOKEN`, or a file named by `FLOW_AUTH_TOKEN_FILE`), send `Authorization: Bearer <token>` to API routes; `/healthz` does not require it. The default daemon binds to loopback.

`flow serve --profile deployed` hardens a daemon that fronts a remote client: it refuses to start without auth (even on a unix socket); sessions may only compose `read` and `grep` (an explicit request for anything else is a 400); a session `callback_url` may only target a host listed in `FLOW_CALLBACK_HOSTS`, or, for a site with its own `callback_hosts` in the tenants file, one from that list instead (none configured means client callbacks are refused); and everything outside the core session verbs answers `403 {"detail": "disabled by server policy"}` — all of `/fs/*`, the session file diff and attach-by-path, `/models` and `/providers*`, the extension and skill routes, and the `/tools` list. It also skips `~/.flow/extensions` (explicit `--extension` paths still load); answers `413` to request bodies over 224 MiB (sized to fit a full attachment batch of 10 × 20 MiB files); and appends one JSONL row per sensitive call (any mutation, and every 401/403) to `<data_dir>/audit.jsonl` — timestamp, method, path, status, and site, never bodies. The default profile (`local`) changes nothing. Individual switches of either profile can be overridden with `FLOW_POLICY`, a JSON object of policy fields (e.g. `{"skills_api": true, "tool_allowlist": ["read", "grep", "bash"]}`) applied on top of the profile.

One daemon can serve many sites (a Frappe bench): point `FLOW_TENANTS_FILE` at a JSON file mapping each site to its bearer token, e.g. `{"site1.localhost": {"token": "…", "allowed_roots": ["/path/to/site1"]}}`. A request's token names its site, and every route then acts only on that site's sessions — stored under `data_dir/tenants/<site>`, so two sites can even reuse a session id. A site's `allowed_roots` fence its cwds and paths, and the file must list them for every site — a shared fence would let sites read each other's files, so a missing entry refuses startup. A site may also list `callback_hosts`, the `host[:port]` values its sessions' `callback_url` may target; the list replaces `FLOW_CALLBACK_HOSTS` for that site, so a bench adds a site and its callback host in one edit of the file. The daemon re-reads the file when a token matches nothing, so a site added to the file works at once, and on `POST /tenants/reload`, which whoever writes the file calls after editing or removing a site. The route takes any site's token, and answers 400 on a file it cannot read, the last good list still standing. Each site also resolves model credentials from its own partition, never the daemon-wide store — per-site keys are sent inline by the client — and the provider and credential routes (which manage the daemon-wide store) are disabled in this mode regardless of profile. Mutually exclusive with the single-token variables.

`POST /sessions` accepts a `SessionConfig`. Important fields are:

- `model`, `credential_id`, and optional `reasoning_effort` (`off` through `max`);
- `cwd`, `tools`, `extension_tools` (omit it to get every loaded extension tool), `client_tools`, and `auto_approve` (default: `false`);
- `subagents`, the sub-agents the `subagent` tool may run beside `general`, and `max_concurrent_subagents`, how many may run at once (see [tools.md](tools.md#sub-agents)); an agent's `api_key` and `api_base` are refused wherever the session's own are;
- `system_prompt` for a complete prompt override, or `system_preamble`, `system_suffix`, and `system_append` for composition;
- `skills_enabled`, `skill_paths`, and compaction settings.

The server resolves credentials and prompt context itself; do not send API keys, provider URLs, or tokens in session or run requests. The one exception is a policy opt-in for clients that manage credentials themselves (the deployed profile turns it on, since e.g. Frappe resolves credentials per site): `api_key` and an optional `api_base` may then be sent on session create and on `POST /sessions/{sid}/model`, and replace the daemon's credential resolution for that session. On set-model the pair is replaced as a unit — sending either field replaces both, sending neither keeps the stored pair. The key persists with the session (owner-only files) and is redacted to `***` in every API response. When the policy switch is off (the default), a request carrying these fields is a 400.

## Service and provider routes

| Route | Purpose |
| --- | --- |
| `GET /healthz` | Returns `{"ok": true}`. |
| `POST /tenants/reload` | Re-reads the tenants file after its writer edited or removed a site, and returns the site count; a file it cannot read is a 400. Takes any site's token. |
| `GET /models` | Lists models available to configured providers and non-fatal discovery errors. |
| `GET /providers` | Lists built-in and custom providers plus their setup state. |
| `POST /providers/custom` | Saves an OpenAI-compatible endpoint: `name`, `base_url`, `models`, optional `api_key`. |
| `PUT /providers/custom/{id}` | Rewrites a stored endpoint with the same fields; a blank `api_key` keeps the saved one. |
| `POST /providers/{id}/api-key` | Stores an API key. |
| `DELETE /providers/{id}` | Removes a stored provider or custom-endpoint credential. |
| `POST /providers/{id}/oauth/start` | Starts browser OAuth and returns an authorization URL. |
| `GET /providers/{id}/oauth/status` | Reads OAuth progress. |
| `POST /providers/{id}/oauth/complete` | Completes OAuth with `{"callback_url": "..."}`. |
| `POST /fs/pick` | Opens a native folder picker when the daemon host supports one. |
| `GET /fs/files?cwd=&path=` | Lists a directory under the absolute `cwd`; every `/fs` path is fenced by the allowed roots. |
| `GET /fs/files/search?cwd=&query=` | Finds paths under `cwd` containing `query`, case-insensitively; `truncated` says the scan hit its cap. |
| `GET /fs/file?cwd=&path=` | Reads one text file. |
| `PUT /fs/file` | Writes `{"cwd", "path", "content"}`; content over the file-view cap is a 413. |
| `GET /fs/git/changes?cwd=` | The repository's uncommitted files with added and removed line counts. |
| `GET /fs/git/file/diff?cwd=&path=` | HEAD and working-tree text of one uncommitted file. |
| `GET /tools` | Lists the built-in, bundled, and extension tools a session may enable under the daemon's policy; a bundled row has `"bundled": true`, and an extension row names its extension. A built-in stays listed beside an extension tool of the same name. |
| `GET /skills?cwd=` | Lists every `SKILL.md` under the global skill root and, with `cwd`, the project's, with parse errors per file; `truncated` names the scopes whose folder exceeded the scan cap. |
| `GET /skills/file?path=&cwd=` | Reads one managed `SKILL.md`. |
| `PUT /skills/file` | Writes `{"path", "content", "cwd"?}` to a managed `SKILL.md`, creating it. Invalid content is a 400 and nothing is written. |
| `DELETE /skills/file?path=&cwd=` | Deletes a managed `SKILL.md` and its directory when empty. |

## Session routes

| Route | Purpose |
| --- | --- |
| `POST /sessions` | Creates a session from `SessionConfig`; returns its id and redacted config. |
| `GET /sessions` | Lists known sessions, newest first. |
| `GET /sessions/{sid}` | Returns state, config, effective model, title, context information, and image support. |
| `DELETE /sessions/{sid}` | Permanently deletes an idle session and its attachments. |
| `GET /sessions/{sid}/skills` | Returns the skills the session can invoke — its catalog plus any added since it was created — and the diagnostics recorded at creation. |
| `GET /sessions/{sid}/extensions` | Returns loaded server extensions and diagnostics. |
| `POST /extensions/reload` | Re-imports all extensions and returns the fresh info payload. |
| `POST /skills` | Previews the skills a supplied `SessionConfig` would discover. |
| `PATCH /sessions/{sid}/config` | Updates `auto_approve`, `tools`, `client_tools` together with `confirm_tools`, or `title`; any other field is refused. An approval change applies at the next tool gate, a tool change to later runs. |
| `POST /sessions/{sid}/model` | Sets `model`, optional `credential_id`, and optional `reasoning_effort`. With the inline-credentials policy on, also accepts `api_key`/`api_base`. |
| `POST /sessions/{sid}/rewind` | Moves the active branch to `{"target_seq": N}`; `0` means an empty conversation. |
| `POST /sessions/{sid}/compact` | Runs manual compaction; the optional body is `{"instructions": "..."}`. |
| `GET /sessions/{sid}/file/diff?path=` | Original and current text of a file the session changed, for the diff viewer; 404 when the session never touched it. |

## Running a session

`POST /sessions/{sid}/run` takes `{"message": "...", "attachments": ["id"]}`. A blank message is allowed only with attachments. By default it starts in the background and returns `{"status": "started"}`. A message sent during an active run becomes steering and returns `{"status": "steered"}`.

Add `?wait=true` to `run`, `resume`, or `compact` to wait for completion. The response includes the terminal `reason`, final `output`, per-operation token `usage`, and any pending approval batch.

| Route | Purpose |
| --- | --- |
| `POST /sessions/{sid}/resume` | Continues a pause with `{"approval_seq": N, "answers": {"call-id": "Approve"}}`. Answers must cover exactly the pending calls. Use `Deny` or other text to reject or redirect. A batch a running sub-agent waits on is answered the same way and returns `{"status": "resumed"}`. |
| `POST /sessions/{sid}/abort` | Stops an active run and drops uncommitted steering. |
| `POST /sessions/{sid}/cancel_pending` | Cancels every unanswered approval call and returns the session to idle. While a run is active, it cancels the batches its sub-agents wait on instead. |
| `POST /sessions/{sid}/attachments` | Multipart upload with one or more `files` fields. Only supported images are accepted and normalized. |
| `POST /sessions/{sid}/attachments/files` | Attaches project files by path: `{"paths": ["src/a.py"]}`, resolved from `cwd`. Images are stored as images, anything else as text named by its cwd-relative path. |
| `GET /sessions/{sid}/attachments/{id}` | Returns an uploaded image's bytes, for previews. |
| `DELETE /sessions/{sid}/attachments` | Removes unclaimed uploaded attachments: `{"attachments": ["id"]}`. |

Most invalid session states return `409`; unknown sessions return `404`.

## Entries and streaming

`GET /sessions/{sid}/entries` returns durable log entries and the current live `preview`. `path=active` is the current branch and is a full snapshot only. `path=all` includes abandoned branches and accepts `since=N`.

The response also carries `stream_id` and `revision` for Redis catch-up. The revision advances for every event, including live deltas. The stream ID changes whenever the session is loaded again. These values are not durable log cursors; use `latest_seq` for `since`.

Subscribe and buffer live messages before requesting a snapshot. Apply the returned entries, replace the preview (even when empty), then apply buffered messages from the same stream with revisions above the snapshot's revision. Ignore older revisions. Fetch another snapshot on a revision gap or a `resync_required` signal. On a stream ID change, fetch a full snapshot with `since=0` and discard buffered messages from other streams. Remove transport fields (`site`, `session_id`, `stream_id`, `revision`) before parsing a message as a Harness event.

For resync signals, `session_ids` limits recovery to those tracked sessions within the scope named by the channel. When `session_ids` is absent, refresh all tracked sessions in that scope; a global signal covers all tracked sessions. Do not treat a session ID as unique across sites. Resync notices are transport messages, not Harness events. See [Redis channels](development.md#environment) for subscription details.

`GET /sessions/{sid}/stream?since=N` is an SSE feed. It first replays durable entries after `N`, then streams live events. Reconnect with the last durable `seq`. Without `follow=true`, the stream closes at a run boundary. With `follow=true`, it stays open across idle periods and sends `: keepalive` comments. Slow streams close when their event queue fills and should reconnect from their last durable `seq`.

When a run already has provisional assistant output, the stream emits `preview_replay_started` followed by a snapshot of the current text, thinking, tool-call, and retry events before continuing live. Clear only the existing provisional preview when that marker arrives, then fold the snapshot normally. Durable transcript entries are unaffected. This makes a fresh attachment restore output emitted before it connected and makes transport reconnects idempotent.

Durable events have a monotonic `seq`; live preview events such as `text_delta` do not. Render durable `assistant_message` and `tool_result` events as the source of truth, using deltas only for temporary output.
