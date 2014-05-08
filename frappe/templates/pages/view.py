# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

no_cache = 1
no_sitemap = 1

def get_context(context):
	doc = frappe.get_doc(frappe.local.form_dict.doctype, frappe.local.form_dict.name)
	doc.run_method("make_view")
	return {
		"doc": doc,
		"meta": doc.meta
	}
