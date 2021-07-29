import frappe
from frappe.utils import random_string

def update_system_settings(args):
	doc = frappe.get_doc('System Settings')
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()

def get_system_setting(key):
	return frappe.db.get_single_value("System Settings", key)


def make_note(values=None):
	defaults = dict(
		doctype = 'Note',
		title = random_string(10),
		content = random_string(20)
	)

	defaults.update(values or {})
	return frappe.get_doc(defaults).insert(ignore_permissions=True)

def make_todo(**kwargs):
	defaults = dict(
		doctype = 'ToDo',
		description = 'Description'
	)

	defaults.update(kwargs)
	return frappe.get_doc(defaults).insert(ignore_permissions=True)

global_test_dependencies = ['User']
