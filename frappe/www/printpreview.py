# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe.utils.weasyprint import get_html

no_cache = 1

def get_context(context):
	doctype = frappe.form_dict.doctype
	name = frappe.form_dict.name
	print_format = frappe.form_dict.print_format
	letterhead = frappe.form_dict.letterhead
	context.no_cache = 1
	context.html = get_html(doctype, name, print_format, letterhead)
