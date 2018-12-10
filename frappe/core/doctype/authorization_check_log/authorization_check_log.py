# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class AuthorizationCheckLog(Document):

	def on_rollback(self):
		"""in case log insert rolled back due to raise except, then insert back here"""
		try:
			old_name = '%s-%s' % (self.owner, self.doc_type)
			frappe.delete_doc('Authorization Check Log', old_name, force=1, ignore_permissions=1)
			self.insert(ignore_permissions=1)
			frappe.db.commit()
		except:
			pass
