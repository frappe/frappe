# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json, os
from frappe import _

@frappe.whitelist()
def get():
	setup = []
	for app in frappe.get_installed_apps():
		try:
			setup += frappe.get_attr(app + ".config.setup.data")
		except ImportError, e:
			pass

	return setup
