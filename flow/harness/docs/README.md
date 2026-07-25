# flow_server

A standalone, client-server **agent core** — "the brain." It runs the agent loop
(model ↔ tools), owns a durable event log, and dispatches tools either in-process or
back to a client over HTTP. Frappe/Flow is just one client among many; the CLI is
another; an embedding Python app is a third.

The daemon is deliberately **client-neutral** — no host-specific logic leaks in. The
main extensibility seam is `SessionConfig`, while provider credentials and endpoints
remain server-owned.

## Why a daemon with a durable log?

Everything the loop emits is a numbered, persisted event. That single design choice buys:

- **Disconnect tolerance** — a run lives in the daemon, not in your HTTP request. Drop
  the connection, reconnect later, and replay from your last cursor catches you up.
- **Restart tolerance** — session state (transcript, pending approvals) is rebuilt from
  the log, so a run can survive a daemon restart mid-approval.
- **One code path for "catch up" and "watch live"** — `GET /stream?since=N` replays the
  log from `N`, then attaches to the live feed.

tau and pi (the reference implementations) are in-process/streaming-only; the durable
log is flow_server's deliberate divergence for exactly this multi-client, disconnect-
tolerant use case.

## Quickstart

```bash
pip install -e ".[dev]"        # or: uv pip install -e ".[dev]"
```

**In-process** (the `Agent` front door):

```python
import asyncio
from flow_server.agent import Agent

async def main():
    agent = Agent(model="mock", system_prompt="You are a coding agent.", cwd=".")
    async for event in agent.run("List the files here."):
        print(event.type, getattr(event, "text", ""))

asyncio.run(main())
```

**As a daemon:**

```bash
flowd serve --port 8787
```

Then talk HTTP (create a session, `POST /sessions/{id}/run`, `GET .../stream`). See
[api.md](api.md). Durable state defaults to `~/.flow/server`, independent of the
directory where `flowd` is started.

## Documentation

- **[architecture.md](architecture.md)** — the layers, the event protocol, the durable
  log, the agent loop, and an end-to-end execution trace. Start here.
- **[api.md](api.md)** — the in-process `Agent` API and the HTTP API reference, with
  examples.
- **[authentication.md](authentication.md)** — provider login, credential resolution,
  and daemon security.
- **[tools.md](tools.md)** — the tool model, writing a new tool, the builtins, and how
  confirmation works.
- **[development.md](development.md)** — setup, tests, the ruff clean bar, conventions,
  and env/config.

## Status

**Part 1 (the headless daemon) is complete** — durable event substrate, model layer,
auth foundation, tools, agent loop, and the uniform HTTP API + `flowd`.

Planned: Part 2 (a TUI + a standalone web UI over the same API) and Part 3 (Flow adopts
the daemon as a client). See the roadmap in [development.md](development.md).
