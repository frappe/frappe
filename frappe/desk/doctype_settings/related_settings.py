# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
"""Backend for the DocType Settings → Related Settings tab.

Settings scattered across Single doctypes (Selling Settings, Accounts Settings, …) are
linked to the doctypes they affect through the target doctype's `related_settings` child
table — each row points at a Settings DocType and one of its fields. This resolves those
rows into editable fields (label / type / description / value pulled live from the source
single), grouped by source single, with a per-single write-permission flag.
"""

import frappe
from frappe import _


@frappe.whitelist()
def has_related_settings(doctype: str) -> bool:
	"""Cheap existence check: does this doctype map any related settings?

	Used to decide whether to show the General tab without resolving every field's metadata
	and value. Pure row existence — the full resolve happens in `get_related_settings`."""
	return bool(frappe.db.exists("DocType Related Setting", {"parenttype": "DocType", "parent": doctype}))


@frappe.whitelist()
def get_related_settings(doctype: str) -> list[dict]:
	"""Resolve `doctype`'s related-settings mappings into grouped, editable fields.

	Only Single source doctypes the user can read are returned; each group carries a
	`can_write` flag so the tab can render read-only when the user lacks write access.
	Saving is done client-side via `frappe.client.set_value` (which re-checks permission)."""
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype), frappe.DoesNotExistError)

	meta = frappe.get_meta(doctype)
	mappings = meta.get("related_settings") or []

	# Group the mapped fieldnames by their source Settings doctype, preserving order.
	by_single: dict[str, list[str]] = {}
	for row in mappings:
		if row.settings_doctype and row.setting_field:
			by_single.setdefault(row.settings_doctype, []).append(row.setting_field)

	groups = []
	for single, fieldnames in by_single.items():
		single_meta = frappe.get_meta(single)
		# Related Settings only makes sense for Single ("Settings") doctypes the user can see.
		if not single_meta.issingle or not frappe.has_permission(single, "read"):
			continue

		doc = frappe.get_cached_doc(single)
		fields = []
		for fieldname in fieldnames:
			df = single_meta.get_field(fieldname)
			if not df:
				continue
			fields.append(
				{
					"fieldname": df.fieldname,
					"label": _(df.label) if df.label else df.fieldname,
					"fieldtype": df.fieldtype,
					"options": df.options,
					"description": _(df.description) if df.description else None,
					"value": doc.get(df.fieldname),
				}
			)

		if not fields:
			continue

		groups.append(
			{
				"settings": single,
				"label": _(single),
				"can_write": bool(frappe.has_permission(single, "write")),
				"fields": fields,
			}
		)

	return groups
