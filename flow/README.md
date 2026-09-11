<div align="center">

# Flow

**AI agents for Frappe.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/frappe/flow/actions/workflows/ci.yml/badge.svg)](https://github.com/frappe/flow/actions/workflows/ci.yml)

</div>

<img width="1470" height="923" alt="image" src="https://github.com/user-attachments/assets/59749f10-ccc7-49ce-aa30-9d0dc46c117a" />

---

Flow puts an AI assistant inside your Frappe site. It knows your DocTypes, respects your permissions, and can operate your site in plain English — creating records, sending emails, building DocTypes, creating agents and tools, and setting up RAG chatbots.

**Set up a support agent:**
> *"Create an agent that resolves customer support issues. It should use the Support Ticket doctype and these files as its knowledge: [attach files]"*

Flow sets up the RAG pipeline, embeds and indexes the files, and keeps the DocType source in sync — automatically.


**Put reporting on autopilot:**
> *"Every weekday at 9am, email me a summary of yesterday's new leads with their contact details and source."*

**Do anything a user can do:**
> *"Find all overdue sales orders from last month and mark them as closed."*

---

## Quick Access

You can open the global AI chat interface from anywhere in the Frappe Desk by pressing:

<kbd>Cmd</kbd> + <kbd>I</kbd> *(or <kbd>Ctrl</kbd> + <kbd>I</kbd> on Windows)*

---

## Framework

Flow also ships as a Python framework for building agents in code.

### Define a tool

```python
import frappe
from flow import tool

@tool
def get_open_todos(allocated_to: str) -> list[dict]:
	"""List open ToDo items for a user."""
	return frappe.get_list(
		"ToDo",
		filters={"allocated_to": allocated_to, "status": "Open"},
		fields=["name", "description", "status"],
	)
```

### Run an agent

```python
from flow import Agent

agent = Agent(
	name="Todo Assistant",
	model="Claude Sonnet 4.6",  # a Flow Model
	instructions="You help with Frappe tasks.",
	tools=[get_open_todos],
)

run = agent.run("List open ToDo items assigned to me")
```

```python
# myapp/ai.py
def agents():
	return [agent]


# hooks.py
flow_agents = ["myapp.ai.agents"]
```

The definition lives in code, and constructing an `Agent` touches nothing. On every migrate and app install, Flow writes each agent returned by the `flow_agents` hook to the site as a `Flow Agent` record plus an Imported `Flow Tool` for each `@tool` function (`agent.sync()` does the same by hand, say from the console). These records are system-generated: the Desk can enable or disable them and switch the agent's model (a site choice), nothing else. Tools must be module-level functions in an installed app, since the flow server calls them back by import path; they run on the site as the session's owner, with that user's permissions. Users need read access to the `Flow Agent` and its `Flow Model`.

`run()` starts the turn on the flow server and returns the `Flow Run` while it is still `Running`; it never waits. The run is updated when the turn ends, so react to the outcome through `Flow Run` document events, or give the agent a tool that writes the result.

### Persist a conversation

```python
session = agent.new_session(title="Todo assistant")

session.chat("What tasks do I have open?")
session.chat("Close the ones due before last Friday.")
```

Every turn is saved as a `Flow Run` linked to the session — so conversation history, tool calls, and outputs are all in the database. `chat()` returns the run immediately; a message sent while a turn is still running joins it. Answer a tool approval with `session.resume(answers)` and stop a turn with `session.abort()`.

Files travel with the turn they are sent on: `session.chat("Summarize this", attachments=[file.name])` takes `File` names the user can read (text, PDF, Office, HTML and images; scans and images are read by OCR). Up to half of the model's total context is reserved for exact attachment text on each turn, independent of conversation length; only an attached set larger than that is chunked into a per-session index, with the largest files moved to retrieval first. The turn that attaches such a file gets its most relevant excerpts; later turns search it with the builtin `search_attachments` tool. Images go to a vision model as images.

An agent with the builtin `update_memory` tool remembers: it saves short facts, shared by everyone who uses the agent or private to one user, and each message brings along only the saved facts relevant to it. Relevance is hybrid vector and keyword search with a score floor when Flow Knowledge Settings has an embedding model, keyword search otherwise. A thumbs-down comment on a run is saved the same way.

An agent with the builtin `load_skill` tool sees the name and description of each skill bound to it, plus any skill marked available to all agents, and loads one when a task matches. Binding a skill attaches the tool; the built-in assistant always has it.

Tool calls can require human confirmation before executing, and every run is persisted for audit.

---

## Installation

Install into an existing [bench](https://github.com/frappe/bench):

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app flow
bench --site site-name install-app flow
```

Then add a `Flow Provider` with your API key and a `Flow Model` with a model ID such as `anthropic/claude-sonnet-4-6`, and open the Desk Flow panel to start. For local providers like Ollama or LM Studio, set `Base URL` on the provider or model.

### Flow server

Conversations run on a bench-local daemon provided by the `frappe-flow` package, one per bench and shared by every site. The package is installed into the bench environment as a dependency of the Flow app. Installing the app on a site provisions the site and starts the daemon; `bench flow-server setup` does the same by hand, and `start`, `stop`, `restart` and `status` do what they say.

- Durable data and `tenants.json` live under `<bench>/sites/flow-server/` so they survive deployments. The socket and PID are runtime files under `<bench>/flow-server/`, and logs go to `<bench>/logs/flow-server.log`.
- Sessions have no file access: the daemon's own read and grep tools are switched off for every session. The only path in a site's fence is its public files folder, which sessions use as their working directory.
- Each site gets a `flow_server_secret` in its site config. The daemon calls the site back for tool calls at `flow_server_url` if set, otherwise at the site URL Frappe computes (`host_name`, `http_port`, or `webserver_port` in developer mode). Set that before the first chat: changing it later invalidates the callback URLs of existing sessions.
- `flow_callback_timeout` in site config caps how many seconds the daemon waits for a tool call to answer (the daemon's default is 120).
- Events are published to the bench's `redis_queue`, or `flow_redis_url` from `common_site_config.json`.
- The scheduler restarts a dead daemon within five minutes, and `bench migrate` restarts it so updates ship. Uninstalling the app from a site removes its token and session data; removing the last site stops the daemon.

## License

[GNU AGPLv3](license.txt)
