# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals
import frappe
from frappe import throw, _

from frappe.model.document import Document

class Currency(Document):
	def validate(self):
		frappe.clear_cache()
