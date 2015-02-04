# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_fullname

class DocShare(Document):
	no_feed_on_delete = True

	def validate(self):
		if not frappe.has_permission(self.share_doctype, "share",
			frappe.get_doc(self.share_doctype, self.share_name)):
			frappe.throw(_("Not Allowed"), frappe.PermissionError)
		self.cascade_permissions_downwards()

	def cascade_permissions_downwards(self):
		if self.share:
			self.write = 1
		if self.write:
			self.read = 1

	def after_insert(self):
		self.add_comment(_("{0} shared this document with {0}").format(get_fullname(self.owner), get_fullname(self.user)))

	def on_trash(self):
		self.add_comment(_("{0} un-shared this document with {0}").format(get_fullname(self.owner), get_fullname(self.user)))

def on_doctype_update():
	"""Add index in `tabDocShare` for `(user, share_doctype)`"""
	frappe.db.add_index("DocShare", ["user", "share_doctype"])
