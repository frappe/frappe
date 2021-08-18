# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class EmailGroupMember(Document):
	def after_delete(self):
		email_group = frappe.get_doc('Email Group', self.email_group)
		email_group.update_total_subscribers()

	def after_insert(self):
		email_group = frappe.get_doc('Email Group', self.email_group)
		email_group.update_total_subscribers()

def after_doctype_insert():
	frappe.db.add_unique("Email Group Member", ("email_group", "email"))
