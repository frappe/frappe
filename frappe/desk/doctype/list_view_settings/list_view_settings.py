# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ListViewSettings(Document):

	def validate(self):
		frappe.clear_document_cache(self.doctype, self.name)