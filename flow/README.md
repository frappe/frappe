# Flow

Flow is a Frappe app for running AI agents inside a Frappe site.

It includes:

- `AI Provider` for provider-level credentials and endpoint settings
- `AI Model` for LiteLLM model configuration
- `AI Tool` for reusable module or script tools
- `AI Agent` for instructions, model selection, and tool access
- `AI Trigger` for DocType-event and scheduled automation
- `AI Session` and `AI Run` for persisted conversations and execution history
- a Desk sidebar for chatting with the built-in assistant

Flow ships with built-in tools for common site operations:

- `find_doctypes`
- `describe`
- `read`
- `create`
- `update`
- `delete`
- `run_action`
- `execute`

## Installation

Install Flow into an existing bench:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/ShrihariMahabal/flow.git
bench --site site-name install-app flow
```

## Usage

1. Create an `AI Provider` with your provider name and API key.
2. Create an `AI Model` using a LiteLLM model ID such as `openai/gpt-4.1` or `anthropic/claude-sonnet-4-6`.
3. Save the model and test the connection from the form.
4. Create any `AI Tool` records you need. Tools can be created in code or directly from the `AI Tool` DocType.
5. Create an `AI Agent` and attach the tools you want it to use.
6. Open the Desk AI panel and start a conversation with the built-in `Assistant` or your own agent.
7. Open `AI Run` to inspect the execution details.
8. Open `AI Session` to review the saved conversation.
9. Create an `AI Trigger` if you want the agent to run on a document event or on a schedule.
10. For a simple trigger test, use a target like `ToDo`, pick a DocType event such as `after_insert` or `on_update`, write a prompt template, and then create or update a matching record.
11. If a tool call pauses for confirmation, approve or respond to it from the UI and then review the updated run and session.

For local providers like Ollama or LM Studio, leave the API key empty and set `Base URL` on either the provider or model.

## Code Examples

### Create a tool in code

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

The same tool can also be created from the `AI Tool` DocType as either:

- a `Module` tool pointing at an import path
- a `Script` tool with inline code

### Run an agent directly

```python
from flow import Agent

agent = Agent(
	name="todo-helper",
	model="gemini/gemini-2.5-flash",
	instructions="You help with Frappe tasks.",
	tools=[get_open_todos]
)

events = agent.run("List open ToDo items assigned to me", stream=True)

for event in events:
	print(event)
```

## License

MIT
