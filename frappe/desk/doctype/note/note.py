# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re

import frappe
from frappe.model.document import Document

NAME_PATTERN = re.compile("[%'\"#*?`]")


class Note(Document):
	def autoname(self):
		# replace forbidden characters
		self.name = NAME_PATTERN.sub("", self.title.strip())

	def validate(self):
		if self.notify_on_login and not self.expire_notification_on:

			# expire this notification in a week (default)
			self.expire_notification_on = frappe.utils.add_days(self.creation, 7)

	def before_print(self, settings=None):
		self.print_heading = self.name
		self.sub_heading = ""


@frappe.whitelist()
def mark_as_seen(note):
	if not isinstance(note, str):
		raise TypeError("note must be a string")

	doc = frappe.get_doc("Note", note)
	if frappe.session.user not in [d.user for d in doc.seen_by]:
		doc.append("seen_by", {"user": frappe.session.user})
		doc.save(ignore_version=True, ignore_permissions=True)
