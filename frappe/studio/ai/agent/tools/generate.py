"""Full-page generation tool.

`generate_page` is an *artifact* tool: the conversational model calls it with a
short `brief`, and the loop hands execution to `generate_page_json`, which streams
the full page block JSON on the heavy model as content (so the canvas renders live)
and returns the canonical client op the frontend applies. The agent calling this
tool is the only trigger for generation — see agent/artifact.py.
"""

from studio.ai.agent.artifact import generate_page_json
from studio.ai.agent.registry import Tool

generate_page = Tool(
	name="generate_page",
	side="client",
	artifact="page_json",
	generator=generate_page_json,
	description=(
		"Build a complete page from scratch and replace the entire page with it. Use this when "
		"the page is empty, or when the user asks to create a new page or fully redesign the "
		"existing one — but only AFTER the user has approved a proposed plan. When a plan is "
		"pending and the user approves it (any affirmative), call THIS — do not call propose_plan "
		"again. For small, targeted edits to an existing page, use the block tools (update_block, "
		"add_block, …) instead — do NOT regenerate the whole page for a minor change."
	),
	parameters={
		"type": "object",
		"properties": {
			"brief": {
				"type": "string",
				"description": (
					"A concise spec of the page to build, drawn from the approved plan and "
					"conversation: the design direction (layout style, typography mood), brand/product "
					"name and one-line positioning, the section list with real copy intent, and the "
					"palette. Do NOT write the JSON yourself — the brief guides a dedicated generation step."
				),
			},
		},
		"required": ["brief"],
	},
)

TOOLS = [generate_page]
