# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.permissions import get_access
from frappe.website.doctype.website_group.website_group import clear_cache
from frappe.model.document import Document

class UserVote(Document):
	def after_insert(self):
		clear_cache(self.ref_name)

	def validate(self):
		# if new
		if self.get("__islocal"):
			if frappe.db.get_value("User Vote", {"ref_doctype": self.ref_doctype,
				"ref_name": self.ref_name, "owner": frappe.session.user}):

				raise frappe.DuplicateEntryError

	def on_update(self):
		self.update_ref_count()

	def on_trash(self):
		self.update_ref_count(-1)

	def update_ref_count(self, cnt=0):
		count = frappe.db.sql("""select count(*) from `tabUser Vote` where ref_doctype=%s and ref_name=%s""",
			(self.ref_doctype, self.ref_name))[0][0]
		frappe.db.set_value(self.ref_doctype, self.ref_name, "upvotes", count + cnt)

def on_doctype_update():
	frappe.db.add_index("User Vote", ["ref_doctype", "ref_name"])

# don't allow guest to give vote
@frappe.whitelist()
def set_vote(ref_doctype, ref_name):
	website_group_name = frappe.db.get_value(ref_doctype, ref_name, "website_group")
	group = frappe.get_doc("Website Group", website_group_name)

	if not get_access(group, group.get_route()).get("read"):
		raise frappe.PermissionError

	try:
		user_vote = frappe.get_doc({
			"doctype": "User Vote",
			"ref_doctype": ref_doctype,
			"ref_name": ref_name
		})
		user_vote.ignore_permissions = True
		user_vote.insert()
		return "ok"
	except frappe.DuplicateEntryError:
		return "duplicate"
