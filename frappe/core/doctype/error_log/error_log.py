# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ErrorLog(Document):
	def onload(self):
		if not self.seen:
			self.db_set('seen', 1, update_modified=0)
			frappe.db.commit()

def set_old_logs_as_seen():
	# set logs as seen
	frappe.db.sql("""update `tabError Log` set seen=1
		where seen=0 and datediff(curdate(), creation) > 7""")

	# clear old logs
	frappe.db.sql("""delete from `tabError Log` where datediff(curdate(), creation) > 30""")

@frappe.whitelist()
def clear_error_logs():
	'''Flush all Error Logs'''
	frappe.only_for('System Manager')
	frappe.db.sql('''delete from `tabError Log`''')