# Authentication

Flow keeps provider credentials outside sessions. Clients select a model and, when needed, a credential id; they never send provider secrets in a run request.

## Set up a provider

```bash
flow providers
flow login openai
flow login codex
flow logout openai
```

API-key providers prompt for a key. `codex` uses OAuth; `flow login codex --manual` prints the authorization URL and accepts a pasted callback URL for headless environments.

`orcarouter` offers both: `flow login orcarouter --method api-key` stores an existing
`sk-orca-…` key, and `flow login orcarouter --method oauth` (the default when you answer
its prompt) signs in through the browser and stores the key it issues. Either one is a
normal OrcaRouter API key; inference and model discovery do not know which was used.

The built-in providers are OpenAI, Anthropic, Gemini, OpenRouter, OrcaRouter, xAI, Groq, DeepSeek, Mistral, Cerebras, Codex, and OpenCode Go. The provider list is the source of truth for the current set:

```bash
flow providers
```

The HTTP API offers the same setup flow through `/providers`, including custom OpenAI-compatible endpoints and OAuth start/status/complete routes. See [api.md](api.md).

## Credential resolution

For a standard model, Flow chooses credentials in this order:

1. A stored credential for the selected provider or explicit `credential_id`.
2. That provider's configured API-key environment variable.

Custom endpoints are stored credentials containing their base URL, declared model ids, and optional key. An explicit `credential_id` pins a run to that endpoint; otherwise Flow uses an endpoint that declares the selected model.

OAuth credentials are refreshed shortly before expiry. If a provider rejects an access token, Flow refreshes once and retries the request. A stored credential error is reported; Flow does not silently switch to another account.

OrcaRouter is the exception: its sign-in returns a durable key with no expiry and no
refresh grant, so it is reused until it is revoked. A rejected one is marked for
re-authentication — Flow does not invent a refresh for it — and `flow login orcarouter`
replaces it.

## Storage and daemon access

Credentials default to `~/.flow/server/credentials.json`. Flow creates the credential directory with owner-only permissions, locks writes, and replaces the JSON atomically. Set `FLOW_CREDENTIALS_PATH` to store them elsewhere.

The daemon binds to `127.0.0.1` by default. Set `FLOW_AUTH_TOKEN` to require `Authorization: Bearer <token>` for API requests other than `/healthz`. `flow serve` refuses a non-loopback TCP bind without that token.
