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
	frappe.db.sql("""UPDATE `tabError Log` SET `seen`=1
		WHERE `seen`=0 AND `creation` < (NOW() - INTERVAL '7' DAY)""")

	# clear old logs
	frappe.db.sql("""DELETE FROM `tabError Log` WHERE `creation` < (NOW() - INTERVAL '30' DAY)""")

@frappe.whitelist()
def clear_error_logs():
	'''Flush all Error Logs'''
	frappe.only_for('System Manager')
	frappe.db.sql('''DELETE FROM `tabError Log`''')