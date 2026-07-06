"""Selector tools: find and inspect blocks by structural filters.

`query_blocks` is server-side — it walks the turn-start page tree the frontend
shipped and returns the matching blocks' ids (+ component and full text). This
grounds bulk edits: instead of scanning the page context and hoping it catches
every block, the model asks for the exact set ("all text", "all Button") and gets
it deterministically, then applies one `update_blocks` call. Text is returned in
FULL — translation/rewrite needs every block's real copy.
"""

from studio.ai.agent.registry import Tool
from studio.ai.agent.selectors import block_text, find_block, match_block, walk_blocks
from studio.ai.block_codec import BlockCodec


def run_query_blocks(ctx, args: dict) -> str:
	root = ctx._page_root()
	if root is None:
		return "The page is empty — nothing to select."

	scope = args.get("within")
	start = root
	if scope:
		start = find_block(root, scope)
		if start is None:
			return f"No block found with id {scope}."

	component = args.get("component")
	text_only = bool(args.get("text_only"))
	contains = args.get("contains")

	matches = []
	for block, _depth in walk_blocks(start):
		if not match_block(block, component=component, text_only=text_only, contains=contains):
			continue
		component_id = block.get("componentId")
		if not component_id:
			continue
		entry = {"id": component_id, "name": block.get("componentName") or "div"}
		if text := block_text(block):
			entry["text"] = text  # full text, never truncated — needed for translate/rewrite
		matches.append(entry)

	if not matches:
		return "No blocks matched. Loosen the filters or check the page outline."
	header = f"{len(matches)} block(s) matched (page as it was at the start of this turn):\n"
	return header + BlockCodec.to_json(matches)


query_blocks = Tool(
	name="query_blocks",
	side="server",
	handler=run_query_blocks,
	description=(
		"Find blocks on the current page by structural filters, returning each match's 'id' "
		"(its component_id), component name, and FULL text. Use this before any change that "
		"affects MANY blocks — translate the page, restyle every Button, rewrite all headings "
		"— so you act on the complete, exact set instead of guessing from the outline. Filters "
		"AND together. Then apply the change with ONE update_blocks call. Results reflect the "
		"page at the start of this turn (edits you make mid-turn are not re-queried)."
	),
	parameters={
		"type": "object",
		"properties": {
			"component": {
				"type": "string",
				"description": "Match only this component name (e.g. 'TextBlock', 'Button', 'container').",
			},
			"text_only": {
				"type": "boolean",
				"description": "Match only text-bearing blocks (headings, paragraphs, labels, buttons…). Use this for translate/rewrite-all requests.",
			},
			"contains": {
				"type": "string",
				"description": "Match only blocks whose text contains this substring (case-insensitive).",
			},
			"within": {
				"type": "string",
				"description": "Limit the search to the subtree under this block's id. Defaults to the whole page.",
			},
		},
	},
)


def run_read_block(ctx, args: dict) -> str:
	root = ctx._page_root()
	if root is None:
		return "The page is empty."
	component_id = args.get("component_id")
	block = find_block(root, component_id) if component_id else None
	if block is None:
		return f"No block found with id {component_id}."
	detail = BlockCodec.to_json(BlockCodec.compress(block))
	return f"Block {component_id} (full props/styles/children, as of the start of this turn):\n{detail}"


read_block = Tool(
	name="read_block",
	side="server",
	handler=run_read_block,
	description=(
		"Return a block's FULL detail — its props, styles, and child subtree — by id. Use this "
		"before editing a block whose current props/styles you need to see, or to match the "
		"styling of an existing section. Reflects the page at the start of this turn."
	),
	parameters={
		"type": "object",
		"properties": {
			"component_id": {"type": "string", "description": "The id of the block to inspect."},
		},
		"required": ["component_id"],
	},
)

TOOLS = [query_blocks, read_block]
