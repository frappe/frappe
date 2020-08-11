# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import safe_exec
from frappe import _


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

	def execute_scheduled_method(self):
		if self.script_type == 'Scheduler Event':
			safe_exec(self.script)
		else:
			# wrong report type!
			raise frappe.DoesNotExistError

@frappe.whitelist()
def setup_scheduler_events(script_name, frequency):
	method = frappe.scrub('{0}-{1}'.format(script_name, frequency))
	scheduled_script = frappe.db.get_value('Scheduled Job Type',
		dict(method=method))

	if not scheduled_script:
		doc = frappe.get_doc(dict(
			doctype = 'Scheduled Job Type',
			method = method,
			frequency = frequency,
			server_script = script_name
		))

		doc.insert()

		frappe.msgprint(_('Enabled scheduled execution for script {0}').format(script_name))

	else:
		doc = frappe.get_doc('Scheduled Job Type', scheduled_script)
		doc.update(dict(
			doctype = 'Scheduled Job Type',
			method = method,
			frequency = frequency,
			server_script = script_name
		))
		doc.save()

		frappe.msgprint(_('Scheduled execution for script {0} has updated').format(script_name))
