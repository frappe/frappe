# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

import frappe, frappe.utils, os
from frappe import conf
from frappe.model.document import Document
from frappe.utils.file_manager import delete_file_data_content

class FileData(Document):
	def before_insert(self):
		frappe.local.rollback_observers.append(self)

	def validate(self):
		if not getattr(self, "ignore_duplicate_entry_error", False):
			# check duplicate assignement
			n_records = frappe.db.sql("""select name from `tabFile Data`
				where content_hash=%s
				and name!=%s
				and attached_to_doctype=%s
				and attached_to_name=%s""", (self.content_hash, self.name, self.attached_to_doctype,
					self.attached_to_name))
			if len(n_records) > 0:
				self.duplicate_entry = n_records[0][0]
				frappe.throw(frappe._("Same file has already been attached to the record"), frappe.DuplicateEntryError)

	def on_trash(self):
		if self.attached_to_name:
			# check persmission
			try:
				if not getattr(self, 'ignore_permissions', False) and \
					not frappe.has_permission(self.attached_to_doctype, "write", self.attached_to_name):

					frappe.msgprint(frappe._("No permission to write / remove."), raise_exception=True)

			except frappe.DoesNotExistError:
				pass

		# if file not attached to any other record, delete it
		if self.file_name and self.content_hash and (not frappe.db.count("File Data",
			{"content_hash": self.content_hash, "name": ["!=", self.name]})):
				delete_file_data_content(self)

	def on_rollback(self):
		self.on_trash()
