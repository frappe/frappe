# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

page_title = "Blog"
def get_context(context):
	return frappe.get_doc("Blog Settings", "Blog Settings").as_dict()
