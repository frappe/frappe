# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def get_context(context):
	return frappe.doc("Blog Settings", "Blog Settings").fields
