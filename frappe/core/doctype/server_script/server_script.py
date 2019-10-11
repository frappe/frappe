# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import safe_exec

class ServerScriptNotEnabled(frappe.PermissionError): pass

class ServerScript(Document):
	def validate(self):
		frappe.only_for('Script Manager')

	def on_update(self):
		frappe.cache().delete_value('server_script_map')

	def execute_method(self):
		if not frappe.conf.server_script_enabled:
			raise ServerScriptNotEnabled
		if self.script_type == 'API':
			if frappe.session.user == 'Guest' and not self.allow_guest:
				raise frappe.PermissionError
			safe_exec(self.script)
		else:
			raise frappe.DoesNotExistError

	def execute_doc(self, doc):
		if not frappe.conf.server_script_enabled:
			raise ServerScriptNotEnabled
		context = dict(doc = doc)
		safe_exec(self.script, None, context)

