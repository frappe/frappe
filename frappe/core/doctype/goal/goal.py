# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Goal(Document):
	def fetch_fields(self):
		if not self.source:
			return

		meta = frappe.get_meta(self.source)

		print meta.get("fields")
		return [d.fieldname for d in meta.get("fields")]
