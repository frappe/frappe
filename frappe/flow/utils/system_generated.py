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
	"""Call from validate. Blocks unsetting the flag and edits to `fields` (columns, or Table
	MultiSelect fields compared by their rows' links), against DB values so tampering with the
	flag can't disarm the other guards."""
	if doc.is_new() or doc.flags.ignore_permissions:
		return
	tables = [f for f in fields if doc.meta.get_field(f).fieldtype == "Table MultiSelect"]
	columns = [f for f in fields if f not in tables]
	before = frappe.db.get_value(doc.doctype, doc.name, ["is_system_generated", *columns], as_dict=True)
	if not before or not before.is_system_generated:
		return
	if not doc.is_system_generated:
		frappe.throw(
			_("Cannot remove the system-generated flag from {0} {1}.").format(_(doc.doctype), doc.name),
			title=_("Protected"),
		)
	for fieldname in fields:
		if fieldname in tables:
			saved, current = _table_links(doc, fieldname)
		else:
			saved, current = before.get(fieldname), doc.get(fieldname)
		if saved != current:
			frappe.throw(
				_("Cannot change {0} of system-generated {1} {2}.").format(
					_(doc.meta.get_label(fieldname)), _(doc.doctype), doc.name
				),
				title=_("Protected"),
			)


def _table_links(doc, fieldname: str) -> tuple[list, list]:
	"""The saved and the current link values of a Table MultiSelect field, in row order."""
	df = doc.meta.get_field(fieldname)
	link = next(f.fieldname for f in frappe.get_meta(df.options).fields if f.fieldtype == "Link")
	saved = frappe.get_all(
		df.options, {"parent": doc.name, "parentfield": fieldname}, pluck=link, order_by="idx"
	)
	return saved, [row.get(link) for row in doc.get(fieldname)]


def block_delete(doc, always: bool = False) -> None:
	"""Call from on_trash. The owning app deletes with ignore_permissions, e.g. in a patch
	after a rename; `always=True` blocks even that, for Flow's own builtin agent and tools."""
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
