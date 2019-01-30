from __future__ import unicode_literals
import frappe.utils, os

def execute():
	path = frappe.utils.get_site_path('task-logs')
	if not os.path.exists(path):
		os.makedirs(path)
