# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document

from frappe.desk.utils import get_doctype_route

class DocTypeLayout(Document):
	def validate(self):
		if not self.route:
			self.route = get_doctype_route(self.name)
