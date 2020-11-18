# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document

class DocTypeLayout(Document):
	def validate(self):
		frappe.cache().delete_value('doctype_name_map')
