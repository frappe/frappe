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

update_blocks = Tool(
	name="update_blocks",
	side="client",
	description=(
		"Apply edits to MANY blocks in ONE call — the right tool for page-wide changes "
		"(translate every text block, restyle all buttons, recolour all headings). Pair it "
		"with query_blocks: query the set, then update it here in a single call. Two modes:\n"
		"• UNIFORM — set 'component_ids' (a list of ids) plus any of props / style / rstyle / "
		"mstyle / tstyle. The SAME change is merged into every listed block (e.g. colour all "
		"headings red).\n"
		"• PER-BLOCK — set 'patches', a list where each item is {component_id, …same fields as "
		"update_block}. Each block gets its OWN values. Use this for translation/rewrites where "
		"the new text differs per block.\n"
		"If 'patches' is given it takes precedence. Merges are shallow, like update_block."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_ids": {
				"type": "array",
				"items": {"type": "string"},
				"description": "UNIFORM mode: the ids to apply the same change to. Ignored if 'patches' is set.",
			},
			"props": {
				"type": "object",
				"description": "UNIFORM mode: props to merge into every listed block.",
			},
			"style": {
				"type": "object",
				"description": "UNIFORM mode: desktop styles to merge into every listed block.",
			},
			"rstyle": {"type": "object", "description": "UNIFORM mode: raw styles to merge."},
			"mstyle": {"type": "object", "description": "UNIFORM mode: mobile style overrides to merge."},
			"tstyle": {"type": "object", "description": "UNIFORM mode: tablet style overrides to merge."},
			"patches": {
				"type": "array",
				"description": "PER-BLOCK mode: one object per block, each with 'component_id' plus the fields to change on that block.",
				"items": {
					"type": "object",
					"properties": {
						"component_id": {"type": "string", "description": "The target block's id."},
						"props": {"type": "object"},
						"style": {"type": "object"},
						"rstyle": {"type": "object"},
						"mstyle": {"type": "object"},
						"tstyle": {"type": "object"},
						"label": {"type": "string"},
					},
					"required": ["component_id"],
				},
			},
		},
	},
)

add_block = Tool(
	name="add_block",
	side="client",
	description=(
		"Insert a new block (and optionally its subtree) as a child of an existing block. Use "
		"this to add sections, components, or elements anywhere in the page tree. Do NOT include "
		"an 'id' — Studio assigns it. Use container/div for layout wrappers and catalog "
		"components (Button, TextBlock, …) for content."
	),
	parameters={
		"type": "object",
		"properties": {
			"parent_component_id": {
				"type": "string",
				"description": "The id of the parent block that will contain the new block.",
			},
			"block": {
				"type": "object",
				"description": "The new block definition, in the same compact vocabulary as the page structure. Do NOT include 'id'.",
				"properties": {
					"name": {
						"type": "string",
						"description": "componentName — a catalog component, or 'container'/'div'.",
					},
					"label": {"type": "string", "description": "Descriptive label for the block."},
					"props": {"type": "object", "description": "componentProps (text, label, variant, …)."},
					"style": {"type": "object", "description": "Panel-editable desktop CSS (camelCase)."},
					"rstyle": {
						"type": "object",
						"description": "Raw CSS for properties not in the style panel.",
					},
					"mstyle": {"type": "object", "description": "Mobile style overrides."},
					"tstyle": {"type": "object", "description": "Tablet style overrides."},
					"events": {
						"type": "object",
						"description": 'Event handlers: eventName → JS script, e.g. {"click":"counter.value++"}. Variables are refs (write with .value).',
					},
					"visibility": {
						"type": "string",
						"description": 'Render only when a {{ }} expression is truthy, e.g. "{{ todos.data.length > 0 }}".',
					},
					"c": {
						"type": "array",
						"description": "Child blocks (same schema, recursively). These fill the component's DEFAULT slot.",
						"items": {"type": "object"},
					},
					"slots": {
						"type": "object",
						"description": 'NAMED slots (only for components that expose them): {"<slotName>": [ child block objects ]} — each value is a list of blocks in this same schema. Use "c" for default-slot content; use "slots" only for named slots.',
					},
				},
				"required": ["name"],
			},
			"after_component_id": {
				"type": "string",
				"description": "Insert the new block immediately after this sibling's id. Takes precedence over 'index'.",
			},
			"index": {
				"type": "integer",
				"description": "Zero-based position in the parent's children. Defaults to appending at the end.",
			},
		},
		"required": ["parent_component_id", "block"],
	},
)

remove_block = Tool(
	name="remove_block",
	side="client",
	description="Delete an existing block (and all its descendants) from the page.",
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The id of the block to delete."},
		},
		"required": ["component_id"],
	},
)

move_block = Tool(
	name="move_block",
	side="client",
	description="Move an existing block to a different parent, or reorder it within the same parent.",
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The id of the block to move."},
			"new_parent_component_id": {"type": "string", "description": "The id of the new parent block."},
			"after_component_id": {
				"type": "string",
				"description": "Place the block immediately after this sibling's id in the new parent. Takes precedence over 'index'.",
			},
			"index": {
				"type": "integer",
				"description": "Zero-based position in the new parent's children. Defaults to appending at the end.",
			},
		},
		"required": ["component_id", "new_parent_component_id"],
	},
)

set_slot = Tool(
	name="set_slot",
	side="client",
	description=(
		"Fill a NAMED slot of a block that ALREADY EXISTS on the page — the component-specific slots "
		"a frappe-ui component exposes beyond its default slot (e.g. a card's header/footer, a custom "
		"prefix/suffix). Replaces that slot's content with 'blocks' (a list of block definitions in the "
		"add_block schema — they get their ids on the canvas, so bake any bindings/events into their "
		"props). A slot only holds blocks: for a text label use a TextBlock. For default-slot content, "
		"add children with add_block instead; for a block you are CREATING this turn, put named slots in "
		"its add_block 'slots' field rather than calling this."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The id of the block whose slot to fill."},
			"slot_name": {
				"type": "string",
				"description": "The named slot to set, e.g. 'header', 'footer', 'prefix'.",
			},
			"blocks": {
				"type": "array",
				"description": "Block definitions to place in the slot (add_block schema, recursively). Do NOT include ids.",
				"items": {"type": "object"},
			},
		},
		"required": ["component_id", "slot_name", "blocks"],
	},
)

remove_slot = Tool(
	name="remove_slot",
	side="client",
	description=(
		"Remove a NAMED slot (and its content) from a block that ALREADY EXISTS. Use this to undo a "
		"slot set on the wrong name — e.g. a slot was put on 'footer' but the component's real slot is "
		"'footer-items', so remove 'footer'. Only affects componentSlots; to clear default-slot content, "
		"remove those child blocks with remove_block instead."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The id of the block to remove the slot from."},
			"slot_name": {"type": "string", "description": "The named slot to remove, e.g. 'footer'."},
		},
		"required": ["component_id", "slot_name"],
	},
)

TOOLS = [update_block, update_blocks, add_block, remove_block, move_block, set_slot, remove_slot]
