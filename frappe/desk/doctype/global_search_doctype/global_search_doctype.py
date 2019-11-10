# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class GlobalSearchDocType(Document):

	def on_doctype_update():
		frappe.db.add_index("Global Search DocType", ["document_type"])
