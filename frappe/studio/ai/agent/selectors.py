"""Tree helpers for the agent's selector tools.

The server already holds the full page tree (the frontend ships it as
`page_context`), so block selection and inspection are answered here without a
frontend round-trip. These walk the native block dict (componentName /
componentId / children / …) — the same shape `BlockCodec` operates on.
"""

from collections.abc import Iterator


def child_blocks(block: dict) -> Iterator[dict]:
	"""A block's direct child blocks: its `children` PLUS blocks nested in named slots
	(componentSlots[<name>].slotContent). Slotted blocks
	are real children of the block — walking only `children` makes them unreachable for
	selection and ref-validation."""
	for child in block.get("children") or []:
		if isinstance(child, dict):
			yield child
	for slot in (block.get("componentSlots") or {}).values():
		content = slot.get("slotContent") if isinstance(slot, dict) else None
		if isinstance(content, list):
			for child in content:
				if isinstance(child, dict):
					yield child


def walk_blocks(root: dict, depth: int = 0) -> Iterator[tuple[dict, int]]:
	"""Yield (block, depth) for the root and every descendant, depth-first — descending
	both `children` and named-slot content (see child_blocks)."""
	if not isinstance(root, dict):
		return
	yield root, depth
	for child in child_blocks(root):
		yield from walk_blocks(child, depth + 1)


def find_block(root: dict, component_id: str) -> dict | None:
	"""Return the block with this componentId, or None."""
	for block, _depth in walk_blocks(root):
		if block.get("componentId") == component_id:
			return block
	return None


# componentProps keys that hold user-visible copy, in priority order. Studio blocks
# carry text in props (there is no innerHTML), so block_text reads the first non-empty
# one — enough to ground translate/rewrite and "find all text" queries.
TEXT_PROP_KEYS = ("text", "label", "title", "message", "description", "placeholder")


def block_text(block: dict) -> str:
	"""The block's own user-visible copy, from its componentProps. Empty for containers."""
	props = block.get("componentProps") or {}
	for key in TEXT_PROP_KEYS:
		value = props.get(key)
		if isinstance(value, str) and value.strip():
			return value.strip()
	return ""


def is_text_block(block: dict) -> bool:
	"""A block that carries user-visible copy (a heading, label, button, paragraph…).
	Defined by SHAPE — a non-empty text prop — so translate/rewrite-all reaches every
	piece of copy regardless of component."""
	return bool(block_text(block))


def match_block(
	block: dict,
	*,
	component: str | None = None,
	text_only: bool = False,
	contains: str | None = None,
) -> bool:
	"""Does this block satisfy every supplied filter? Filters AND together."""
	if component and (block.get("componentName") or "").lower() != component.lower():
		return False
	if text_only and not is_text_block(block):
		return False
	if contains and contains.lower() not in block_text(block).lower():
		return False
	return True
