# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import safe_exec


class SystemConsole(Document):
	def run(self):
		frappe.only_for("System Manager")
		try:
			frappe.debug_log = []
			safe_exec(self.console)
			self.output = "\n".join(frappe.debug_log)
		except Exception:
			self.output = frappe.get_traceback()

		if self.commit:
			frappe.db.commit()
		else:
			frappe.db.rollback()

		frappe.get_doc(dict(doctype="Console Log", script=self.console, output=self.output)).insert()
		frappe.db.commit()


@frappe.whitelist()
def execute_code(doc):
	console = frappe.get_doc(json.loads(doc))
	console.run()
	return console.as_dict()
