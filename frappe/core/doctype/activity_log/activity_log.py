# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe import _
from frappe.utils import get_fullname, now
from frappe.model.document import Document
from frappe.core.utils import set_timeline_doc
import frappe
from frappe.query_builder import DocType, Interval
from frappe.query_builder.functions import Now
from pypika.terms import PseudoColumn

class ActivityLog(Document):
	def before_insert(self):
		self.full_name = get_fullname(self.user)
		self.date = now()

	def validate(self):
		self.set_status()
		set_timeline_doc(self)

	def set_status(self):
		if not self.is_new():
			return

		if self.reference_doctype and self.reference_name:
			self.status = "Linked"

def on_doctype_update():
	"""Add indexes in `tabActivity Log`"""
	frappe.db.add_index("Activity Log", ["reference_doctype", "reference_name"])
	frappe.db.add_index("Activity Log", ["timeline_doctype", "timeline_name"])
	frappe.db.add_index("Activity Log", ["link_doctype", "link_name"])

def add_authentication_log(subject, user, operation="Login", status="Success"):
	frappe.get_doc({
		"doctype": "Activity Log",
		"user": user,
		"status": status,
		"subject": subject,
		"operation": operation,
	}).insert(ignore_permissions=True, ignore_links=True)

def clear_activity_logs(days=None):
	"""clear 90 day old authentication logs or configured in log settings"""

	if not days:
		days = 90
	doctype = DocType("Activity Log")
	frappe.db.delete(doctype, filters=(
		doctype.creation < PseudoColumn(f"({Now() - Interval(days=days)})")
	))