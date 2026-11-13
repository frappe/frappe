# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""What the editor loaded, so a save can refuse when someone else changed it since (#45866 r11)."""

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.app_layout import read_app_layouts
from frappe.desk.doctype.form_layout.form_layout import FORM_LAYOUT_TYPES


def base_version(doctype: str) -> dict:
	"""Design: the DocType's `modified`, each Form Layout row's `modified`, each app layout file's hash."""
	rows = frappe.get_all("Form Layout", filters={"dt": doctype}, fields=["name", "modified"])
	app_layouts = {type: read_app_layouts(doctype, type) for type in FORM_LAYOUT_TYPES}
	return {
		"doctype": str(frappe.db.get_value("DocType", doctype, "modified")),
		"layouts": {row.name: str(row.modified) for row in rows},
		"app_layouts": {type: found.version for type, found in app_layouts.items() if found},
	}


def stale_error(doctype: str, loaded: dict, rows: list[str], app_types: list[str]) -> dict | None:
	"""A banner error when the DocType, a written row or a written app file changed since `loaded`."""
	current = base_version(doctype)
	loaded = loaded or {}
	changed = loaded.get("doctype") != current["doctype"]
	changed |= any(loaded.get("layouts", {}).get(row) != current["layouts"].get(row) for row in rows)
	changed |= any(
		loaded.get("app_layouts", {}).get(type) != current["app_layouts"].get(type) for type in app_types
	)
	if not changed:
		return None
	by, at = frappe.db.get_value("DocType", doctype, ["modified_by", "modified"])
	return {
		"target": {"kind": "banner"},
		"code": "stale",
		"message": _("Changed by {0} at {1} since you opened it.").format(by, at),
		"modified_by": by,
		"modified": str(at),
	}
