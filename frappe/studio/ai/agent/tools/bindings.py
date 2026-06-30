"""Binding tools — wire a block's props to live data via `{{ }}` expressions.

Both are client-side: the loop validates the ref against the WorkingTree, then
emits the op for the canvas to apply on the block tree. The expression contract
is Studio's: a prop value of "{{ <expr> }}" is evaluated against the page's
data context — variables, resources (`<data_source>.data`), page-script
bindings, route/router, and globalUtils.
"""

from studio.ai.agent.registry import Tool

bind_prop = Tool(
	name="bind_prop",
	side="client",
	description=(
		"Bind one prop of a block to a live expression instead of a static value. The expression is "
		"evaluated against the page's data context: data sources (as <data_source>.data), variables, "
		"page-script bindings, and route/router. Pass the raw expression WITHOUT braces — e.g. "
		"prop='value', expression='counter' binds to the counter variable; "
		"expression='todos.data.length' shows a count. Inside a Repeater, bind to the current row "
		"with `dataItem.<field>` (e.g. expression='dataItem.title') — NOT `<source>.data.<field>`. "
		"Use this for scalar/text props; use set_repeater_data to feed a list into a Repeater."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The target block's id."},
			"prop": {
				"type": "string",
				"description": "The component prop to bind, e.g. 'text', 'label', 'modelValue', 'value'.",
			},
			"expression": {
				"type": "string",
				"description": "The expression to bind to, WITHOUT {{ }} — e.g. 'todos.data.length' or 'counter'.",
			},
		},
		"required": ["component_id", "prop", "expression"],
	},
)

set_repeater_data = Tool(
	name="set_repeater_data",
	side="client",
	description=(
		"Feed a Document-List data source into a Repeater so its single child block repeats once per "
		"record. Sets the Repeater's data to {{ <data_source_name>.data }} and its dataKey to the "
		"field that uniquely identifies each row (usually 'name'). The Repeater must have ONE child "
		"as the row template — do not add a child per record. Then bind that child's props (and its "
		"descendants') to the CURRENT ROW with bind_prop using `dataItem.<field>` expressions, e.g. "
		"bind_prop(prop='text', expression='dataItem.description'). For a tabular ListView instead, "
		"skip this tool and bind its 'rows' prop with bind_prop(prop='rows', expression='<data_source>.data')."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The Repeater block's id."},
			"data_source_name": {
				"type": "string",
				"description": "The data source to repeat over (its rows come from <name>.data).",
			},
			"data_key": {
				"type": "string",
				"description": "Field that uniquely keys each row, usually 'name'.",
			},
		},
		"required": ["component_id", "data_source_name", "data_key"],
	},
)

TOOLS = [bind_prop, set_repeater_data]
