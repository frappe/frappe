# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Guards for rows flagged `is_system_generated`.

Such rows are owned by the app that ships them: permission-checked (Desk/API)
writes cannot break them, while the owning app keeps full control by passing
`ignore_permissions=True`. Renames are blocked outright because frappe's
rename_doc never propagates ignore_permissions to the doc.
"""

from __future__ import annotations

import frappe
from frappe import _


def validate_immutable(doc, fields: tuple[str, ...] = ()) -> None:
	"""Call from validate. Blocks unsetting the flag and edits to `fields`, comparing
	against DB values so tampering with the flag can't disarm the other guards."""
	if doc.is_new() or doc.flags.ignore_permissions:
		return
	before = frappe.db.get_value(doc.doctype, doc.name, ["is_system_generated", *fields], as_dict=True)
	if not before or not before.is_system_generated:
		return
	if not doc.is_system_generated:
		frappe.throw(
			_("Cannot remove the system-generated flag from {0} {1}.").format(_(doc.doctype), doc.name),
			title=_("Protected"),
		)
	for fieldname in fields:
		if before.get(fieldname) != doc.get(fieldname):
			frappe.throw(
				_("Cannot change {0} of system-generated {1} {2}.").format(
					_(doc.meta.get_label(fieldname)), _(doc.doctype), doc.name
				),
				title=_("Protected"),
			)


def block_delete(doc, always: bool = False) -> None:
	"""Call from on_trash. `always=True` blocks even the owning app — for rows Flow
	itself ships (builtin agent/tools) that must never disappear."""
	if doc.is_system_generated and (always or not doc.flags.ignore_permissions):
		frappe.throw(
			_("Cannot delete system-generated {0} {1}.").format(_(doc.doctype), doc.name),
			title=_("Protected"),
		)


def block_rename(doc, old: str) -> None:
	"""Call from before_rename."""
	if doc.is_system_generated:
		frappe.throw(
			_("Cannot rename system-generated {0} {1}.").format(_(doc.doctype), old),
			title=_("Protected"),
		)
