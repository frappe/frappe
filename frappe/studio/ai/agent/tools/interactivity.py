"""Interactivity tools — wire behaviour onto EXISTING blocks: event handlers and
visibility conditions.

Both are client-side: the loop validates the ref against the WorkingTree, then emits
the op for the canvas to apply. For a block you are CREATING this turn, bake the
handler / condition into the block instead (add_block/generate_page 'events' and
'visibility' fields) — a new block has no id to target.

An event handler runs as a 'Run Script' action: arbitrary JS evaluated with the page's
script context in scope — variables (as refs: read/write via `.value`, e.g.
`counter.value++`), data sources, page-script bindings, and `route`/`router`.
"""

from studio.ai.agent.registry import Tool

set_event_handler = Tool(
	name="set_event_handler",
	side="client",
	description=(
		"Attach a JavaScript event handler to a block that ALREADY EXISTS on the page (for a block "
		"you're adding this turn, put it in the block's 'events' field in add_block instead). The "
		"script runs with the page context in scope: variables are refs — read/write with `.value` "
		"(e.g. to increment a counter variable: `counter.value++`); data sources are available as "
		"<source>.data. Example: on a button, event='click', script='counter.value++'."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The target block's id."},
			"event": {
				"type": "string",
				"description": "The DOM event: click, change, focus, blur, submit, keydown, keyup, keypress.",
			},
			"script": {
				"type": "string",
				"description": "JavaScript to run when the event fires, e.g. 'counter.value++' or 'todos.reload()'.",
			},
		},
		"required": ["component_id", "event", "script"],
	},
)

set_visibility = Tool(
	name="set_visibility",
	side="client",
	description=(
		"Show/hide a block that ALREADY EXISTS on the page based on a condition (for a new block, use "
		"the 'visibility' field in add_block instead). The block renders only when the expression is "
		"truthy. Pass the expression WITHOUT braces — e.g. expression='todos.data.length > 0' hides an "
		"empty list; expression='showDetails' ties visibility to a Boolean variable."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The target block's id."},
			"expression": {
				"type": "string",
				"description": "Condition to show the block, WITHOUT {{ }} — e.g. 'todos.data.length > 0'.",
			},
		},
		"required": ["component_id", "expression"],
	},
)

TOOLS = [set_event_handler, set_visibility]
