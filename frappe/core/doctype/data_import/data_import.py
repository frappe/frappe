# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import format_datetime

class DataImport(Document):
	def validate(self):
		if not frappe.flags.in_test:
			self.name = "Import on "+ format_datetime(self.creation)

	def import_data(self, args=None):
		print ("********************************")
		args = frappe._dict(args)
		if args.validate:
			upload(data_import_doc=self, from_data_import="Yes", validate_template=True)
		else:
			upload(data_import_doc=self, from_data_import="Yes")
