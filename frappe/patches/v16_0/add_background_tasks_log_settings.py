# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe.core.doctype.user.user import desk_properties


def execute():
	frappe.get_single("Log Settings").register_doctype("Background Task", 90)
