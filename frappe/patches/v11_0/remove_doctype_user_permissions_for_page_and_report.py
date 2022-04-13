# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe


def execute():
	frappe.delete_doc_if_exists("DocType", "User Permission for Page and Report")
