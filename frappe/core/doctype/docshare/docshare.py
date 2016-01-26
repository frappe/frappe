# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_fullname

exclude_from_linked_with = True

class DocShare(Document):
	no_feed_on_delete = True

	def validate(self):
		self.validate_user()
		self.check_share_permission()
		self.cascade_permissions_downwards()
		self.get_doc().run_method("validate_share", self)

	def cascade_permissions_downwards(self):
		if self.share:
			self.write = 1
		if self.write:
			self.read = 1

	def get_doc(self):
		if not getattr(self, "_doc", None):
			self._doc = frappe.get_doc(self.share_doctype, self.share_name)
		return self._doc

	def validate_user(self):
		if self.everyone:
			self.user = None
		elif not self.user:
			frappe.throw(_("User is mandatory for Share"), frappe.MandatoryError)

	def check_share_permission(self):
		if (not self.flags.ignore_share_permission and
			not frappe.has_permission(self.share_doctype, "share", self.get_doc())):

			frappe.throw(_('You need to have "Share" permission'), frappe.PermissionError)
			# if owner has the permission to write then only allow the self.user to write permission
		elif not frappe.has_permission(self.share_doctype, "write", self.get_doc(), self.owner):
			self.write = 0
			frappe.msgprint(_('You need to have "Write" permission'))

	def after_insert(self):
		doc = self.get_doc()
		owner = get_fullname(self.owner)

		if self.everyone:
			doc.add_comment("Shared", _("{0} shared this document with everyone").format(owner))
		else:
			doc.add_comment("Shared", _("{0} shared this document with {1}").format(owner, get_fullname(self.user)))

	def on_trash(self):
		if not self.flags.ignore_share_permission:
			self.check_share_permission()

		self.get_doc().add_comment("Unshared",
			_("{0} un-shared this document with {1}").format(get_fullname(self.owner), get_fullname(self.user)))

def on_doctype_update():
	"""Add index in `tabDocShare` for `(user, share_doctype)`"""
	frappe.db.add_index("DocShare", ["user", "share_doctype"])
	frappe.db.add_index("DocShare", ["share_doctype", "share_name"])

@frappe.whitelist()
def docshare_user_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.reportview import get_match_cond
	txt = "%{}%".format(txt)
	
	# excluding Guest User and session user
	exclude_users = ["Guest"]
	if filters.get("user") not in exclude_users: exclude_users.append(filters.get("user"))
	get_all_filters = {
		"share_name":filters.get("docname"),
		"share_doctype":filters.get("doctype"),
	}
	
	# excluding the user to whom the document is already shared
	shared_with = frappe.db.get_all("DocShare", filters=get_all_filters, fields="user", as_list=True)
	exclude_users.extend([user[0] for user in shared_with])
	exclude_users = list(set(exclude_users))

	query = """	select name, concat_ws(' ', first_name, middle_name, last_name)
				from `tabUser`
				where enabled=1
					and docstatus < 2
					and name not in ({exclude_users})
					and user_type != 'Website User'
					and ({key} like %s
						or concat_ws(' ', first_name, middle_name, last_name) like %s)
				order by
					case when name like %s then 0 else 1 end,
					case when concat_ws(' ', first_name, middle_name, last_name) like %s
						then 0 else 1 end,
					name asc
				limit %s, %s""".format(exclude_users=", ".join(["%s"]*len(exclude_users)),
					key=searchfield)

	return frappe.db.sql(query, tuple(list(exclude_users) + [txt, txt, txt, txt, start, page_len]))