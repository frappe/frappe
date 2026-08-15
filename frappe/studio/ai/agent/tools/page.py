"""Shared helpers for server tools that mutate a Studio Page's child tables
(data sources → `resources`, variables → `variables`).

Both families load the page, mutate a child table, save, commit, and emit a
`reload` event; and both warn when a deleted name is still bound somewhere. That
common machinery lives here so data.py and variables.py stay focused on their own
field shapes.
"""

import re

import frappe

from studio.ai.agent.selectors import walk_blocks


def text_arg(value) -> str:
	"""Coerce an LLM-supplied argument to a stripped string. Tool arguments are JSON
	from the model, so a field expected to be a string can arrive as a number, list, or
	dict; normalize at this trust boundary rather than crashing later on `.strip()`. A
	wrong-typed value becomes "" so the caller's own validation reports it clearly."""
	return value.strip() if isinstance(value, str) else ""


def load_page(ctx):
	return frappe.get_doc("Studio Page", ctx.page_id) if ctx.page_id else None


def save_page(page) -> str | None:
	"""Save the page (runs child-table validation + JSON conversion) and return an error
	string on failure, else None.

	The commit is intentional, not a stray mid-transaction commit: each data/variable
	tool is one atomic unit, and committing makes it durable and visible to the reload
	event the handler emits next (the canvas re-reads the child table straight after)."""
	try:
		page.save()
		frappe.db.commit()
		return None
	except frappe.ValidationError as e:
		frappe.db.rollback()
		return str(e)
	except Exception:  # noqa: BLE001 — surface a safe message; keep the real cause in the log
		frappe.db.rollback()
		frappe.log_error("Studio AI page child-table write failed", frappe.get_traceback(with_context=True))
		return "could not save the change (see error log)."


def dangling_binding_warning(ctx, name: str) -> str:
	"""Scan the (turn-start) block tree for props still referencing `name` inside a
	`{{ }}` binding, so the model can fix dangling references in the same turn."""
	root = ctx._page_root()
	if not root:
		return ""
	pattern = re.compile(r"\{\{[^}]*\b" + re.escape(name) + r"\b[^}]*\}\}")
	hits = []
	for block, _depth in walk_blocks(root):
		for value in (block.get("componentProps") or {}).values():
			if isinstance(value, str) and pattern.search(value):
				hits.append(block.get("componentId"))
				break
	if not hits:
		return ""
	return f"WARNING: these blocks still bind '{name}' and now resolve to nothing — rebind or remove them: {hits}."
