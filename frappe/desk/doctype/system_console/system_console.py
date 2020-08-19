# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

import frappe
from frappe.utils.safe_exec import safe_exec
from frappe.model.document import Document

class SystemConsole(Document):
	pass

@frappe.whitelist()
def execute_code(doc):
	doc = json.loads(doc)
	frappe.only_for('System Manager')
	try:
		frappe.debug_log = []
		safe_exec(doc['console'])
		doc['output'] = '\n'.join(frappe.debug_log)
	except:
		doc['output'] = frappe.get_traceback()

	if doc.get('commit'):
		frappe.db.commit()
	else:
		frappe.db.rollback()

	frappe.get_doc(dict(doctype='Console Log', script=doc['console'], output=doc['output'])).insert()
	frappe.db.commit()


	return doc