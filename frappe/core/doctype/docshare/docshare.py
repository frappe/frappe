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

	def after_insert(self):
		self.get_doc().add_comment("Shared",
			_("{0} shared this document with {1}").format(get_fullname(self.owner), get_fullname(self.user)))

	def on_trash(self):
		if not self.flags.ignore_share_permission:
			self.check_share_permission()

		self.get_doc().add_comment("Unshared",
			_("{0} un-shared this document with {1}").format(get_fullname(self.owner), get_fullname(self.user)))

def on_doctype_update():
	"""Add index in `tabDocShare` for `(user, share_doctype)`"""
	frappe.db.add_index("DocShare", ["user", "share_doctype"])
	frappe.db.add_index("DocShare", ["share_doctype", "share_name"])
