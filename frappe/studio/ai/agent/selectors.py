"""Tree helpers for the agent's selector tools.

The server already holds the full page tree (the frontend ships it as
`page_context`), so block selection and inspection are answered here without a
frontend round-trip. These walk the native block dict (componentName /
componentId / children / …) — the same shape `BlockCodec` operates on.
"""

from collections.abc import Iterator


def walk_blocks(root: dict, depth: int = 0) -> Iterator[tuple[dict, int]]:
	"""Yield (block, depth) for the root and every descendant, depth-first."""
	if not isinstance(root, dict):
		return
	yield root, depth
	for child in root.get("children") or []:
		if isinstance(child, dict):
			yield from walk_blocks(child, depth + 1)


def find_block(root: dict, component_id: str) -> dict | None:
	"""Return the block with this componentId, or None."""
	for block, _depth in walk_blocks(root):
		if block.get("componentId") == component_id:
			return block
	return None
