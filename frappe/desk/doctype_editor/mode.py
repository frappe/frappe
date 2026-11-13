# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Who may open the DocType editor in each mode."""

import frappe
from frappe import _
from frappe.model import core_doctypes_list

MODES = ("Design", "Customize")


def check_mode(doctype: str, mode: str) -> None:
	"""Throw `PermissionError` unless the session user may open `doctype` in `mode`."""
	if mode not in MODES:
		frappe.throw(_("{0} is not an editor mode.").format(mode))
	if refusal := mode_refusal(doctype, mode):
		frappe.throw(refusal, frappe.PermissionError)


def mode_refusal(doctype: str, mode: str) -> str | None:
	custom, issingle = frappe.db.get_value("DocType", doctype, ["custom", "issingle"]) or (None, None)
	if custom is None:
		return _("{0} is not a DocType.").format(frappe.bold(doctype))
	if mode == "Customize":
		if custom:
			return _("{0} is a custom DocType: it always opens in Design mode.").format(frappe.bold(doctype))
		if doctype in core_doctypes_list:
			return _("{0} is a core DocType and cannot be customized.").format(frappe.bold(doctype))
		if issingle:
			return _("A standard Single opens only in Design mode.")
		if not frappe.has_permission("Customize Form", "write"):
			return _("Customize mode needs write access to Customize Form.")
		return None
	if "System Manager" not in frappe.get_roles():
		return _("Design mode needs the System Manager role.")
	if not custom and not frappe.conf.developer_mode:
		return _("Design mode on a standard DocType needs developer mode.")
	return None
