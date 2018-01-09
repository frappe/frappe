# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class UserEmail(Document):
	pass

@frappe.whitelist()
def get_gravatar_url(email, size = 0):
	return frappe.utils.get_gravatar_url(email, size)
