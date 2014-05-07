# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

no_cache = 1
no_sitemap = 1

def get_context(context):
	return {
		"doc": frappe.get_doc(frappe.local.form_dict.doctype, frappe.local.form_dict.name),
		"meta": frappe.get_meta(frappe.local.form_dict.doctype)
	}
