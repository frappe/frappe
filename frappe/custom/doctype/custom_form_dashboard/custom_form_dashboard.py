# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
import json

class CustomFormDashboard(Document):

	def validate(self):
		links, transactions = {}, []

		for transaction in self.transactions:
			if not frappe.get_meta(transaction.document_type).has_field(self.fieldname or self.custom_fieldname):
				frappe.throw(_("Document type {0} has no field {1}.").format(frappe.bold(transaction.document_type), \
					frappe.bold(self.fieldname or self.custom_fieldname)))

			if links.get(transaction.label):
				links.get(transaction.label).append(transaction.document_type)
			else:
				links.update({transaction.label: [transaction.document_type]})

		for key, value in links.items():
			transactions.append({
				"label": key,
				"items": value
			})

		self.transactions_list = json.dumps(transactions)

	def get_form_fields_and_dashboard_field(self, doctype):
		meta = frappe.get_meta(doctype)

		return {
			"custom": meta.custom,
			"fields": get_doctype_fields(meta.fields) if meta.custom else None,
			"fieldname": meta.get_dashboard_data().get("fieldname") if not meta.custom else None
		}

def get_custom_dashboard(doctype, dashboard):
	if frappe.get_all("Custom Form Dashboard", {"name": doctype}):
		d = frappe.get_doc("Custom Form Dashboard", doctype)
		if not dashboard:
			dashboard.update({
				"fieldname": d.fieldname or d.custom_fieldname,
				"transactions": []
			})

		dashboard["transactions"].extend(json.loads(d.transactions_list))

	return dashboard

def get_doctype_fields(fields):
	return "\n".join([f.fieldname for f in fields])