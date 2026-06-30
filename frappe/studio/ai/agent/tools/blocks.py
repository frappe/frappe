"""Block-editing tools. All are client-side: the loop batches the operations
and the frontend applies them to the canvas block tree."""

from studio.ai.agent.registry import Tool

update_block = Tool(
	name="update_block",
	side="client",
	description=(
		"Merge prop or style changes into an existing block on the page. Use it to change "
		"a block's text/label/variant (props); its colours, spacing, or typography (style); "
		"or its responsive overrides. Send ONLY the fields you are changing — merges are "
		"shallow. Set units on style values (e.g. padding '10px', not 10)."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {
				"type": "string",
				"description": "The target block's 'id' value from the page structure.",
			},
			"props": {
				"type": "object",
				"description": 'Component props to merge into componentProps, e.g. {"text":"Sign up"} for a TextBlock or {"label":"Save","variant":"solid"} for a Button.',
			},
			"style": {
				"type": "object",
				"description": 'Panel-editable desktop CSS (camelCase) to merge into baseStyles, e.g. {"color":"var(--ink-red-3)","padding":"12px"}.',
			},
			"rstyle": {
				"type": "object",
				"description": "Raw CSS for properties not in the style panel (opacity, transform, transition, …) to merge into rawStyles.",
			},
			"mstyle": {
				"type": "object",
				"description": "Mobile style overrides to merge into mobileStyles.",
			},
			"tstyle": {
				"type": "object",
				"description": "Tablet style overrides to merge into tabletStyles.",
			},
			"label": {
				"type": "string",
				"description": "Rename the block's descriptive label (blockName).",
			},
		},
		"required": ["component_id"],
	},
)

TOOLS = [update_block]
