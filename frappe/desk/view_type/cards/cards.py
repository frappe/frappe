# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _

SETTINGS_FIELDS = ("title_field", "body_field")


def validate_settings(doctype: str, settings: dict):
	"""The card's title and body fields, when set, must be fields of the doctype, and its image an Attach Image one."""
	meta = frappe.get_meta(doctype)
	for key in SETTINGS_FIELDS:
		fieldname = settings.get(key)
		if fieldname and not (
			isinstance(fieldname, str) and (fieldname == "name" or meta.has_field(fieldname))
		):
			_throw_not_a_field(doctype, fieldname)

	image = settings.get("image_field")
	if image is None or image == "":
		return
	if not (isinstance(image, str) and meta.has_field(image)):
		_throw_not_a_field(doctype, image)
	if meta.get_field(image).fieldtype != "Attach Image":
		frappe.throw(
			_("{0} is not an Attach Image field of {1}.").format(frappe.bold(image), _(doctype)),
			title=_("Invalid Card Settings"),
		)


def _throw_not_a_field(doctype: str, fieldname):
	frappe.throw(
		_("{0} is not a field of {1}.").format(frappe.bold(fieldname), _(doctype)),
		title=_("Invalid Card Settings"),
	)
