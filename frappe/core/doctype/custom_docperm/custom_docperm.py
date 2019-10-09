# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class CustomDocPerm(Document):
	def on_update(self):
		frappe.clear_cache(doctype = self.parent)
