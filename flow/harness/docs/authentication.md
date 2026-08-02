# Authentication

The flow server owns user-global provider credentials. Clients select a model and may select
a named credential; provider secrets and endpoints never belong in session or run
payloads.

## CLI

```bash
flowd providers
flowd login openai
flowd login anthropic
flowd login codex
flowd logout openai
```

API-key login prompts without echo and stores the key in
`~/.flow/server/credentials.json`. Codex login uses OAuth PKCE and captures the redirect
on `127.0.0.1:1455`. For a headless environment, use `flowd login codex --manual` and
paste the full callback URL.

Built-in API-key providers are `openai`, `anthropic`, `gemini`, `openrouter`, `xai`,
`groq`, `deepseek`, `mistral`, `cerebras`, and `opencode-go`. `codex` is the native
ChatGPT subscription provider; use a model name such as `codex/gpt-5.4`.

## Resolution

For every run, `resolve_model_auth` resolves in this order:

1. A stored provider credential (`api_key` or `oauth`).
2. The provider's standard environment variable.

The provider is inferred from the model prefix. Set `credential_id` on a session to use
a differently named credential, such as a key for a custom proxy. A stored credential
owns that provider: refresh or type errors are surfaced and never silently fall back to
another account.

OAuth resolution (`resolve_oauth`) refreshes tokens that are expired or within a
60-second skew of expiring, and hands the model adapter a one-shot `refresh` hook so a
token the provider rejects mid-run is refreshed exactly once and the request retried
(see `run_with_retries` in [architecture.md](architecture.md)).

Clients send only `model` and, when needed, `credential_id`. API keys must go through
`flowd login`; Codex tokens come from its OAuth flow. `api_key` and `api_base` are
rejected on both session creation and run requests.

## Storage security

The credential directory is created as `0700`; its JSON and lock files are `0600`.
Writes are validated, locked, and atomically replaced. OAuth refresh is
serialized per provider within the daemon so concurrent sessions do not consume the
same rotating refresh token.

The daemon binds to `127.0.0.1` by default. Set `FLOW_AUTH_TOKEN` to require
`Authorization: Bearer <token>` on every endpoint except `/healthz`. `flowd serve`
refuses a non-loopback bind unless this token is configured; embedders calling
`create_app` directly must pass `auth_token=` themselves.
