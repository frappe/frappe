# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class UserViewSettings(Document):
	pass

def on_doctype_update():
	frappe.db.add_index("User View Settings", ["view", "sort_by", "sort_order", "document_type"])
