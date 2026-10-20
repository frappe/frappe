# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Kept for backward compatibility. Everything here now lives in `frappe.model.document`."""


def __getattr__(name):
	import frappe.model.document

	if name == "BaseDocument":
		return frappe.model.document.Document

	return getattr(frappe.model.document, name)
