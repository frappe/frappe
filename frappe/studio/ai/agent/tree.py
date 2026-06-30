"""Server-side mirror of the canvas block tree for one agent turn.

The loop applies each client block op to this mirror as it emits it, so the
tool result handed back to the model is the truth — "applied to block X",
"3 of 12 not found", "parent not found" — instead of a blanket "Applied." that
hides a silently dropped edit (the frontend no-ops on a missing ref, and that
never travels back). A wrong ref then drives a self-correcting round.

The mirror tracks only what reference-validation needs: it resolves refs
against the live tree and keeps structure honest across rounds (remove detaches
the subtree, move reparents). Style/prop changes are not mirrored — nothing
reads them back yet. Unlike Builder, add_block assigns a componentId server-side
and echoes it (via the result message and the mutated args) so the model can
reference or bind the new block in the same turn.
"""

import frappe

from studio.ai.agent.selectors import find_block, walk_blocks


class WorkingTree:
	def __init__(self, root: dict | None):
		self.root = root

	def resolve(self, component_id: str | None) -> dict | None:
		return find_block(self.root, component_id) if (self.root and component_id) else None

	def parent_of(self, component_id: str) -> dict | None:
		for block, _ in walk_blocks(self.root):
			for child in block.get("children") or []:
				if isinstance(child, dict) and child.get("componentId") == component_id:
					return block
		return None

	def detach(self, component_id: str) -> None:
		if parent := self.parent_of(component_id):
			parent["children"] = [c for c in parent["children"] if c.get("componentId") != component_id]

	def id_hint(self, component_id: str | None) -> str:
		"""The model often passes a block's HTML id (attributes.id) instead of its
		editor ref — the most common miss. When the id matches a real block, name its
		ref."""
		for block, _ in walk_blocks(self.root or {}):
			attrs = block.get("attributes") or {}
			if component_id and attrs.get("id") == component_id:
				return (
					f" — that's the HTML id; this block's ref is '{block.get('componentId')}'. Use the ref."
				)
		return " — not a valid ref. Call query_blocks or re-read the page outline for real refs."

	def apply(self, tool_name: str, args: dict) -> str:
		args = args or {}
		if tool_name == "update_block":
			return self.apply_update(args.get("component_id"))
		if tool_name == "update_blocks":
			return self.apply_update_blocks(args)
		if tool_name == "remove_block":
			return self.apply_remove(args.get("component_id"))
		if tool_name == "move_block":
			return self.apply_move(args)
		if tool_name == "add_block":
			return self.apply_add(args)
		# Non-block client tools (scripts) carry no ref to validate.
		return "Applied."

	def apply_update(self, component_id: str | None) -> str:
		block = self.resolve(component_id)
		if block is None:
			return f"FAILED: component_id '{component_id}' not found{self.id_hint(component_id)}"
		return f"Applied to block {component_id} (<{block.get('componentName') or 'div'}>)."

	def apply_update_blocks(self, args: dict) -> str:
		patches = args.get("patches")
		if isinstance(patches, list):
			ids = [p.get("component_id") for p in patches if isinstance(p, dict)]
		else:
			ids = args.get("component_ids") or []
		if not ids:
			return "FAILED: no component_ids or patches supplied — nothing to update."
		missing = [i for i in ids if self.resolve(i) is None]
		applied = len(ids) - len(missing)
		if missing:
			return (
				f"Applied to {applied} of {len(ids)} blocks. NOT FOUND: {missing}. "
				"Those refs don't exist — recheck them, don't reissue the same ids."
			)
		return f"Applied to all {applied} block(s)."

	def apply_remove(self, component_id: str | None) -> str:
		block = self.resolve(component_id)
		if block is None:
			return f"FAILED: component_id '{component_id}' not found{self.id_hint(component_id)}"
		self.detach(component_id)
		return f"Removed block {component_id}."

	def apply_move(self, args: dict) -> str:
		component_id = args.get("component_id")
		new_parent_id = args.get("new_parent_component_id")
		block = self.resolve(component_id)
		if block is None:
			return f"FAILED: component_id '{component_id}' not found{self.id_hint(component_id)}"
		new_parent = self.resolve(new_parent_id)
		if new_parent is None:
			return f"FAILED: new_parent_component_id '{new_parent_id}' not found{self.id_hint(new_parent_id)}"
		# A block can't become a child of itself or its own descendant — that would
		# cycle the tree (and infinite-loop a later walk). Reject it like an invalid ref.
		if find_block(block, new_parent_id) is not None:
			return f"FAILED: can't move {component_id} into itself or its own descendant ({new_parent_id})."
		self.detach(component_id)
		new_parent.setdefault("children", []).append(block)
		return f"Moved block {component_id} under {new_parent_id}."

	def apply_add(self, args: dict) -> str:
		parent_id = args.get("parent_component_id")
		parent = self.resolve(parent_id)
		if parent is None:
			return f"FAILED: parent_component_id '{parent_id}' not found{self.id_hint(parent_id)}"
		component_name = args.get("component_name") or "block"
		new_id = f"{component_name}-{frappe.generate_hash(length=10)}"
		# Insert a stub so same-turn references to the new block resolve against the mirror.
		parent.setdefault("children", []).append(
			{"componentId": new_id, "componentName": component_name, "children": []}
		)
		# Echo the assigned id back through args so the loop emits the client op with the
		# same id — the model can reference or bind this block in the same turn.
		args["component_id"] = new_id
		return f"Added {component_name} block {new_id} under {parent_id}. Reference it by this id to update or bind it."
