# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ErrorLog(Document):
	def onload(self):
		if not self.seen:
			self.seen = 1
			self.save()

def set_old_logs_as_seen():
	frappe.db.sql("""update `tabError Log` set seen=1
		where seen=0 and datediff(curdate(), creation) > 7""")
