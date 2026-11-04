# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _

SETTINGS_FIELDS = ("title_field", "body_field")


def validate_settings(doctype: str, settings: dict):
	"""The card's title and body fields, when set, must be fields of the doctype."""
	meta = frappe.get_meta(doctype)
	for key in SETTINGS_FIELDS:
		fieldname = settings.get(key)
		if fieldname and not (
			isinstance(fieldname, str) and (fieldname == "name" or meta.has_field(fieldname))
		):
			frappe.throw(
				_("{0} is not a field of {1}.").format(frappe.bold(fieldname), _(doctype)),
				title=_("Invalid Card Settings"),
			)
