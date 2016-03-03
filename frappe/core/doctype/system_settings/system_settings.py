# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model import no_value_fields
from frappe.translate import set_default_language
from frappe.utils import cint
from frappe.utils.momentjs import get_all_timezones

class SystemSettings(Document):
	def validate(self):
		for key in ("session_expiry", "session_expiry_mobile"):
			if self.get(key):
				parts = self.get(key).split(":")
				if len(parts)!=2 or not (cint(parts[0]) or cint(parts[1])):
					frappe.throw(_("Session Expiry must be in format {0}").format("hh:mm"))

	def on_update(self):
		for df in self.meta.get("fields"):
			if df.fieldtype not in no_value_fields:
				frappe.db.set_default(df.fieldname, self.get(df.fieldname))

		if self.language:
			set_default_language(self.language)

@frappe.whitelist()
def load():
	if not "System Manager" in frappe.get_roles():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	all_defaults = frappe.db.get_defaults()
	defaults = {}

	for df in frappe.get_meta("System Settings").get("fields"):
		if df.fieldtype in ("Select", "Data"):
			defaults[df.fieldname] = all_defaults.get(df.fieldname)

	return {
		"timezones": get_all_timezones(),
		"defaults": defaults
	}
