# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.doctype.data_import.importer import Importer

class DataImportMapping(Document):
	pass

@frappe.whitelist()
def get_preview_from_template(doctype, file_path):
	imp = Importer(doctype=doctype, file_path=file_path)
	return imp.get_data_for_import_preview()['columns']

