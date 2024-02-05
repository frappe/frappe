# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class Note(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.note_seen_by.note_seen_by import NoteSeenBy
		from frappe.types import DF

		content: DF.TextEditor | None
		expire_notification_on: DF.Date | None
		notify_on_every_login: DF.Check
		notify_on_login: DF.Check
		public: DF.Check
		seen_by: DF.Table[NoteSeenBy]
		title: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.notify_on_login and not self.expire_notification_on:
			# expire this notification in a week (default)
			self.expire_notification_on = frappe.utils.add_days(self.creation, 7)

		if not self.public and self.notify_on_login:
			self.notify_on_login = 0

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


def has_permission(doc, user):
	return bool(doc.public or doc.owner == user)
