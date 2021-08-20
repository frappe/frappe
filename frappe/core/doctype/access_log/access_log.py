# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

# imports - standard imports
from __future__ import unicode_literals

# imports - module imports
import frappe
from frappe.model.document import Document


class AccessLog(Document):
	pass


@frappe.whitelist()
def make_access_log(doctype=None, document=None, method=None, file_type=None,
		report_name=None, filters=None, page=None, columns=None):

	user = frappe.session.user

	doc = frappe.get_doc({
		'doctype': 'Access Log',
		'user': user,
		'export_from': doctype,
		'reference_document': document,
		'file_type': file_type,
		'report_name': report_name,
		'page': page,
		'method': method,
		'filters': frappe.utils.cstr(filters) if filters else None,
		'columns': columns
	})
	doc.insert(ignore_permissions=True)

	# `frappe.db.commit` added because insert doesnt `commit` when called in GET requests like `printview`
	frappe.db.commit()
