# Authentication

flow_server owns user-global provider credentials. Clients select a model and may select
a named credential, but do not need to transport a provider secret on every session.

## CLI

```bash
flowd providers
flowd login openai
flowd login anthropic
flowd login codex
flowd logout openai
```

API-key login prompts without echo and stores the key in
`~/.flow-server/credentials.json`. Codex login uses OAuth PKCE and captures the redirect
on `127.0.0.1:1455`. For a headless environment, use `flowd login codex --manual` and
paste the full callback URL.

Built-in API-key providers are `openai`, `anthropic`, `gemini`, `openrouter`, `xai`,
`groq`, `deepseek`, `mistral`, `cerebras`, and `opencode-go`. `codex` is the native
ChatGPT subscription provider; use a model name such as `codex/gpt-5.4`.


## Resolution

For every run, authentication resolves in this order:

1. An explicit request `api_key` (compatibility/ephemeral override).
2. A stored provider credential (`api_key` or `oauth`).
3. The provider's standard environment variable.

The provider is inferred from the model prefix. Set `credential_id` on a session to use
a differently named credential, such as a key for a custom proxy. A stored credential
owns that provider: refresh or type errors are surfaced and never silently fall back to
another account.

Explicit request keys are held in memory only. They are excluded from session metadata
and disappear when the daemon restarts. Persistent credentials must go through
`flowd login`.

## Storage security

The credential directory is created as `0700`; its JSON and lock files are `0600`.
Writes are validated, locked, fsynced, and atomically replaced. OAuth refresh is
serialized per provider within the daemon so concurrent sessions do not consume the
same rotating refresh token.

The daemon binds to `127.0.0.1` by default. Set `FLOW_SERVER_AUTH_TOKEN` to require
`Authorization: Bearer <token>` on every endpoint except `/healthz`. `flowd serve`
refuses a non-loopback bind unless this token is configured.
