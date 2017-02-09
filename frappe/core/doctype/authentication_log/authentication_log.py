# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import get_fullname, now
from frappe.model.document import Document

class AuthenticationLog(Document):
	def before_insert(self):
		self.full_name = get_fullname(self.user)
		self.date = now()

def add_authentication_log(subject, user, operation="Login", status="Success"):
	frappe.get_doc({
		"doctype": "Authentication Log",
		"user": user,
		"status": status,
		"subject": subject,
		"operation": operation,
	}).insert(ignore_permissions=True)

def clear_authentication_logs():
	"""clear 100 day old authentication logs"""
	frappe.db.sql("""delete from `tabAuthentication Log` where 
		creation<DATE_SUB(NOW(), INTERVAL 100 DAY)""")