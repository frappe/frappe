# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class Note(Document):
	def validate(self):
		if self.notify_on_login and not self.expire_notification_on:
			# expire this notification in a week (default)
			self.expire_notification_on = frappe.utils.add_days(self.creation, 7)

		if not self.content:
			self.content = "<span></span>"

	def before_print(self, settings=None):
		self.print_heading = self.name
		self.sub_heading = ""

	def mark_seen_by(self, user: str) -> None:
		if user in [d.user for d in self.seen_by]:
			return

		self.append("seen_by", {"user": user})


@frappe.whitelist()
def mark_as_seen(note: str):
	note: Note = frappe.get_doc("Note", note)
	note.mark_seen_by(frappe.session.user)
	note.save(ignore_permissions=True, ignore_version=True)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	return f"(`tabNote`.owner = {frappe.db.escape(user)} or `tabNote`.public = 1)"
