# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import nowdate, add_days
from frappe.model.document import Document

class LogSettings(Document):
	pass

@frappe.whitelist()
def get_log_doctypes(doctype, txt, searchfield, start, page_len, filters):
	doctypes = frappe.get_all("DocType", filters={"istable": 0, "issingle": 0, "name": ('like', '%Log')})
	return [[entry.name] for entry in doctypes]

def clear_logs():
	for entry in frappe.get_single('Log Settings').log_settings:
		frappe.db.sql("""DELETE FROM `tab{0}` WHERE creation < %s""".format(entry.ref_doctype), add_days(nowdate(), -int(entry.log_days)))