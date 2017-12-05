# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import format_datetime
from frappe.core.doctype.data_import.importer import upload
from frappe.utils.background_jobs import enqueue

class DataImport(Document):
	def autoname(self):
		self.name = "Import on "+ format_datetime(self.creation)

	def validate(self):
		if not self.import_file:
			self.db_set("total_rows", 0)
		if self.import_status == "In Progress":
			frappe.throw(_("Can't save the form as data import is in progress."))

		# validate the template just after the upload
		# if there is total_rows in the doc, it means that the template is already validated and error free
		if self.import_file and not self.total_rows:
			upload(data_import_doc=self, from_data_import="Yes", validate_template=True)

@frappe.whitelist()
def import_data(data_import):
	frappe.db.set_value("Data Import", data_import, "import_status", "In Progress", None, None, False)
	frappe.db.set_value("Data Import", data_import, "docstatus", 1, None, None, False)
	frappe.publish_realtime("data_import_progress", {"progress": "0",
		"data_import": data_import, "reload": True}, user=frappe.session.user)
	enqueue(upload, queue='default', timeout=6000, event='data_import',
		data_import_doc=data_import, from_data_import="Yes", validate_template=False)
