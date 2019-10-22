# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import safe_exec

class ServerScript(Document):
	@staticmethod
	def validate():
		frappe.only_for('Script Manager', True)

	@staticmethod
	def on_update():
		frappe.cache().delete_value('server_script_map')

	def execute_method(self):
		if self.script_type == 'API':
			# validate if guest is allowed
			if frappe.session.user == 'Guest' and not self.allow_guest:
				raise frappe.PermissionError
			safe_exec(self.script)
		else:
			# wrong report type!
			raise frappe.DoesNotExistError

	def execute_doc(self, doc):
		# execute event
		safe_exec(self.script, None, dict(doc = doc))

