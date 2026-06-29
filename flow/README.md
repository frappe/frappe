<div align="center">

# Flow

**AI agents for Frappe.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/frappe/flow/actions/workflows/ci.yml/badge.svg)](https://github.com/frappe/flow/actions/workflows/ci.yml)

</div>

<img width="1470" height="923" alt="image" src="https://github.com/user-attachments/assets/f097e271-47ff-4c97-9ef0-a3647959e8d4" />

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

## Framework

Flow also ships as a Python framework for building agents in code.

### DocTypes

| DocType | Purpose |
| --- | --- |
| `Flow Provider` | Provider-level credentials and endpoint settings |
| `Flow Model` | Model configuration — set a `model_id` like `anthropic/claude-sonnet-4-6` |
| `Flow Tool` | Reusable tools, defined as a module path or inline script |
| `Flow Agent` | Instructions, model, and tools — configurable from the Desk or in code |
| `Flow Trigger` | Run an agent on a DocType event or a schedule |
| `Flow Knowledge Base` / `Flow Knowledge Source` | Knowledge sources (files, URLs, DocTypes) for retrieval-augmented answers |
| `Flow Session` / `Flow Run` | Persisted conversations and execution history |

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
	model="anthropic/claude-sonnet-4-6",
	instructions="You help with Frappe tasks.",
	tools=[get_open_todos],
)

result = agent.run("List open ToDo items assigned to me")
print(result.output)
```

### Persist a conversation

```python
session = agent.new_session(title="Todo assistant")

session.chat("What tasks do I have open?")
session.chat("Close the ones due before last Friday.")
```

Every turn is saved as a `Flow Run` linked to the session — so conversation history, tool calls, and outputs are all in the database.

### Built-in tools

| Tool | What it does |
| --- | --- |
| `find_doctypes` | Search for DocTypes by name or module |
| `describe` | Get the fields, filters, and available actions for a DocType or record |
| `read` | Fetch records from any DocType |
| `create` | Create one or more records |
| `update` | Update fields across multiple records at once |
| `delete` | Delete records |
| `run_action` | Call a whitelisted method or workflow action on a record |
| `execute` | Run arbitrary Python in a sandboxed context |

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

## License

[GNU AGPLv3](license.txt)
