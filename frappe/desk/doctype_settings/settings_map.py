# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE
"""Backend for the DocType Settings → General tab.

Settings scattered across Single doctypes (Selling Settings, Accounts Settings, …) are
mapped to the doctypes they affect via `DocType Settings Map` records. A doctype may have a
standard (shipped) map and/or a custom (user) map, but only one is active at a time (the
controller enforces single-active). Its `mappings` grid names a Settings DocType and one of
its fields per row. This resolves the active map's rows into editable fields (label / type /
description / value pulled live from the source single), grouped by source single. Both
document-level and field-level (permlevel) permissions on the source single are honored:
fields the user can't read at their permlevel are dropped, and each field carries its own
`can_write` flag.
"""

import frappe
from frappe import _
from frappe.model import no_value_fields


@frappe.whitelist()
def has_settings_map(doctype: str) -> bool:
	"""Cheap existence check: does this doctype have a settings map?

	Used to decide whether to show the General tab without resolving every field's metadata
	and value. Pure existence — the full resolve happens in `get_settings_map`."""
	# Gate on read access to the target doctype so this doesn't leak map existence for
	# doctypes the caller can't see (matches the guard `get_settings_map` applies).
	if not frappe.has_permission(doctype, "read"):
		return False
	return bool(frappe.db.exists("DocType Settings Map", {"applies_to_doctype": doctype, "is_active": 1}))


@frappe.whitelist()
def get_settings_map(doctype: str) -> list[dict]:
	"""Resolve `doctype`'s settings-map rows into grouped, editable fields.

	Only Single source doctypes the user can read are returned; each group carries a
	`can_write` flag so the tab can render read-only when the user lacks write access.
	Saving is done client-side via `frappe.client.set_value` (which re-checks permission)."""
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(doctype), frappe.DoesNotExistError)

	# Gate on read access to the target doctype — without this, a caller without access to
	# `doctype` could still learn it has a settings map and read every mapped Single field
	# they happen to have access to (matches the guard `has_settings_map` applies).
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You are not permitted to access {0}.".format(doctype)), frappe.PermissionError)

	# Exactly one map per doctype is active (enforced by the controller). `is_standard asc`
	# is a defensive tie-break (custom before standard) in case of inconsistent data.
	active = frappe.get_all(
		"DocType Settings Map",
		filters={"applies_to_doctype": doctype, "is_active": 1},
		fields=["name"],
		order_by="is_standard asc",
		limit=1,
	)
	if not active:
		return []
	mappings = frappe.get_cached_doc("DocType Settings Map", active[0].name).mappings

	# Group the mapped fieldnames by their source Settings doctype, preserving order.
	by_single: dict[str, list[str]] = {}
	for row in mappings:
		if row.settings_doctype and row.setting_field:
			by_single.setdefault(row.settings_doctype, []).append(row.setting_field)

	groups = []
	for single, fieldnames in by_single.items():
		single_meta = frappe.get_meta(single)
		# A settings map only makes sense for Single ("Settings") doctypes the user can see.
		if not single_meta.issingle or not frappe.has_permission(single, "read"):
			continue

		# Field-level (permlevel) access: a field is shown only if the user has read at its
		# permlevel, and is editable only with both doc-level write and write at its permlevel.
		# `can_write` is a UI hint only — the real write check happens server-side on save via
		# `frappe.client.set_value`, so this boolean isn't the enforcement boundary.
		doc_write = bool(frappe.has_permission(single, "write"))
		read_levels = single_meta.get_permlevel_access("read")
		write_levels = single_meta.get_permlevel_access("write")

		doc = frappe.get_cached_doc(single)
		fields = []
		for fieldname in fieldnames:
			df = single_meta.get_field(fieldname)
			if not df:
				continue
			permlevel = df.permlevel or 0
			# Skip fields the user can't read at their permlevel.
			if permlevel not in read_levels:
				continue
			fields.append(
				{
					"fieldname": df.fieldname,
					"label": df.label if df.label else df.fieldname,
					"fieldtype": df.fieldtype,
					"options": df.options,
					"description": df.description,
					"value": doc.get(df.fieldname),
					"can_write": doc_write and permlevel in write_levels,
					# Raw expressions (JavaScript) — evaluated client-side, so NOT translated.
					"depends_on": df.get("depends_on") or None,
					"read_only_depends_on": df.get("read_only_depends_on") or None,
				}
			)

		if not fields:
			continue

		# `doc` context for client-side depends_on evaluation: every value-bearing field the
		# user can read at their permlevel (a depends_on often references a non-mapped field).
		# Fields above the user's read permlevel are omitted, so expressions referencing them
		# evaluate against `undefined` (the dependent field hides — the safe default).
		doc_context = {
			f.fieldname: doc.get(f.fieldname)
			for f in single_meta.fields
			if (f.permlevel or 0) in read_levels and f.fieldtype not in no_value_fields
		}

		groups.append(
			{
				"settings": single,
				"label": single,
				"doc": doc_context,
				"fields": fields,
			}
		)

	return groups
