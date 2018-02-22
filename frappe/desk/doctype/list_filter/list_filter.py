# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document

class ListFilter(Document):
	pass

@frappe.whitelist()
def get_filters(doctype):
	filters = frappe.get_all('List Filter',
		# global filters
		filters={'reference_doctype': doctype, 'for_user': ''},
		# user filters
		or_filters={'reference_doctype': doctype, 'for_user': frappe.session.user},
		fields=['name', 'filter_name', 'filters', 'for_user'],
		order_by='filter_name'
	)

	return filters

@frappe.whitelist()
def remove(name):
	frappe.delete_doc('List Filter', name, ignore_permissions=1)
	return

@frappe.whitelist()
def add(filter_name, reference_doctype, filters, user=None):

	if isinstance(filters, unicode):
		filters = json.loads(filters)

	doc = frappe.get_doc({
		'doctype': 'List Filter',
		'filter_name': filter_name,
		'reference_doctype': reference_doctype,
		'for_user': user,
		'filters': filters
	}).insert()

	return doc
