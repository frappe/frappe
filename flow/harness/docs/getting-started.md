# Getting started

Flow is a coding agent that runs on your machine. This page gets you from install to a first working chat in the web UI.

## Install

Flow needs Python 3.14 or newer.

```sh
uv tool install frappe-flow
# or: pip install frappe-flow
```

## Run

```sh
flow
```

This starts a local server and opens the web UI in your browser (`http://127.0.0.1:8787`). Prefer a terminal? `flow tui` runs the same agent in the terminal. See [tui.md](tui.md).

## Connect a provider

Flow needs one model provider before it can answer. Type `/providers` in the composer and pick one:

- **API key**: paste the key from OpenAI, Anthropic, Gemini, OpenRouter, xAI, Groq, DeepSeek, Mistral, Cerebras or OpenCode Go.
- **Codex (OAuth)**: sign in with your ChatGPT account. No key needed.
- **Custom**: any OpenAI-compatible endpoint, such as a local Ollama, with its base URL and model ids.

The same setup works from the terminal:

```sh
flow login openai      # prompts for a key
flow login codex       # opens the browser for OAuth
flow providers         # shows what is configured
```

Then pick a model with `/model`. Keys are stored in `~/.flow/server/credentials.json` and never leave your machine except to call the provider.

## Your first chat

1. Pick a project folder with `/cwd` (or `/cwd /path/to/project`). The agent reads and writes inside it.
2. Type what you want and press Enter. `@` mentions a file, and images can be pasted or attached.
3. When the agent wants to run a command or change a file, it pauses and asks. Approve, deny, or type a redirect.

Switch to **Auto-approve** in `/settings` if you don't want the pauses.

## Built-in tools

| Tool | What it does |
| --- | --- |
| `bash` | Runs a shell command in the project folder. Asks first. |
| `read` | Reads a file, with paging for long ones. |
| `write` | Creates or overwrites a file. Asks first. |
| `edit` | Makes exact find-and-replace edits in a file. Asks first. |
| `subagent` | Hands a task to a child agent with a fresh context and gets back its answer. |
| `grep` | Searches file contents. Bundled but off by default; enable it in a preset. |

## Slash commands

Type `/` in the composer to see them.

| Command | Purpose |
| --- | --- |
| `/model` | Choose the model. |
| `/thinking` | Set the reasoning effort. |
| `/providers` | Connect or edit providers. |
| `/settings` | Approval mode, custom instructions, presets, skills, theme. |
| `/cwd [path]` | Start a new chat in a folder. |
| `/new` | Start a fresh chat. |
| `/rewind` | Branch from before your last message. |
| `/compact` | Summarize the conversation to free context. |
| `/transcript` | Every step of the chat and its token cost. |
| `/reload` | Re-import extensions after you change one. |
| `/abort` | Stop the running turn. |
| `/skill:<name>` | Run a skill (see below). |

## Presets

A preset is a saved agent setup for new chats: which tools are on, and a system prompt that replaces or extends the default one. Make one in `/settings` under **Agent presets**, for example a "Reviewer" with only `read` and `grep` and a review-focused prompt. A chat keeps the preset it started with.

## AGENTS.md

Put an `AGENTS.md` in a project to tell the agent how that project works: build commands, conventions, things to avoid. Flow reads it at the start of every chat in that folder, along with any `AGENTS.md` in the parent folders up to the git root. `~/AGENTS.md` applies to every project.

## Skills

A skill is a `SKILL.md` file with reusable instructions, such as a release checklist or a review procedure. Flow finds them in `~/.agents/skills/<name>/` (global) and `<project>/.agents/skills/<name>/` (per project). Create and edit them in `/settings` under **Skills**.

The agent sees the list of skills and loads one when it fits the task. You can also run one yourself with `/skill:<name>`. Details in [skills.md](skills.md).

## Extensions

An extension is a Python file in `~/.flow/extensions/` that adds tools or hooks into tool calls, with no change to Flow itself. A hook can block or rewrite a call before it runs, or rewrite what the model sees afterwards. Run `/reload` after editing one. Working examples live in [examples/extensions/](../examples/extensions/); the full guide is [extensions.md](extensions.md).
